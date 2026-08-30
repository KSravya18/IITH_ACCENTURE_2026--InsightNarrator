"""
STEP 2: Anomaly Detection
==========================
Goal (plain English): look at every region+product's weekly revenue,
and automatically spot weeks where the number is "weird" compared to
its own recent normal pattern -- without a human eyeballing a chart.

We do NOT use AI here. This is pure statistics:
  - For each region+product, look at the last 6 weeks of revenue.
  - Calculate the average and how much it normally wobbles (std deviation).
  - If this week's number is much further from that average than usual,
    flag it as a real anomaly (not just normal noise).
"""
import pandas as pd
import numpy as np

sales = pd.read_csv("data/sales_weekly.csv")
sales["week"] = pd.to_datetime(sales["week"])

# -------------------------------------------------------------------
# STEP 2a: RECONCILIATION (explicit, visible step)
# -------------------------------------------------------------------
def reconcile_sources():
    """
    Plain English: our 3 sources don't naturally line up.
      - Sales is already weekly, per region+product.
      - Marketing is weekly, per region (not per product).
      - Complaints have IRREGULAR timestamps (whenever a customer
        writes in) -- not weekly at all.

    This function forces all 3 onto ONE common weekly calendar per
    region, so they can be compared apples-to-apples. This is the
    "reconcile data across heterogeneous sources" requirement, made
    visible and auditable rather than implicit.
    """
    mkt = pd.read_csv("data/marketing_weekly.csv")
    mkt["week"] = pd.to_datetime(mkt["week"])
    complaints = pd.read_csv("data/complaints_log.csv")
    complaints["date"] = pd.to_datetime(complaints["date"])

    # Sales: already weekly, per region+product -> aggregate to region+week for joining
    sales_region_week = sales.groupby(["region", "week"], as_index=False)["revenue"].sum()

    # Marketing: already weekly, per region -> sum across channels
    mkt_region_week = mkt.groupby(["region", "week"], as_index=False)["spend"].sum()

    # Complaints: IRREGULAR timestamps -> bin onto the same weekly calendar
    # as sales/marketing using the nearest week-ending date, so a complaint
    # filed on a Tuesday lines up with the Sunday-dated weekly bucket.
    all_weeks = sorted(sales["week"].unique())
    def nearest_week(d):
        return min(all_weeks, key=lambda w: abs((w - d).days))
    complaints["aligned_week"] = complaints["date"].apply(nearest_week)
    complaints_region_week = complaints.groupby(["region", "aligned_week"], as_index=False).size()
    complaints_region_week.columns = ["region", "week", "complaint_count"]

    # Merge all 3 onto one reconciled table (region+week grain)
    reconciled = sales_region_week.merge(mkt_region_week, on=["region", "week"], how="left")
    reconciled = reconciled.merge(complaints_region_week, on=["region", "week"], how="left")
    reconciled["complaint_count"] = reconciled["complaint_count"].fillna(0).astype(int)
    reconciled["spend"] = reconciled["spend"].fillna(0)

    reconciled.to_csv("data/reconciled_weekly.csv", index=False)
    return reconciled


def detect_anomalies(df, value_col="revenue", group_cols=("region", "product"),
                      window=6, z_thresh=1.8, min_pct_impact=8):
    """
    Generalized so the SAME detection logic can monitor any of our
    5 connected KPIs (revenue, units_sold, average_selling_price,
    marketing_spend, complaint_volume) -- not just revenue.

    value_col: which KPI column to check
    group_cols: what to group by (region+product, or just region for
                KPIs that aren't tracked per-product)
    window: how many past weeks count as "recent normal"
    z_thresh: how many standard deviations away counts as "weird"
    min_pct_impact: also require at least this % change, so we ignore
                    statistically odd but practically tiny wobbles
    """
    anomalies = []
    for key, g in df.groupby(list(group_cols)):
        g = g.sort_values("week").reset_index(drop=True)
        if len(g) < 4:
            continue  # too little history to judge (sparse-history case)

        g["rolling_mean"] = g[value_col].rolling(window, min_periods=3).mean()
        g["rolling_std"] = g[value_col].rolling(window, min_periods=3).std()
        g["z_score"] = (g[value_col] - g["rolling_mean"]) / g["rolling_std"]
        g["pct_change"] = (g[value_col] - g["rolling_mean"]) / g["rolling_mean"] * 100

        flagged = g[(g["z_score"].abs() > z_thresh) & (g["pct_change"].abs() > min_pct_impact)]

        for _, row in flagged.iterrows():
            entry = {"kpi": value_col, "week": row["week"].date().isoformat(),
                      "actual_value": round(row[value_col], 2),
                      "expected_value": round(row["rolling_mean"], 2),
                      "pct_change": round(row["pct_change"], 1),
                      "z_score": round(row["z_score"], 2)}
            for i, col in enumerate(group_cols):
                entry[col] = key[i] if isinstance(key, tuple) else key
            anomalies.append(entry)
    return anomalies


