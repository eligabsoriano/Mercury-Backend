# Mercury ML Pipeline Plan

## Goal

Build reproducible RFM segmentation and churn prediction workflows.

## Steps

1. Define the prediction target, observation window, and evaluation horizon.
2. Implement feature generation from time-bounded customer history.
3. Establish a simple baseline before training classifiers.
4. Split data without temporal leakage and record class balance.
5. Evaluate precision, recall, calibration, and revenue-at-risk impact.
6. Version preprocessing, model artifacts, feature definitions, and metrics.
7. Expose a stable inference output for FastAPI.

## Guardrails

Keep exploratory notebooks separate from reusable production code. Never train or validate with future information.