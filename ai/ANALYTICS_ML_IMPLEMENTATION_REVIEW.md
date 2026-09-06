# Mercury Analytics and ML Review

Use this checklist when reviewing analytics or machine-learning work:

- Confirm the source dataset, grain, key definitions, and null policy.
- Prevent temporal leakage by deriving features only from information available at prediction time.
- Split training and evaluation data by time or customer as appropriate.
- Report class balance, baseline comparisons, precision/recall, calibration, and business impact.
- Version preprocessing, feature definitions, model artifacts, and evaluation data.
- Keep model inference deterministic and separate from exploratory notebooks.
- Expose model confidence and last-refresh metadata through the API where useful.
- Add tests for metric calculations, empty inputs, duplicate transactions, and boundary dates.