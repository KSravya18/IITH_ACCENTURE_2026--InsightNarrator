#!/bin/bash
# Runs the full InsightNarrator pipeline end-to-end, in order.
set -e
echo "Step 1: Generating sample data..."
python3 01_generate_data.py
echo -e "\nStep 2: Detecting anomalies..."
python3 02_anomaly_detection.py
echo -e "\nStep 3: Attributing drivers..."
python3 03_driver_attribution.py
echo -e "\nStep 4: Scoring confidence..."
python3 04_confidence_scoring.py
echo -e "\nStep 5: Applying access control..."
python3 05_access_control.py
echo -e "\nStep 6: Generating persona narratives..."
python3 06_narrative_generation.py
echo -e "\nStep 7: Building action recommendations + feedback loop..."
python3 07_actions_and_feedback.py
echo -e "\nStep 8: Measuring telemetry..."
python3 08_telemetry.py
echo -e "\nDone. All outputs are in data/."
