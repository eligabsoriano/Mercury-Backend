# Mercury API Map

The documented FastAPI surface is:

| Method | Path | Purpose |
|---|---|---|
| GET | `/customers` | List customers with filtering and pagination. |
| GET | `/customers/{customer_id}` | Retrieve a customer intelligence profile. |
| GET | `/customers/{customer_id}/rfm` | Retrieve RFM metrics and segment. |
| GET | `/customers/{customer_id}/churn` | Retrieve churn probability and model evidence. |
| GET | `/customers/at-risk` | List customers prioritized by churn and value. |
| GET | `/customers/revenue-at-risk` | Summarize projected revenue exposure. |

These routes are planned/documented, not proof of implementation. Preserve response shapes, validation, pagination, status codes, and error behavior when the API is built.