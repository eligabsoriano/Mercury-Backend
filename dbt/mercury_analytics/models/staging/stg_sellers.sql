-- stg_sellers.sql
-- =============================================================================
-- Staging: Sellers
-- =============================================================================
-- Lightly cleaned seller dimension.
-- =============================================================================

WITH source AS (
    SELECT * FROM {{ source('raw', 'sellers') }}
),

cleaned AS (
    SELECT
        seller_id,
        seller_zip_code_prefix             AS zip_prefix,
        LOWER(TRIM(seller_city))           AS city,
        UPPER(TRIM(seller_state))          AS state
    FROM source
)

SELECT * FROM cleaned
