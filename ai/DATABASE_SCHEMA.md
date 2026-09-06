# Mercury Data Schema

The analytical PostgreSQL model is organized around:

- `customers`: stable customer identifiers and profile attributes.
- `orders`: invoice-level transaction records.
- `order_items`: products, quantities, prices, and order relationships.
- `products`: product metadata.
- `countries`: country reference data.
- `customer_metrics`: calculated revenue, recency, frequency, monetary value, RFM segment, churn output, and revenue-at-risk values.

Use foreign keys, appropriate numeric types for money, UTC-aware timestamps where applicable, and indexes for customer/order joins and dashboard filters. Treat schema changes as contract changes and update this document plus affected SQL and tests.