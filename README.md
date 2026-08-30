# InsightNarrator

**An AI-powered KPI intelligence-to-action engine.**
Accenture Innovation Challenge 2026 — Round 2 Prototype
Team: IITH_ACCENTURE_2026 | Problem Track 3: BusinessIntelligence.ai

---

## What this is

Most business dashboards can tell you *that* a KPI changed — revenue dropped
8%, for example — but not *why*. Finding the real cause today usually means
an analyst manually digging through separate data sources for days.

**InsightNarrator** automatically detects meaningful KPI movements, cross-references
structured data (sales, marketing spend) and unstructured data (customer
complaints), identifies the most likely drivers using statistics — not
guesswork — and generates a plain-language explanation and recommended
action, tailored to who's asking (an executive, a regional manager, or a
support lead). When there isn't enough evidence to explain a change, it
says so honestly instead of inventing a cause.

## Why this matters — the core design principle

**The LLM is never the source of quantitative truth in this system.**
All detection, math, and decision logic run on deterministic code and
statistics. The LLM's only job is to turn already-verified structured
facts into natural-language sentences for different audiences. This
directly follows Accenture's Round 2 guidance that "the LLM should not
be treated as the source of quantitative truth."

| Stage | What it does | Technology used |
|---|---|---|
| 1. Data generation | Simulates 3 realistic data sources | Pandas (no AI) |
| 2. Anomaly detection | Flags real KPI movements vs. normal noise | Rolling z-score statistics (no AI) |
| 3. Driver attribution | Price/volume decomposition + correlates marketing & complaints | Deterministic math + keyword matching (no AI) |
| 4. Confidence scoring | Decides if there's enough real evidence to explain a change | Rule-based logic (no AI) |
| 5. Semantic contract | Defines every KPI's formula, owner, and access rules | Config file (no AI) |
| 6. Access control | Enforces who can see what, per persona | Rule-based permission logic (no AI) |
| 7. Narrative generation | Writes the explanation in plain language, per persona | **LLM** (Claude API, with offline template fallback) |
| 8. Action recommendations | Maps each driver to a concrete business action | Lookup table (no AI) |
| 9. Feedback loop | Lets an analyst's correction improve future detection | Logged + keyword-list update (no AI) |
| 10. Telemetry | Measures latency, token usage, and estimated cost | Instrumentation (no AI) |

## Project structure

```
insight_narrator_r2/
├── README.md                      <- you are here
├── requirements.txt
├── run_all.sh                     <- runs the full pipeline end-to-end
├── config/
│   ├── semantic_contract.yaml     <- KPI definitions, thresholds, access rules
│   └── learned_keywords.json      <- grows via the feedback loop
├── data/                          <- generated sample data + all pipeline outputs
│   ├── sales_weekly.csv
│   ├── marketing_weekly.csv
│   ├── complaints_log.csv
│   └── *.json                     <- results from each pipeline stage
├── 01_generate_data.py
├── 02_anomaly_detection.py
├── 03_driver_attribution.py
├── 04_confidence_scoring.py
├── 05_access_control.py
├── 06_narrative_generation.py
├── 07_actions_and_feedback.py
└── 08_telemetry.py
```

## How to run it

```bash
pip install -r requirements.txt
./run_all.sh
```

This regenerates the sample data and runs all 8 pipeline stages in order,
printing results at each step and saving JSON outputs to `data/`.

**To use the real LLM instead of the offline template**, set your API key
before running:
```bash
export ANTHROPIC_API_KEY=your_key_here
./run_all.sh
```
Without a key set, Step 7 automatically falls back to a rule-based
template so the whole pipeline still runs end-to-end for grading/demo
purposes without requiring an API key.

## Built-in test scenarios (mapped to Round 2's minimum requirements)

| Requirement | Scenario in this prototype |
|---|---|
| 3–5 KPIs across 2–3 sources, different grains | **5 KPIs actively monitored**: revenue, units sold, average selling price (all region+product grain, from sales), marketing spend (region grain, weekly), and complaint volume (region grain, irregular→weekly-binned). See `02_anomaly_detection.py`. |
| Data reconciliation across heterogeneous sources | `reconcile_sources()` in `02_anomaly_detection.py` explicitly merges sales (weekly), marketing (weekly), and complaints (irregular timestamps, binned to the nearest week) into one `data/reconciled_weekly.csv` table before analysis. |
| Semantic/KPI contract | `config/semantic_contract.yaml` |
| 2+ personas, different narratives | Executive, Regional Manager, Support Lead (see `06_narrative_generation.py`) |
| Multi-factor KPI movement | West/ProductA, week of 2026-04-26 — price cut + reduced marketing + shipping-delay complaints, all at once, corroborated across 4 of the 5 monitored KPIs simultaneously |
| Low-confidence / abstention case | East/ProductB, week of 2026-03-22 — real anomaly, zero supporting evidence, system explicitly abstains |
| Sparse-history KPI | West/ProductC — only 4 weeks of data. Flows through the **full pipeline**: detected in Step 2, given a persona-specific narrative in Step 6, and a monitoring-only action recommendation in Step 7 — not just flagged and dropped. |
| Role-based security scenario | Regional Manager scoped to their own region only (denied test included in `05_access_control.py`); raw complaint text/customer IDs restricted to Support Lead persona |
| Evidence & lineage | Every insight traces back to its source file, method, and confidence level |
| LLM vs. non-LLM breakdown | See table above and inline comments in each script |
| Runtime telemetry | `08_telemetry.py` — latency, token estimates, cost estimates per insight |

## Feedback loop example (already run once in this repo)

`data/feedback_log.csv` contains a logged example: an analyst reviewing
the East/ProductB low-confidence case discovers the real cause (an internal
warehouse system migration) that wasn't visible in the complaints data.
That correction is logged, and `config/learned_keywords.json` is
automatically updated so similar future complaints are caught without
retraining any model.

## Known limitations & honest caveats

- **Sample data, not real enterprise data** — as explicitly permitted by
  the Round 2 brief, all data here is simulated to demonstrate the
  mechanism, not sourced from a real company.
- **Correlation, not proven causation** — the driver attribution finds
  *plausible* explanations backed by timing correlation; it does not
  claim certainty, and the confidence-scoring layer exists specifically
  to communicate that distinction to users.
- **Offline LLM fallback** — narrative generation defaults to a
  rule-based template unless an API key is provided, so the prototype
  can be graded without requiring credentials.
- **Cost/latency figures are illustrative** — token pricing used in
  `08_telemetry.py` is a placeholder for sizing purposes and should be
  replaced with live pricing before any production estimate.
- **Keyword-based complaint matching is simple by design** — a
  production version would likely use semantic/embedding-based matching
  instead of literal keyword lists for better recall.

## Team

IITH_ACCENTURE_2026 — G Sai Charan
                      K Sravya
