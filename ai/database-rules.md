# Mercury Database Rules

- PostgreSQL is the analytical source of truth.
- Use migrations or the repository's selected schema tool once implementation begins; do not mutate production manually.
- Use parameterized queries and least-privilege credentials.
- Preserve raw, cleaned, and analytical layers so transformations are reproducible.
- Define keys, foreign keys, indexes, numeric precision, and timestamp semantics explicitly.
- Validate duplicate invoices, returns, negative quantities, missing customer IDs, and currency assumptions.
- Do not load production or personal data during local tests.
- Review schema changes against `ai/DATABASE_SCHEMA.md` and affected API/Power BI consumers.