# Mercury Testing Standards

- Documentation-only changes need path and structure validation.
- ETL tests should cover schema, nulls, duplicates, returns, date boundaries, and idempotency.
- SQL tests should cover joins, aggregates, filters, and representative edge cases.
- ML tests should cover feature calculations, leakage boundaries, reproducibility, empty inputs, and model-output schema.
- FastAPI tests should cover valid responses, invalid input, status codes, pagination, and error handling.
- React tests should cover loading, empty, error, filtering, accessibility, and responsive behavior.
- Run the smallest focused check first, then the project-wide test/type/lint/build commands that exist.
- Do not claim live database, deployment, browser, or Power BI validation without evidence.