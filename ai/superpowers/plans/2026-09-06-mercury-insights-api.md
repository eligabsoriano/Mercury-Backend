# Mercury Insights API Plan

## Goal

Expose customer intelligence safely through FastAPI and provide a stable contract for the React interface and Power BI.

## Steps

1. Confirm customer, metric, segment, churn, and revenue-at-risk schemas.
2. Implement read-only endpoints with validation and pagination.
3. Add filtering for segment, risk, value, country, and activity windows.
4. Add consistent not-found and validation error responses.
5. Add focused endpoint tests and an API contract example.
6. Connect the frontend only through the API boundary.

## Guardrails

Use parameterized queries, authorize customer-data access, avoid sensitive fields, and do not expose raw database errors.