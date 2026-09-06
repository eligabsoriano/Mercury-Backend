# Mercury Current State

Snapshot date: 2026-09-06.

## Phase 1 — Scaffolding (✅ Complete)

The following files and directories were created as part of Phase 1:

| Path | Purpose |
|------|---------|
| `requirements.txt` | Pinned Python dependencies (pandas, psycopg2, scikit-learn, FastAPI, pytest, httpx) |
| `.env.example` | Environment variable reference — copy to `.env` and fill in values |
| `.gitignore` | Protects `.env`, `data/`, `ml/artifacts/`, `*.pkl`, `__pycache__/`, etc. |
| `etl/` | ETL pipeline directory (implementation starts Phase 3) |
| `sql/` | SQL schema and queries directory (implementation starts Phase 2) |
| `ml/artifacts/` | ML model artifact directory (gitignored) |
| `backend/routers/` | FastAPI route handlers directory |
| `backend/schemas/` | Pydantic model directory |
| `backend/services/` | Business logic and DB query layer |
| `notebooks/` | Exploratory analysis |
| `tests/` | Pytest suite |
| `data/raw/` | Raw dataset (gitignored — never commit) |
| `data/processed/` | ETL output (gitignored) |

## Verified Runtime State

- Python 3.13.5 confirmed on host machine.
- No runtime backend, frontend, trained model, database connection, or deployment has been verified in this checkout.
- All directories contain `.gitkeep` files so git tracks the structure before implementation code is added.

## Next Phase

**Phase 2 — PostgreSQL Schema**: Write `sql/schema.sql`, `sql/views.sql`, and `sql/migrate.py`.

Treat planned endpoints, directories, and capabilities as design guidance until source code and focused validation exist.