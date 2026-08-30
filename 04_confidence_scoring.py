"""
STEP 4: Confidence Scoring & Abstention ("Are we actually sure?")
====================================================================
Goal (plain English): decide whether we have ENOUGH REAL EVIDENCE to
explain an anomaly, or whether we should honestly say "we don't know"
instead of guessing.

Important distinction (still no AI -- these are simple rules):

  - The price/volume split from Step 3 is just algebra restating the
    problem ("revenue dropped because units dropped") -- it does NOT
    count as a real explanation on its own.

  - Only EXTERNAL evidence counts as real support:
      - A marketing spend change in the same week
      - Real customer complaints in the same window

  RULE: if external evidence exists -> HIGH or MEDIUM confidence.
        if NO external evidence exists -> LOW confidence, and the
        system must say so honestly instead of inventing a reason.
"""
import json

with open("data/driver_analysis.json") as f:
    results = json.load(f)


def score_confidence(r):
    external_drivers = [d for d in r["identified_drivers"]
                         if d["driver"] in ("Marketing spend change",
                                            "Customer complaints (fulfillment/logistics)")]

    if len(external_drivers) >= 2:
        return "HIGH", "Multiple independent external signals (marketing + complaints) point the same direction."
    elif len(external_drivers) == 1:
        return "MEDIUM", "One external signal found, but not fully corroborated by a second source."
    else:
        return "LOW", "No external evidence (no marketing change, no related complaints) found for this anomaly. The mechanical price/volume split alone does not explain the root cause."


if __name__ == "__main__":
    print("=" * 70)
    print("CONFIDENCE SCORING RESULTS")
    print("=" * 70)

    for r in results:
        a = r["anomaly"]
        confidence, reason = score_confidence(r)
        r["confidence_level"] = confidence
        r["confidence_reason"] = reason

        print(f"\n{a['region']} / {a['product']} - week of {a['week']}")
        print(f"  CONFIDENCE: {confidence}")
        print(f"  Reason: {reason}")
        if confidence == "LOW":
            print(f"  ACTION: System should ABSTAIN from claiming a cause. "
                  f"Flag for manual analyst review instead.")

    with open("data/driver_analysis_scored.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to data/driver_analysis_scored.json")
