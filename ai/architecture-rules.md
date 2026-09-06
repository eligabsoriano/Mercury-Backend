# Mercury Architecture Rules

- Keep ETL, SQL, ML, API, frontend, and Power BI concerns in separate owning areas.
- The data flow is ETL -> PostgreSQL -> analytical queries/features -> models -> FastAPI/React/Power BI.
- Keep request validation and response shaping in FastAPI schemas/routes.
- Keep business calculations in testable services or domain modules, not route handlers.
- Keep model training separate from inference and API startup.
- Do not make notebooks the only location of production logic.
- Use documented, stable SQL views or API schemas for Power BI and frontend consumers.
- Do not introduce cross-layer imports that bypass the intended boundaries.