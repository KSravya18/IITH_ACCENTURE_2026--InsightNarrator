"""
STEP 6: Role-Based Access Control ("Who's allowed to see what?")
====================================================================
Goal (plain English): take the rulebook from Step 5 (semantic_contract.yaml)
and actually ENFORCE it in code. Different job roles (personas) should
see different amounts of detail about the same finding.

Example: a Regional Manager for the West region should:
  - See West region's findings in full
  - NOT see East region's findings at all
  - See complaint THEMES (like "shipping delay") but NOT the raw
    customer complaint text or customer ID (that's private/sensitive)

A Support Lead, on the other hand, is allowed to see raw complaint
text and customer IDs, because that's their job.

Still NO AI in this step -- this is just permission-checking logic.
"""
import json
import yaml
import pandas as pd

with open("config/semantic_contract.yaml") as f:
    contract = yaml.safe_load(f)

with open("data/driver_analysis_scored.json") as f:
    results = json.load(f)

complaints_raw = pd.read_csv("data/complaints_log.csv")


def enrich_with_customer_id(complaint_evidence):
    """Match complaint text back to the raw log to pull customer_id
    (kept separate from Step 3 on purpose, since customer_id is
    sensitive and shouldn't flow through the general pipeline by default)."""
    enriched = []
    for c in complaint_evidence:
        match = complaints_raw[complaints_raw["complaint_text"] == c["text"]]
        customer_id = match["customer_id"].values[0] if not match.empty else "UNKNOWN"
        enriched.append({**c, "customer_id": customer_id})
    return enriched


def view_for_persona(anomaly_result, persona, requesting_region=None):
    """Returns what a given persona is allowed to see for one anomaly."""
    a = anomaly_result["anomaly"]

    # --- Regional manager: region lock ---
    if persona == "regional_manager":
        if requesting_region and a["region"] != requesting_region:
            return {"access": "DENIED",
                    "reason": f"Regional managers cannot view {a['region']} data "
                              f"(you are scoped to {requesting_region} only)."}

    complaints_enriched = enrich_with_customer_id(anomaly_result["complaint_evidence"])

    base_view = {
        "region": a["region"],
        "product": a["product"],
        "week": a["week"],
        "pct_change": a["pct_change"],
        "confidence_level": anomaly_result["confidence_level"],
    }

    if persona == "executive":
        # Aggregated framing, no raw complaint text/IDs, hide low-confidence noise by default
        if anomaly_result["confidence_level"] == "LOW":
            base_view["summary"] = "Anomaly detected but under investigation - not yet explainable."
        else:
            base_view["summary"] = f"Revenue impact explained by: " + \
                ", ".join(d["driver"] for d in anomaly_result["identified_drivers"])
        base_view["access"] = "GRANTED (executive view - aggregated, no raw customer data)"
        return base_view

    elif persona == "regional_manager":
        base_view["drivers"] = [d["driver"] for d in anomaly_result["identified_drivers"]]
        base_view["complaint_themes"] = list(set(
            kw for c in complaints_enriched for kw in c["keywords"]
        ))
        base_view["complaint_count"] = len(complaints_enriched)
        base_view["access"] = "GRANTED (regional view - themes only, no raw text/customer ID)"
        return base_view

    elif persona == "support_lead":
        base_view["drivers"] = [d["driver"] for d in anomaly_result["identified_drivers"]]
        base_view["raw_complaints"] = complaints_enriched  # full text + customer_id
        base_view["access"] = "GRANTED (support lead view - full complaint detail)"
        return base_view

    return {"access": "DENIED", "reason": "Unknown persona"}


if __name__ == "__main__":
    # Pick the West/ProductA high-confidence anomaly to demo all 3 personas
    target = next(r for r in results if r["anomaly"]["region"] == "West"
                  and r["anomaly"]["week"] == "2026-04-26")

    print("=" * 70)
    print("SAME FINDING, VIEWED BY 3 DIFFERENT PERSONAS")
    print("=" * 70)

    for persona in ["executive", "regional_manager", "support_lead"]:
        # Regional manager is scoped to West -> should be GRANTED for this one
        view = view_for_persona(target, persona, requesting_region="West")
        print(f"\n--- {persona.upper()} ---")
        print(json.dumps(view, indent=2))

    print("\n" + "=" * 70)
    print("ACCESS DENIED TEST: an East-scoped regional manager requests West data")
    print("=" * 70)
    denied_view = view_for_persona(target, "regional_manager", requesting_region="East")
    print(json.dumps(denied_view, indent=2))

    with open("data/access_control_demo.json", "w") as f:
        json.dump({
            "executive_view": view_for_persona(target, "executive"),
            "regional_manager_view_west": view_for_persona(target, "regional_manager", "West"),
            "regional_manager_view_denied": view_for_persona(target, "regional_manager", "East"),
            "support_lead_view": view_for_persona(target, "support_lead"),
        }, f, indent=2)
    print(f"\nSaved to data/access_control_demo.json")
