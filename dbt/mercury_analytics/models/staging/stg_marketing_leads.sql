-- stg_marketing_leads.sql
-- =============================================================================
-- Staging: Marketing Qualified Leads (MQL)
-- =============================================================================
-- Lightly cleaned seller acquisition marketing leads from raw_marketing.mql.
-- =============================================================================

WITH source AS (
    SELECT * FROM {{ source('raw_marketing', 'mql') }}
),

cleaned AS (
    SELECT
        mql_id,
        first_contact_date,
        landing_page_id,
        COALESCE(NULLIF(LOWER(TRIM(origin)), ''), 'unknown') AS origin
    FROM source
)

SELECT * FROM cleaned
