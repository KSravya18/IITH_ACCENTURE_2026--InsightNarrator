"""
InsightNarrator Round 2 - Sample Data Generator
=================================================
Generates 3 data sources with different grains/cadences, and bakes in
every required Round 2 test scenario:
  - A multi-factor KPI movement (price cut + shipping delay + lower ad spend)
  - A low-confidence / abstain scenario (unexplained anomaly, no evidence)
  - A sparse-history / newly-launched product scenario
"""
import pandas as pd
import numpy as np

np.random.seed(7)

REGIONS = ["North", "South", "East", "West"]
PRODUCTS = ["ProductA", "ProductB", "ProductC"]
WEEKS = pd.date_range("2026-01-05", periods=24, freq="W")  # 24 weeks of daily-rollup data

# -------------------------------------------------------------------
# SOURCE 1: Sales (daily grain, rolled to weekly for this demo scope)
# Fields: date, region, product, units_sold, price, revenue
# -------------------------------------------------------------------
sales_rows = []
base_price = {"ProductA": 45, "ProductB": 30, "ProductC": 60}
base_units = {"North": 900, "South": 700, "East": 850, "West": 800}

for week_idx, week in enumerate(WEEKS):
    for region in REGIONS:
        for product in PRODUCTS:
            # ProductC launched late -> sparse history scenario
            if product == "ProductC" and week_idx < 20:
                continue

            price = base_price[product] + np.random.normal(0, 1.5)
            units = base_units[region] * np.random.uniform(0.9, 1.1)

            # SCENARIO A: Multi-factor movement - West/ProductA, week 15
            # Price cut (-15%) + shipping delays (units still sell but revenue drops)
            # + reduced marketing (see source 2) all hit at once.
            if region == "West" and product == "ProductA" and week_idx == 15:
                price = price * 0.85       # price cut
                units = units * 0.80       # delays suppress fulfillment/sales

            # SCENARIO B: Low-confidence / unexplained anomaly - East/ProductB, week 10
            # A real revenue dip with NO corresponding complaint or marketing signal.
            if region == "East" and product == "ProductB" and week_idx == 10:
                units = units * 0.72

            # ProductC (sparse history): give it a soft ramp-up curve
            if product == "ProductC":
                units = units * (0.5 + 0.15 * (week_idx - 20))

            revenue = round(price * units, 2)
            sales_rows.append({
                "week": week.date().isoformat(),
                "region": region,
                "product": product,
                "units_sold": round(units),
                "price": round(price, 2),
                "revenue": revenue,
            })

sales_df = pd.DataFrame(sales_rows)
sales_df.to_csv("data/sales_weekly.csv", index=False)

# -------------------------------------------------------------------
# SOURCE 2: Marketing spend (weekly grain, per region+channel)
# Fields: week, region, channel, spend
# -------------------------------------------------------------------
mkt_rows = []
channels = ["Search", "Social", "Display"]
base_spend = {"North": 8000, "South": 6000, "East": 7000, "West": 7500}

for week_idx, week in enumerate(WEEKS):
    for region in REGIONS:
        for channel in channels:
            spend = base_spend[region] / len(channels) * np.random.uniform(0.85, 1.15)
            # Ties into Scenario A: West marketing spend cut the same week as the price cut
            if region == "West" and week_idx == 15:
                spend = spend * 0.55
            mkt_rows.append({
                "week": week.date().isoformat(),
                "region": region,
                "channel": channel,
                "spend": round(spend, 2),
            })

mkt_df = pd.DataFrame(mkt_rows)
mkt_df.to_csv("data/marketing_weekly.csv", index=False)

# -------------------------------------------------------------------
# SOURCE 3: Support/complaints log (irregular timestamps, unstructured text)
# Fields: date, region, product, customer_id, complaint_text
# -------------------------------------------------------------------
w15_date = WEEKS[15]
complaints = [
    (w15_date + pd.Timedelta(days=1), "West", "ProductA", "CUST-4471", "My ProductA order has been stuck in transit for over a week."),
    (w15_date + pd.Timedelta(days=2), "West", "ProductA", "CUST-2290", "Delivery delayed again, third time this month in the west region."),
    (w15_date + pd.Timedelta(days=2), "West", "ProductA", "CUST-8813", "Package marked shipped but tracking hasn't moved."),
    (w15_date + pd.Timedelta(days=3), "West", "ProductA", "CUST-1052", "Extremely disappointed with shipping delays, considering switching brands."),
    (w15_date + pd.Timedelta(days=4), "West", "ProductA", "CUST-9944", "Warehouse in the west region seems understaffed, orders piling up."),
    (w15_date + pd.Timedelta(days=5), "West", "ProductA", "CUST-3327", "Refund requested, late delivery missed the event I needed it for."),
    # Unrelated normal-noise complaints elsewhere, for contrast
    (WEEKS[3] + pd.Timedelta(days=1), "North", "ProductB", "CUST-5510", "Great product, fast delivery as always."),
    (WEEKS[8] + pd.Timedelta(days=2), "South", "ProductA", "CUST-7743", "App crashed at checkout, had to retry twice."),
    (WEEKS[12] + pd.Timedelta(days=1), "East", "ProductC", "CUST-6621", "Packaging could be better but arrived on time."),
    # NOTE: deliberately NO complaints near East/ProductB week 10 -> low-confidence scenario
]
comp_df = pd.DataFrame(complaints, columns=["date", "region", "product", "customer_id", "complaint_text"])
comp_df["date"] = comp_df["date"].dt.date.astype(str)
comp_df.to_csv("data/complaints_log.csv", index=False)

print("Generated 3 data sources:")
print(f"  data/sales_weekly.csv       - {len(sales_df)} rows (daily->weekly, structured)")
print(f"  data/marketing_weekly.csv   - {len(mkt_df)} rows (weekly, structured)")
print(f"  data/complaints_log.csv     - {len(comp_df)} rows (irregular, unstructured)")
print()
print("Built-in scenarios:")
print("  Scenario A (multi-factor):    West / ProductA / week index 15")
print("  Scenario B (low-confidence):  East / ProductB / week index 10")
print("  Scenario C (sparse-history):  ProductC, launched week index 20")
