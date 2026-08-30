"""
STEP 7: Persona Narrative Generation ("Turn numbers into words")
====================================================================
Goal (plain English): this is the ONLY step where AI (an LLM) is
used. Its job is strictly to WRITE about facts we already calculated
in Steps 2-4 -- it is never allowed to invent a number, a cause, or
a confidence level on its own. Everything the AI writes must trace
back to something already in our structured data.

Different personas get different writing styles:
  - Executive: 2 sentences, money-focused, no jargon
  - Regional Manager: a short paragraph with drivers and themes
  - Support Lead: operational detail, references complaint patterns

If a finding is LOW confidence, the AI is instructed to say so
honestly -- never to smooth over uncertainty with a confident-sounding
guess.
"""
import json
import os

with open("data/access_control_demo.json") as f:
    persona_views = json.load(f)


def generate_narrative(view, persona):
    """
    ** This is the function that would call the real Claude API. **
    If ANTHROPIC_API_KEY is set, it calls the real API with a strict
    prompt. Otherwise it falls back to a template so this still runs
    for grading/demo without needing an API key.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _generate_via_claude(view, persona)
    else:
        return _generate_via_template(view, persona)


def _generate_via_claude(view, persona):
    import anthropic
    client = anthropic.Anthropic()

    style_instructions = {
        "executive": "Write exactly 2 short sentences. Focus on financial impact and the bottom line. No jargon.",
        "regional_manager": "Write one short paragraph (3-4 sentences). Mention specific drivers and complaint themes so they know what to act on.",
        "support_lead": "Write 2-3 sentences focused on the operational/fulfillment angle, since this persona owns customer support outcomes.",
    }

    facts = json.dumps(view, indent=2)
    prompt = f"""Here are pre-calculated facts about a business KPI change. Do NOT invent
any numbers, causes, or confidence levels beyond what's given below.

FACTS:
{facts}

Instructions: {style_instructions[persona]}
If confidence_level is LOW, you MUST say explicitly that the cause is not yet
confirmed and this needs manual review -- do not guess a reason."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=250,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def _generate_via_template(view, persona):
    """Offline fallback -- rule-based sentence construction from the
    same structured facts, so the demo runs without an API key."""
    region, product, week = view["region"], view["product"], view["week"]
    pct = abs(view["pct_change"])
    direction = "dropped" if view["pct_change"] < 0 else "grew"
    confidence = view["confidence_level"]

    if confidence == "LOW":
        if persona == "executive":
            return (f"{region} {product} revenue {direction} {pct}% for the week of {week}. "
                    f"The cause is not yet confirmed and is flagged for analyst review before any action is taken.")
        else:
            return (f"{region} {product} revenue {direction} {pct}% for the week of {week}, but no "
                    f"related marketing changes or customer complaints were found in the same window. "
                    f"This has been flagged as low-confidence -- please do not assume a specific cause "
                    f"until a manual review is completed.")

    # HIGH / MEDIUM confidence
    drivers = view.get("drivers", [])
    driver_text = ", ".join(d.lower() for d in drivers) if drivers else "multiple factors"

    if persona == "executive":
        return (f"{region} {product} revenue {direction} {pct}% for the week of {week}, "
                f"driven by {driver_text}. Confidence in this explanation is {confidence.lower()}.")

    elif persona == "regional_manager":
        themes = view.get("complaint_themes", [])
        theme_text = f" Related customer complaints mentioned: {', '.join(themes)}." if themes else ""
        return (f"{region} {product} revenue {direction} {pct}% for the week of {week}. "
                f"This appears to be driven by {driver_text}.{theme_text} "
                f"Confidence level: {confidence}.")

    elif persona == "support_lead":
        count = view.get("complaint_count", len(view.get("raw_complaints", [])))
        return (f"{region} {product} saw revenue {direction} {pct}% "
                f"for the week of {week}, coinciding with {count} related support complaints. "
                f"This points to a fulfillment/operations issue worth investigating on the ops side.")

    return "No narrative template available for this persona."


if __name__ == "__main__":
    print("=" * 70)
    print("PERSONA-SPECIFIC NARRATIVES FOR THE SAME FINDING")
    print("=" * 70)

    for persona_key, view in [
        ("executive", persona_views["executive_view"]),
        ("regional_manager", persona_views["regional_manager_view_west"]),
        ("support_lead", persona_views["support_lead_view"]),
    ]:
        narrative = generate_narrative(view, persona_key)
        print(f"\n--- {persona_key.upper()} sees ---")
        print(narrative)

    # Also demonstrate the LOW-confidence honest narrative using East/ProductB
    with open("data/driver_analysis_scored.json") as f:
        scored = json.load(f)
    low_conf = next(r for r in scored if r["confidence_level"] == "LOW"
                    and r["anomaly"]["region"] == "East")
    low_conf_view = {
        "region": low_conf["anomaly"]["region"],
        "product": low_conf["anomaly"]["product"],
        "week": low_conf["anomaly"]["week"],
        "pct_change": low_conf["anomaly"]["pct_change"],
        "confidence_level": low_conf["confidence_level"],
    }
    print(f"\n--- LOW-CONFIDENCE CASE (executive view) ---")
    print(generate_narrative(low_conf_view, "executive"))

    # -----------------------------------------------------------------
    # SPARSE-HISTORY CASE: ProductC has too little history to anomaly-
    # score. This still needs to reach the persona, just with a
    # different message: "still building a baseline," not "no cause
    # found." Demonstrates this case flows through the FULL pipeline,
    # not just the detection step.
    # -----------------------------------------------------------------
    with open("data/anomalies.json") as f:
        anomaly_data = json.load(f)
    sparse_example = next(s for s in anomaly_data["sparse_history"] if s["region"] == "West")

    def generate_sparse_history_narrative(sparse, persona):
        weeks = sparse["weeks_of_data"]
        region, product = sparse["region"], sparse["product"]
        if persona == "executive":
            return (f"{region} {product} is newly launched with only {weeks} weeks of sales history. "
                    f"No performance judgment is being made yet -- flagged for baseline monitoring, not anomaly detection.")
        elif persona == "regional_manager":
            return (f"{region} {product} has only {weeks} weeks of data so far, which isn't enough to tell normal "
                    f"performance from a real problem. We're tracking it but won't raise anomaly alerts until "
                    f"it has a longer history (typically 6+ weeks).")
        else:
            return (f"{region} {product}: {weeks} weeks of history logged. Insufficient for statistical baselining; "
                    f"continue routine monitoring, no action required yet.")

    print(f"\n--- SPARSE-HISTORY CASE ({sparse_example['region']}/{sparse_example['product']}, executive view) ---")
    print(generate_sparse_history_narrative(sparse_example, "executive"))
