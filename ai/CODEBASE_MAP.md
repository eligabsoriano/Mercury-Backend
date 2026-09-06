# Mercury Codebase Map

Mercury is currently documentation-first. The intended implementation is organized around:

- `data/`: raw and processed dataset boundaries; never commit sensitive exports.
- `etl/`: transaction cleaning, validation, and PostgreSQL loading.
- `sql/`: schema, analytical views, and customer metric queries.
- `ml/`: feature engineering, RFM segmentation, churn models, evaluation, and inference.
- `backend/`: FastAPI routes, schemas, services, and database access.
- `frontend/`: React and TypeScript customer intelligence views.
- `notebooks/`: exploratory analysis and reproducible investigations.
- `powerbi/`: report definitions and documented dashboard inputs.
- `docs/`: architecture and methodology documentation.

Expected flow: Online Retail II data -> ETL -> PostgreSQL -> metrics/features -> ML -> FastAPI/React/Power BI.

Update this map when real source directories, entry points, or ownership boundaries are added.