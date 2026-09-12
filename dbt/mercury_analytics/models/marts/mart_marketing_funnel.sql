-- mart_marketing_funnel.sql
-- =============================================================================
-- Mart: Marketing Funnel & Attribution
-- =============================================================================
-- Unifies seller acquisition marketing qualified leads (MQL), conversion outcomes,
-- sales cycle duration (days to close), declared seller characteristics, and actual
-- realized marketplace performance (orders fulfilled and GMV revenue).
-- =============================================================================

WITH leads AS (
    SELECT * FROM {{ ref('stg_marketing_leads') }}
),

deals AS (
    SELECT * FROM {{ ref('stg_closed_deals') }}
),

seller_performance AS (
    SELECT
        seller_id,
        total_orders_fulfilled,
        total_revenue
    FROM {{ ref('mart_seller_metrics') }}
),

funnel AS (
    SELECT
        l.mql_id,
        l.first_contact_date,
        l.landing_page_id,
        l.origin,
        CASE WHEN d.mql_id IS NOT NULL THEN TRUE ELSE FALSE END            AS is_won,
        d.won_date,
        CASE
            WHEN d.won_date IS NOT NULL AND l.first_contact_date IS NOT NULL
            THEN (d.won_date - l.first_contact_date)::INTEGER
            ELSE NULL
        END                                                                AS days_to_close,
        d.seller_id,
        d.sdr_id,
        d.sr_id,
        d.business_segment,
        d.lead_type,
        d.lead_behaviour_profile,
        d.business_type,
        d.has_company,
        d.has_gtin,
        COALESCE(d.declared_monthly_revenue, 0.0)::NUMERIC(14,2)           AS declared_monthly_revenue,
        COALESCE(d.declared_product_catalog_size, 0.0)::NUMERIC(12,2)      AS declared_product_catalog_size,
        CASE
            WHEN sp.seller_id IS NOT NULL AND sp.total_orders_fulfilled > 0
            THEN TRUE
            ELSE FALSE
        END                                                                AS is_active_marketplace_seller,
        COALESCE(sp.total_orders_fulfilled, 0)::INTEGER                    AS actual_orders_fulfilled,
        COALESCE(sp.total_revenue, 0.0)::NUMERIC(14,2)                     AS actual_marketplace_revenue
    FROM leads l
    LEFT JOIN deals d ON l.mql_id = d.mql_id
    LEFT JOIN seller_performance sp ON d.seller_id = sp.seller_id
)

SELECT * FROM funnel
