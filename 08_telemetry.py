"""
STEP 9: Telemetry ("How fast and how expensive is this, really?")
====================================================================
Goal (plain English): Accenture specifically asked us to prove this
system is practical to actually run -- not just theoretically clever.
So we measure, for the whole pipeline:
  - How long each stage takes (latency)
  - How many times we'd call the AI (LLM calls)
  - Roughly how many "tokens" (chunks of text) the AI would process
  - Roughly what that would cost in real money

NOTE: cost-per-token figures below are illustrative placeholders for
sizing purposes, not a live pricing lookup -- worth saying so out loud
if a judge asks, and swapping in the real current rate before submission.
"""
import time
import json

# Illustrative LLM pricing assumption (USD per million tokens) - STATE THIS ASSUMPTION OUT LOUD IN THE PITCH
ILLUSTRATIVE_INPUT_COST_PER_M = 3.00
ILLUSTRATIVE_OUTPUT_COST_PER_M = 15.00

def estimate_tokens(text):
    """Rough rule of thumb: ~4 characters per token for English text."""
    return max(1, len(text) // 4)


def run_full_pipeline_with_telemetry():
    telemetry = {"stages": [], "llm_calls": []}

    # --- Stage: Anomaly Detection ---
    t0 = time.perf_counter()
    import importlib
    anomaly_mod = importlib.import_module("02_anomaly_detection".replace("0", "_", 0)) if False else None
    # (re-running via exec of the actual scripts to get REAL wall-clock timing)
    exec(open("02_anomaly_detection.py").read(), {"__name__": "__telemetry__"})
    t1 = time.perf_counter()
    telemetry["stages"].append({"stage": "Anomaly Detection (stats)", "latency_ms": round((t1 - t0) * 1000, 1)})

    # --- Stage: Driver Attribution ---
    t0 = time.perf_counter()
    exec(open("03_driver_attribution.py").read(), {"__name__": "__telemetry__"})
    t1 = time.perf_counter()
    telemetry["stages"].append({"stage": "Driver Attribution (stats/math)", "latency_ms": round((t1 - t0) * 1000, 1)})

    # --- Stage: Confidence Scoring ---
    t0 = time.perf_counter()
    exec(open("04_confidence_scoring.py").read(), {"__name__": "__telemetry__"})
    t1 = time.perf_counter()
    telemetry["stages"].append({"stage": "Confidence Scoring (rules)", "latency_ms": round((t1 - t0) * 1000, 1)})

    # --- Stage: Access Control ---
    t0 = time.perf_counter()
    exec(open("05_access_control.py").read(), {"__name__": "__telemetry__"})
    t1 = time.perf_counter()
    telemetry["stages"].append({"stage": "Access Control (rules)", "latency_ms": round((t1 - t0) * 1000, 1)})

    # --- Stage: Narrative Generation (this is the LLM stage) ---
    with open("data/access_control_demo.json") as f:
        persona_views = json.load(f)

    import importlib.util
    spec = importlib.util.spec_from_file_location("narrative_mod", "06_narrative_generation.py")
    narrative_mod = importlib.util.module_from_spec(spec)
    # avoid re-running its __main__ block; just grab the function
    with open("06_narrative_generation.py") as f:
        code = f.read().split('if __name__ == "__main__":')[0]
    ns = {}
    exec(code, ns)
    generate_narrative = ns["generate_narrative"]

    t0 = time.perf_counter()
    for persona_key, view in [
        ("executive", persona_views["executive_view"]),
        ("regional_manager", persona_views["regional_manager_view_west"]),
        ("support_lead", persona_views["support_lead_view"]),
    ]:
        prompt_text = json.dumps(view)  # what we'd actually send to the LLM
        narrative = generate_narrative(view, persona_key)

        input_tokens = estimate_tokens(prompt_text) + 80  # + instructions overhead
        output_tokens = estimate_tokens(narrative)
        cost = (input_tokens / 1_000_000 * ILLUSTRATIVE_INPUT_COST_PER_M) + \
               (output_tokens / 1_000_000 * ILLUSTRATIVE_OUTPUT_COST_PER_M)

        telemetry["llm_calls"].append({
            "persona": persona_key,
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "estimated_cost_usd": round(cost, 6),
        })
    t1 = time.perf_counter()
    telemetry["stages"].append({"stage": "Narrative Generation (LLM)", "latency_ms": round((t1 - t0) * 1000, 1)})

    return telemetry


if __name__ == "__main__":
    import io, contextlib
    # Suppress the print() spam from re-running the earlier scripts
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        telemetry = run_full_pipeline_with_telemetry()

    total_latency = sum(s["latency_ms"] for s in telemetry["stages"])
    total_cost = sum(c["estimated_cost_usd"] for c in telemetry["llm_calls"])
    total_calls = len(telemetry["llm_calls"])

    print("=" * 70)
    print("TELEMETRY REPORT")
    print("=" * 70)
    print("\nPer-stage latency:")
    for s in telemetry["stages"]:
        print(f"  {s['stage']:<35} {s['latency_ms']:>8} ms")
    print(f"  {'TOTAL':<35} {total_latency:>8.1f} ms")

    print(f"\nLLM usage ({total_calls} calls -- one per persona narrative):")
    for c in telemetry["llm_calls"]:
        print(f"  {c['persona']:<20} in={c['estimated_input_tokens']:>4} tok  "
              f"out={c['estimated_output_tokens']:>3} tok  cost=${c['estimated_cost_usd']:.6f}")

    print(f"\nTOTAL estimated cost for this one insight (3 persona narratives): ${total_cost:.6f}")
    print(f"Estimated cost per insight-narrative: ${total_cost/total_calls:.6f}")
    print(f"\n(Non-LLM stages: {total_latency - telemetry['stages'][-1]['latency_ms']:.1f} ms of the "
          f"{total_latency:.1f} ms total came from plain math/rules, not AI.)")

    with open("data/telemetry_report.json", "w") as f:
        json.dump(telemetry, f, indent=2)
    print(f"\nSaved to data/telemetry_report.json")
