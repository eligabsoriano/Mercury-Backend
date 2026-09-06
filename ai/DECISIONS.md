# Mercury Decisions

## Accepted

- PostgreSQL is the analytical source of truth.
- FastAPI exposes customer intelligence to the web interface.
- RFM analysis and churn prediction are separate analytical stages.
- Power BI consumes documented, stable analytical outputs.

## Open

- Final PostgreSQL migration/tooling choice.
- Model registry and artifact versioning approach.
- Authentication and authorization requirements for dashboard users.
- Batch versus on-demand prediction refresh cadence.
- Deployment ownership and environment configuration strategy.

Record the rationale and affected files whenever an open decision is resolved.