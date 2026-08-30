"""
STEP 3: Driver Attribution ("Why did this happen?")
======================================================
Goal (plain English): for each problem week we found in Step 2,
figure out WHY it happened by checking two things:

  1. PRICE vs VOLUME split (pure math):
     Revenue = Price x Units Sold. If revenue drops, was it because
     the PRICE dropped, or because FEWER UNITS sold, or both?
     This alone tells us a lot before we even look at other data.

  2. Related evidence from marketing + complaints (pure math/matching,
     still no AI): did marketing spend drop that same week? Did
     customer complaints spike that same week?

Still NO AI in this step. This is deterministic math + keyword
matching. The AI's only job later will be to describe these findings
in plain English -- not to invent them.
"""
import pandas as pd
import numpy as np
import json
from datetime import timedelta

sales = pd.read_csv("data/sales_weekly.csv")
sales["week"] = pd.to_datetime(sales["week"])
marketing = pd.read_csv("data/marketing_weekly.csv")
marketing["week"] = pd.to_datetime(marketing["week"])
complaints = pd.read_csv("data/complaints_log.csv")
complaints["date"] = pd.to_datetime(complaints["date"])

with open("data/anomalies.json") as f:
    anomaly_data = json.load(f)

NEGATIVE_KEYWORDS = ["delay", "delayed", "stuck", "late", "understaffed",
                     "refund", "disappointed", "crashed", "missing", "damaged"]


def price_volume_split(region, product, week_str):
    """Pure math: how much of the revenue change came from price
    changing vs. how much came from units sold changing."""
    g = sales[(sales["region"] == region) & (sales["product"] == product)].sort_values("week")
    week = pd.to_datetime(week_str)

    this_week = g[g["week"] == week].iloc[0]
    baseline = g[g["week"] < week].tail(6)  # prior 6 weeks as "normal"
    baseline_price = baseline["price"].mean()
    baseline_units = baseline["units_sold"].mean()

    price_effect = (this_week["price"] - baseline_price) * baseline_units
    volume_effect = (this_week["units_sold"] - baseline_units) * baseline_price
    total_change = this_week["revenue"] - (baseline_price * baseline_units)

    return {
        "price_effect_dollars": round(price_effect, 2),
        "volume_effect_dollars": round(volume_effect, 2),
        "total_change_dollars": round(total_change, 2),
        "price_pct_of_drop": round(100 * price_effect / total_change, 1) if total_change != 0 else 0,
        "volume_pct_of_drop": round(100 * volume_effect / total_change, 1) if total_change != 0 else 0,
    }


def marketing_signal(region, week_str):
    """Did marketing spend for this region drop unusually that week?"""
    g = marketing[marketing["region"] == region].groupby("week")["spend"].sum().reset_index()
    g = g.sort_values("week")
    week = pd.to_datetime(week_str)

    this_week = g[g["week"] == week]
    baseline = g[g["week"] < week].tail(6)["spend"].mean()

    if this_week.empty or pd.isna(baseline):
        return None

    actual = this_week["spend"].values[0]
    pct_change = round(100 * (actual - baseline) / baseline, 1)

    if abs(pct_change) > 15:  # meaningful marketing change
        return {"pct_change": pct_change, "baseline_spend": round(baseline, 2), "actual_spend": round(actual, 2)}
    return None


def complaint_signal(region, product, week_str, days_window=10):
    """Are there related customer complaints in the same window?"""
    week = pd.to_datetime(week_str)
    window_start = week - timedelta(days=days_window)
    window_end = week + timedelta(days=days_window)

    relevant = complaints[
        (complaints["region"] == region) &
        (complaints["product"] == product) &
        (complaints["date"] >= window_start) &
        (complaints["date"] <= window_end)
    ]

    tagged = []
    for _, row in relevant.iterrows():
        hits = [kw for kw in NEGATIVE_KEYWORDS if kw in row["complaint_text"].lower()]
        if hits:
            tagged.append({"text": row["complaint_text"], "keywords": hits})
    return tagged


def analyze_anomaly(a):
    pv = price_volume_split(a["region"], a["product"], a["week"])
    mkt = marketing_signal(a["region"], a["week"])
    complaints_found = complaint_signal(a["region"], a["product"], a["week"])

    drivers = []
    if abs(pv["price_pct_of_drop"]) > 20:
        drivers.append({"driver": "Price change", "evidence_strength": "high (direct calculation)",
                         "detail": f"Price changes account for {pv['price_pct_of_drop']}% of the revenue movement."})
    if abs(pv["volume_pct_of_drop"]) > 20:
        drivers.append({"driver": "Units sold change", "evidence_strength": "high (direct calculation)",
                         "detail": f"Units sold changes account for {pv['volume_pct_of_drop']}% of the revenue movement."})
    if mkt:
        drivers.append({"driver": "Marketing spend change", "evidence_strength": "medium (correlated timing)",
                         "detail": f"Marketing spend changed {mkt['pct_change']}% the same week."})
    if complaints_found:
        drivers.append({"driver": "Customer complaints (fulfillment/logistics)", "evidence_strength": "medium (correlated timing)",
                         "detail": f"{len(complaints_found)} related complaints found in the same window."})

    return {
        "anomaly": a,
        "price_volume_split": pv,
        "marketing_signal": mkt,
        "complaint_evidence": complaints_found,
        "identified_drivers": drivers,
        "evidence_count": len(drivers),
    }


if __name__ == "__main__":
    results = [analyze_anomaly(a) for a in anomaly_data["revenue_anomalies"]]

    print("=" * 70)
    print("DRIVER ATTRIBUTION RESULTS")
    print("=" * 70)
    for r in results:
        a = r["anomaly"]
        print(f"\n{a['region']} / {a['product']} - week of {a['week']} ({a['pct_change']}% change)")
        print(f"  Price vs Volume split: price contributed {r['price_volume_split']['price_pct_of_drop']}%, "
              f"volume contributed {r['price_volume_split']['volume_pct_of_drop']}%")
        if r["identified_drivers"]:
            print(f"  Found {len(r['identified_drivers'])} supporting driver(s):")
            for d in r["identified_drivers"]:
                print(f"    - {d['driver']}: {d['detail']}")
        else:
            print(f"  NO supporting evidence found -> this should be a LOW-CONFIDENCE case")

    with open("data/driver_analysis.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to data/driver_analysis.json")
