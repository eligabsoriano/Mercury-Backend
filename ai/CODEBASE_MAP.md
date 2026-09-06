    # Mercury Codebase Map

Last updated: 2026-09-06 (Phase 1 — Scaffolding complete)

## Directory Structure

```
mercury/
├── backend/              ← FastAPI app: routes, schemas, services, DB access
│   ├── routers/          ← Route handlers (one file per resource)
│   ├── schemas/          ← Pydantic request/response models
│   └── services/         ← Business logic and DB query layer
├── data/
│   ├── raw/              ← Original dataset downloads (gitignored, never committed)
│   └── processed/        ← Cleaned outputs from ETL (gitignored)
├── docs/                 ← Architecture and methodology documentation
├── etl/                  ← Data cleaning, validation, and PostgreSQL loading scripts
├── ml/
│   └── artifacts/        ← Trained model files (.pkl/.joblib) (gitignored)
├── notebooks/            ← Exploratory analysis and reproducible investigations
├── sql/                  ← DDL schema, analytical views, metric queries
├── tests/                ← Pytest suite: ETL, ML, API, integration
├── ai/                   ← Agent context: state, maps, decisions, plans
├── .env.example          ← Required environment variable documentation
├── .gitignore            ← Protects secrets, datasets, and artifacts
├── requirements.txt      ← Pinned Python dependencies
└── README.md             ← Project overview
```

## Implementation Status by Area

| Directory    | Status                       | Phase |
|--------------|------------------------------|-------|
| `backend/`   | Structure only               | 1 ✅   |
| `data/`      | Structure only               | 1 ✅   |
| `etl/`       | Structure only               | 3     |
| `ml/`        | Structure only               | 4–5   |
| `notebooks/` | Structure only               | 1 ✅   |
| `sql/`       | Structure only               | 2     |
| `tests/`     | Structure only               | 3+    |

## Data Flow

```
Online Retail II data → ETL → PostgreSQL → metrics/features → ML → FastAPI → React/Power BI
```

Update this map when real source directories, entry points, or ownership boundaries are added.