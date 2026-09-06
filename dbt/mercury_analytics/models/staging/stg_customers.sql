-- stg_customers.sql
-- =============================================================================
-- Staging: Customers
-- =============================================================================
-- Resolves the Olist customer_id ambiguity:
--   customer_id  = order-scoped (one per order, useless for repeat analysis)
--   customer_unique_id = true returning-customer identifier
--
-- This model renames columns to Mercury conventions and selects only
-- the fields needed downstream.
-- =============================================================================

WITH source AS (
    SELECT * FROM {{ source('raw', 'customers') }}
),

renamed AS (
    SELECT
        customer_id,                                -- order-scoped FK to orders
        customer_unique_id,                         -- true customer key for RFM
        customer_zip_code_prefix   AS zip_prefix,
        LOWER(TRIM(customer_city)) AS city,
        UPPER(TRIM(customer_state)) AS state
    FROM source
)

SELECT * FROM renamed
