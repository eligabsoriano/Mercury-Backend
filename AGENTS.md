# Project Identity

Mercury is a customer intelligence and retention analytics platform for
e-commerce businesses. It turns transaction data into customer segments,
churn predictions, revenue-at-risk estimates, and retention recommendations.

This repository is independent. Do not assume that it is part of, or shares
source code with, any other application.

# Scope and Technology

- Data and analytics: Python, Pandas, NumPy, SQL, and Jupyter
- Database: PostgreSQL, including Neon-hosted environments
- Machine learning: scikit-learn and Matplotlib
- API: FastAPI
- Frontend: React, TypeScript, and Tailwind CSS
- Reporting: Microsoft Power BI
- Deployment targets: Vercel, Render, and Railway

The documented analytical flow is:

```text
Online Retail II data -> ETL and cleaning -> PostgreSQL
    -> customer metrics and RFM -> churn models and recommendations
    -> Power BI, FastAPI, and React
```

# Repository Guidance

Use the existing project documentation as the source of truth:

- `README.md`: project purpose, capabilities, stack, and status
- `docs/architecture.md`: system flow, data model, API surface, and intended
  project structure
- `docs/methodology.md`: analytics and machine-learning methodology
- Keep this file current as the implementation structure develops.

The current checkout is documentation-first. Do not invent source directories
or claim that an API, frontend, database, model, or deployment exists until it
is present and verified in the repository.

# Working Rules

- Check `git status --short` before editing and preserve unrelated changes.
- Keep changes focused and consistent with nearby files and documentation.
- Prefer existing libraries, helpers, schemas, and project conventions.
- Do not add dependencies, rename broad sections, or reformat unrelated files
  without a clear need.
- Keep data preparation, SQL, machine-learning, API, frontend, and reporting
  concerns in their owning directories as the implementation grows.
- Keep API validation and response shaping in the FastAPI boundary; keep
  analytics and business rules in the appropriate data or service layer.
- Use parameterized SQL and validate external input. Do not expose database
  credentials or sensitive customer data through API responses or logs.
- Add or update documentation when the data model, API contract, analytical
  methodology, or user-facing workflow changes.

# Sensitive Data and Operations

- Never read, print, commit, or modify secrets, `.env` files, database URLs,
  API keys, private credentials, customer exports, raw personal data, or
  production datasets unless explicitly required and approved.
- Use an example configuration file for documenting required environment
  variables. Keep real values local.
- Do not run destructive database commands, production migrations, deployments,
  or data backfills without explicit approval.
- Treat raw datasets, generated reports, model artifacts, build output, and
  dependency directories as protected or generated unless the task requires
  changing them.

# Implementation Workflow

1. Identify the owning area: data preparation, SQL, machine learning, API,
   frontend, or Power BI/reporting.
2. Read the relevant documentation and nearby implementation or tests.
3. State the root cause or intended behavior before changing code.
4. Make the smallest maintainable change and preserve existing contracts.
5. Run the cheapest focused validation first, then broader checks proportional
   to the change.
6. Review the final diff and report what was changed, verified, and not run.

For data and machine-learning changes, verify schemas, null handling, leakage
risk, reproducibility, and metric calculations. For API changes, verify input
validation, status codes, response shapes, and error handling. For frontend
changes, verify loading, empty, error, and responsive states.

# Testing and Validation

- Documentation-only changes require path/structure checks and a clean status
  review; unrelated runtime suites are unnecessary.
- Python/data changes should use focused tests or reproducible validation
  scripts, followed by the project-wide test command when available.
- SQL changes should be checked against the documented PostgreSQL schema and
  representative edge cases.
- FastAPI changes should include focused endpoint tests where the test suite
  exists, including invalid input and error responses.
- React/TypeScript changes should use the configured type-check, lint, test,
  and build commands when those scripts exist.
- Never claim live database, external-service, deployment, browser, or
  Power BI validation without actually running it.
