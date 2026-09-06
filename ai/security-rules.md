# Mercury Security Rules

- Never expose `.env` values, database URLs, API keys, customer exports, raw personal data, or production logs.
- Keep secrets in environment configuration and document only safe variable names in examples.
- Validate and authorize every API input and customer-data query.
- Use parameterized SQL and least-privilege database roles.
- Redact customer identifiers and sensitive values from logs and error responses.
- Do not use production data for local experiments or tests.
- Require explicit approval before deployments, destructive database actions, backfills, or credential changes.