def flag_sparse_history(df, min_weeks=6):
    """Separately flag products/regions that simply don't have enough
    history yet to judge normal vs. abnormal -- this is its own case,
    not something the anomaly math above should even attempt."""
    sparse = []
    for (region, product), g in df.groupby(["region", "product"]):
        if len(g) < min_weeks:
            sparse.append({
                "region": region,
                "product": product,
                "weeks_of_data": len(g),
                "note": "Not enough history to reliably judge normal vs abnormal yet."
            })
    return sparse


if __name__ == "__main__":
    import json

    print("=" * 70)
    print("STEP 2a: RECONCILING 3 SOURCES ONTO ONE WEEKLY CALENDAR")
    print("=" * 70)
    reconciled = reconcile_sources()
    print(f"Merged sales (weekly), marketing (weekly), and complaints")
    print(f"(irregular timestamps, binned to nearest week) into one table.")
    print(f"Saved data/reconciled_weekly.csv - {len(reconciled)} region-week rows.")
    print("\nSample of the reconciled table:")
    print(reconciled.head(5).to_string(index=False))

    # ---- Primary KPI: Revenue (region+product grain) - drives the rest of the pipeline ----
    print("\n" + "=" * 70)
    print("STEP 2b: ANOMALY DETECTION ACROSS 5 CONNECTED KPIs")
    print("=" * 70)

    revenue_anomalies = detect_anomalies(sales, value_col="revenue", group_cols=("region", "product"))
    print(f"\n[KPI: revenue, region+product grain] -> {len(revenue_anomalies)} anomalies found")
    for a in revenue_anomalies:
        direction = "DROPPED" if a["pct_change"] < 0 else "JUMPED"
        print(f"  {a['region']} / {a['product']} - week of {a['week']}: "
              f"revenue {direction} {abs(a['pct_change'])}% "
              f"(expected ~${a['expected_value']:,.0f}, actual ${a['actual_value']:,.0f})")

    # ---- Supporting/connected KPIs: detected but not run through full driver attribution ----
    units_anomalies = detect_anomalies(sales, value_col="units_sold", group_cols=("region", "product"))
    print(f"\n[KPI: units_sold, region+product grain] -> {len(units_anomalies)} anomalies found")
    for a in units_anomalies:
        direction = "DROPPED" if a["pct_change"] < 0 else "JUMPED"
        print(f"  {a['region']} / {a['product']} - week of {a['week']}: units {direction} {abs(a['pct_change'])}%")

    sales_with_asp = sales.copy()
    sales_with_asp["average_selling_price"] = sales_with_asp["revenue"] / sales_with_asp["units_sold"]
    asp_anomalies = detect_anomalies(sales_with_asp, value_col="average_selling_price", group_cols=("region", "product"))
    print(f"\n[KPI: average_selling_price, region+product grain] -> {len(asp_anomalies)} anomalies found")
    for a in asp_anomalies:
        direction = "DROPPED" if a["pct_change"] < 0 else "JUMPED"
        print(f"  {a['region']} / {a['product']} - week of {a['week']}: ASP {direction} {abs(a['pct_change'])}%")

    marketing_anomalies = detect_anomalies(reconciled, value_col="spend", group_cols=("region",))
    print(f"\n[KPI: marketing_spend, region grain] -> {len(marketing_anomalies)} anomalies found")
    for a in marketing_anomalies:
        direction = "DROPPED" if a["pct_change"] < 0 else "JUMPED"
        print(f"  {a['region']} - week of {a['week']}: marketing spend {direction} {abs(a['pct_change'])}%")

    complaint_anomalies = detect_anomalies(reconciled, value_col="complaint_count", group_cols=("region",),
                                            z_thresh=1.5, min_pct_impact=0)
    print(f"\n[KPI: complaint_volume, region grain] -> {len(complaint_anomalies)} anomalies found")
    for a in complaint_anomalies:
        direction = "ROSE" if a["pct_change"] > 0 else "FELL"
        print(f"  {a['region']} - week of {a['week']}: complaint volume {direction} to {a['actual_value']}")

    # ---- Sparse-history check (still revenue-based, per product+region) ----
    sparse = flag_sparse_history(sales)
    print("\n" + "=" * 70)
    print(f"FOUND {len(sparse)} PRODUCT/REGION COMBOS WITH TOO LITTLE HISTORY")
    print("=" * 70)
    for s in sparse[:5]:
        print(f"  {s['region']} / {s['product']}: only {s['weeks_of_data']} weeks of data")
    if len(sparse) > 5:
        print(f"  ...and {len(sparse)-5} more (mostly ProductC, launched recently)")

    with open("data/anomalies.json", "w") as f:
        json.dump({
            "revenue_anomalies": revenue_anomalies,   # feeds Steps 3-8 (driver attribution onward)
            "units_sold_anomalies": units_anomalies,
            "average_selling_price_anomalies": asp_anomalies,
            "marketing_spend_anomalies": marketing_anomalies,
            "complaint_volume_anomalies": complaint_anomalies,
            "sparse_history": sparse,
        }, f, indent=2)
    print(f"\nSaved results to data/anomalies.json (5 KPIs monitored across 3 reconciled sources)")
