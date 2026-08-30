"""
STEP 8: Action Recommendations + Feedback Loop
====================================================================
Part A - Action Recommendations (still NO AI, just a lookup table):
Goal (plain English): once we know WHY something happened, turn that
into a concrete "what should someone actually do" recommendation,
in the exact format Accenture asked for:
   driver -> controllable lever -> action -> expected impact
   -> owner -> confidence -> monitoring plan

Part B - Feedback Loop:
Goal (plain English): when a human analyst reviews a LOW-confidence
case and figures out the real answer, the system should "remember"
that correction so it can catch similar cases automatically next time
-- instead of making the same "I don't know" mistake forever.
"""
import json
import csv
import os

with open("data/driver_analysis_scored.json") as f:
    results = json.load(f)

# ------------------------------------------------------------------
# PART A: Driver -> Lever -> Action lookup table
# ------------------------------------------------------------------
LEVER_MAPPING = {
    "Price change": {
        "lever": "Pricing strategy",
        "action": "Review the recent price change against competitor pricing and demand sensitivity; consider reverting if volume loss outweighs the price gain.",
        "owner": "Pricing Team",
        "monitoring_plan": "Track units sold vs. price weekly for the next 4 weeks to confirm demand response.",
    },
    "Units sold change": {
        "lever": "Demand & fulfillment capacity",
        "action": "Check inventory availability and fulfillment capacity for this product/region during the affected week.",
        "owner": "Operations Team",
        "monitoring_plan": "Track units sold weekly until back within normal range.",
    },
    "Marketing spend change": {
        "lever": "Marketing budget allocation",
        "action": "Restore marketing spend to baseline for this region and monitor whether revenue recovers accordingly.",
        "owner": "Marketing Lead",
        "monitoring_plan": "Track spend vs. revenue correlation weekly for 4 weeks.",
    },
    "Customer complaints (fulfillment/logistics)": {
        "lever": "Logistics / warehouse operations",
        "action": "Audit the regional warehouse or shipping partner's performance; proactively contact affected customers with delivery updates or compensation.",
        "owner": "Customer Support Lead",
        "monitoring_plan": "Track complaint volume weekly until the cluster resolves.",
    },
}

LOW_CONFIDENCE_ACTION = {
    "lever": "Manual investigation",
    "action": "Flag for analyst review. Do not take corrective action until a root cause is confirmed with real evidence.",
    "owner": "Data & Analytics Team",
    "monitoring_plan": "Re-evaluate next week once more data or complaint signals may have appeared.",
}

SPARSE_HISTORY_ACTION = {
    "lever": "Baseline monitoring (no action lever yet)",
    "action": "Continue passive monitoring. Do not apply standard anomaly thresholds until enough history "
              "exists to establish a reliable baseline (typically 6+ weeks).",
    "owner": "Data & Analytics Team",
    "monitoring_plan": "Re-check weekly; begin normal anomaly detection once 6 weeks of history is reached.",
}


def build_sparse_history_recommendation(sparse_entry):
    return [{
        "driver": "Insufficient history (new product/region combination)",
        **SPARSE_HISTORY_ACTION,
        "expected_impact": "N/A - not yet enough data to assess impact",
        "confidence": "N/A (monitoring only)",
    }]


def build_recommendations(anomaly_result):
    a = anomaly_result["anomaly"]
    confidence = anomaly_result["confidence_level"]

    if confidence == "LOW":
        return [{
            "driver": "Unknown (insufficient evidence)",
            **LOW_CONFIDENCE_ACTION,
            "expected_impact": "N/A - cause not yet confirmed",
            "confidence": confidence,
        }]

    recs = []
    for d in anomaly_result["identified_drivers"]:
        driver_name = d["driver"]
        if driver_name in LEVER_MAPPING:
            rec = {"driver": driver_name, **LEVER_MAPPING[driver_name],
                   "expected_impact": f"Addressing this could recover part of the {abs(a['pct_change'])}% revenue movement.",
                   "confidence": confidence}
            recs.append(rec)
    return recs


# ------------------------------------------------------------------
# PART B: Feedback loop
# ------------------------------------------------------------------
FEEDBACK_LOG = "data/feedback_log.csv"
KEYWORD_CONFIG = "config/learned_keywords.json"

def log_analyst_feedback(region, product, week, analyst_correction, new_keywords=None):
    """An analyst reviews a LOW-confidence case and tells the system
    what actually happened. We log it AND update our keyword list so
    similar future complaints get caught automatically."""
    file_exists = os.path.exists(FEEDBACK_LOG)
    with open(FEEDBACK_LOG, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["region", "product", "week", "analyst_correction", "keywords_added"])
        writer.writerow([region, product, week, analyst_correction, ";".join(new_keywords or [])])

    if new_keywords:
        existing = []
        if os.path.exists(KEYWORD_CONFIG):
            with open(KEYWORD_CONFIG) as f:
                existing = json.load(f)["learned_keywords"]
        updated = sorted(set(existing + new_keywords))
        with open(KEYWORD_CONFIG, "w") as f:
            json.dump({"learned_keywords": updated}, f, indent=2)
        return updated
    return None


if __name__ == "__main__":
    print("=" * 70)
    print("PART A: ACTION RECOMMENDATIONS")
    print("=" * 70)
    for r in results:
        a = r["anomaly"]
        recs = build_recommendations(r)
        print(f"\n{a['region']} / {a['product']} - week of {a['week']} ({r['confidence_level']} confidence)")
        for rec in recs:
            print(f"  Driver: {rec['driver']}")
            print(f"    Lever: {rec['lever']}")
            print(f"    Action: {rec['action']}")
            print(f"    Owner: {rec['owner']}  |  Monitoring: {rec['monitoring_plan']}")

    print("\n" + "=" * 70)
    print("SPARSE-HISTORY CASE: ACTION RECOMMENDATION")
    print("=" * 70)
    with open("data/anomalies.json") as f:
        anomaly_data = json.load(f)
    sparse_example = next(s for s in anomaly_data["sparse_history"] if s["region"] == "West")
    print(f"\n{sparse_example['region']} / {sparse_example['product']} ({sparse_example['weeks_of_data']} weeks of data)")
    for rec in build_sparse_history_recommendation(sparse_example):
        print(f"  Driver: {rec['driver']}")
        print(f"    Lever: {rec['lever']}")
        print(f"    Action: {rec['action']}")
        print(f"    Owner: {rec['owner']}  |  Monitoring: {rec['monitoring_plan']}")

    print("\n" + "=" * 70)
    print("PART B: FEEDBACK LOOP DEMO")
    print("=" * 70)
    print("\nScenario: an analyst manually investigates the East/ProductB LOW-confidence")
    print("case and discovers the real cause wasn't in our complaints data at all --")
    print("it was an internal warehouse system migration that briefly halted fulfillment.\n")

    updated_keywords = log_analyst_feedback(
        region="East", product="ProductB", week="2026-03-22",
        analyst_correction="Root cause was an internal warehouse system migration causing a temporary fulfillment halt. Not visible in customer complaints since customers weren't told the reason.",
        new_keywords=["system migration", "fulfillment halt", "warehouse migration"]
    )
    print(f"Logged feedback to {FEEDBACK_LOG}")
    print(f"System's keyword detection list updated to also catch: {updated_keywords}")
    print("\nNext time a similar situation produces complaint text mentioning these terms,")
    print("Step 3's evidence-matching will catch it automatically -- the system just got smarter")
    print("from ONE human correction, without needing to retrain any model.")
