-- stg_closed_deals.sql
-- =============================================================================
-- Staging: Closed Deals
-- =============================================================================
-- Lightly cleaned converted seller acquisition deals from raw_marketing.closed_deals.
-- =============================================================================

WITH source AS (
    SELECT * FROM {{ source('raw_marketing', 'closed_deals') }}
),

cleaned AS (
    SELECT
        mql_id,
        seller_id,
        sdr_id,
        sr_id,
        won_date,
        LOWER(TRIM(business_segment))                                      AS business_segment,
        LOWER(TRIM(lead_type))                                             AS lead_type,
        LOWER(TRIM(lead_behaviour_profile))                                AS lead_behaviour_profile,
        COALESCE(has_company, FALSE)                                       AS has_company,
        COALESCE(has_gtin, FALSE)                                          AS has_gtin,
        average_stock,
        LOWER(TRIM(business_type))                                         AS business_type,
        COALESCE(declared_product_catalog_size, 0.0)::NUMERIC(12,2)        AS declared_product_catalog_size,
        COALESCE(declared_monthly_revenue, 0.0)::NUMERIC(14,2)             AS declared_monthly_revenue
    FROM source
)

SELECT * FROM cleaned
