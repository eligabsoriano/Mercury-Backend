# Project Identity

Mercury is a customer intelligence and retention analytics platform for e-commerce businesses. It turns transaction data into customer segments, churn predictions, revenue-at-risk estimates, and retention recommendations.

This repository is independent. Do not assume that it is part of, or shares source code with, any other application.

# Instruction Priority Hierarchy

When instructions conflict, resolve them using this strict hierarchy:
1. **User Task Prompt**: Explicit instructions and constraints in the immediate user prompt.
2. **Active Project AGENTS.md**: Repository-level guardrails, autonomy policies, and definitions of done.
3. **Invoked Skill Instructions**: Domain-specific guidance loaded via `.agents/skills/`.
4. **Project Documentation**: Design docs in `docs/` (`architecture.md`, `methodology.md`).
5. **Retrieved External Data**: Web search results, external references, or default model priors.

# Autonomy & Decision Boundaries

## Autonomous (Proceed Without Asking)
- Internal code modifications, bug fixes, and refactoring within existing architectural layers.
- Creating and updating unit and integration test suites.
- Running non-destructive local validation commands (`pytest tests/ -v`, `ruff check`, `ruff format`, `python scripts/export_openapi.py`).
- Adding and updating documentation to reflect verified code changes.
- Updating schema exports when API contracts change intentionally.

## Require Explicit User Approval
- Destructive database commands (e.g., `DROP TABLE`, `TRUNCATE`, destructive migrations) against live or remote databases (Neon).
- Accessing, modifying, or creating live credentials, `.env` files, or cloud secrets.
- Breaking existing public API response contracts or removing active endpoints.
- Triggering production deployments or cloud infrastructure provisioning (Render, Railway, Vercel).

# Scope and Current Baseline

- **Data and analytics**: Python 3.13, Pandas, NumPy, SQL, and Jupyter.
- **Database**: PostgreSQL (Neon-hosted), raw schema ingested from Olist Brazilian E-Commerce dataset.
- **Transformation**: dbt Core (`dbt-postgres`) under `dbt/mercury_analytics/` with 5 analytical marts (`mart_customer_metrics`, `dim_customers`, `fact_orders`, `mart_product_metrics`, `mart_seller_metrics`).
- **Machine learning**: scikit-learn (RFM segmentation and Random Forest churn prediction models under `ml/`).
- **API**: FastAPI application under `backend/` exposing 25 REST endpoints across health, analytics, customer intelligence, predictions, retention, products, and sellers.
- **Testing**: 152 automated tests in `tests/` (114 offline mock/unit tests, 38 live DB integration tests skipped without `DATABASE_URL`).
- **Downstream targets**: React/TypeScript web app (`Mercury-Web`), Flutter mobile app, and Power BI reporting.

# Working Rules

- Check `git status --short` before editing and preserve unrelated changes.
- Keep changes focused, minimal, and consistent with nearby files and conventions.
- Keep data preparation, SQL, machine-learning, API, and reporting concerns in their owning directories:
  - `backend/`: FastAPI application, routers, schemas, services, and database session management.
  - `dbt/`: dbt models (staging, intermediate, marts), tests, and schema configurations under `dbt/mercury_analytics/`.
  - `ml/`: Model training pipelines, feature engineering, and inference artifacts.
  - `docs/`: Technical specifications, architectural designs, and analytical methodologies.
- Keep API validation and response shaping in Pydantic schemas at the FastAPI boundary; keep analytical logic in services or marts.
- Use parameterized SQL always (`sqlalchemy.text` with explicit parameter dictionaries). Never concatenate user input into SQL queries.
- Never log, print, or expose database credentials, tokens, or sensitive customer data.

# Implementation Workflow

1. **Identify the Owning Layer**: Determine whether the change belongs in `backend/`, `dbt/`, `ml/`, or `docs/`.
2. **Read Existing Contracts**: Check relevant schemas, models, tests, or documentation before writing code.
3. **Make Focused Changes**: Preserve existing working contracts and make the smallest maintainable edit.
4. **Proportional Verification**:
   - Documentation changes: verify markdown rendering, links, and structure.
   - Code changes: run focused tests first, then project linter and test suite.
   - API changes: verify response shapes and update OpenAPI schema export.
5. **Review Diff**: Ensure zero unrelated diffs and clear reporting of verification results.

# Definition of Done (DoD)

A task or feature is considered complete only when:
1. **Linting & Formatting**: Code passes `.venv/bin/ruff check backend/ ml/ tests/ scripts/` and `.venv/bin/ruff format --check backend/ ml/ tests/ scripts/` with zero errors.
2. **Automated Tests**: The test suite passes cleanly via `.venv/bin/pytest tests/ -v` (zero failures).
3. **API Synchronization**: If FastAPI routers or schemas were altered, `python scripts/export_openapi.py` has been executed to synchronize `docs/openapi.json`.
4. **Documentation**: Any changes to data models, API endpoints, or methodology are accurately documented in `docs/architecture.md` or `docs/methodology.md`.
