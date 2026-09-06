# Mercury Data Foundation Plan

## Goal

Establish a reproducible ETL and PostgreSQL foundation for customer analytics.

## Steps

1. Confirm Online Retail II input schema and data-quality rules.
2. Implement raw-to-clean transformations with validation reports.
3. Define PostgreSQL tables, keys, indexes, and analytical views.
4. Load a small safe fixture dataset locally.
5. Add tests for duplicates, returns, missing identifiers, dates, and money calculations.
6. Document the repeatable load and rollback procedure.

## Guardrails

Do not use production credentials or commit raw customer data. Validate row counts and aggregate totals at every boundary.