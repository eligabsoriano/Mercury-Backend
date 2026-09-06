-- stg_products.sql
-- =============================================================================
-- Staging: Products
-- =============================================================================
-- Joins products to the English category translation.
-- Fixes column name typos from the source CSV (lenght → length).
-- =============================================================================

WITH products AS (
    SELECT * FROM {{ source('raw', 'products') }}
),

translations AS (
    SELECT * FROM {{ source('raw', 'category_translations') }}
),

joined AS (
    SELECT
        p.product_id,
        p.product_category_name                    AS category_name_pt,
        COALESCE(t.product_category_name_english,
                 p.product_category_name)          AS category_name_en,
        p.product_name_lenght                      AS product_name_length,    -- typo fixed in alias
        p.product_description_lenght               AS product_description_length,
        p.product_photos_qty,
        p.product_weight_g,
        p.product_length_cm,
        p.product_height_cm,
        p.product_width_cm
    FROM products p
    LEFT JOIN translations t
           ON t.product_category_name = p.product_category_name
)

SELECT * FROM joined
