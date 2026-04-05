-- ============================================================
-- FILE: 05_market_expansion_model.sql
-- PURPOSE: Composite market scoring for expansion decisions
-- REQUIRES: MySQL 8.0+ (window functions)
-- FIXES vs original:
--   • RANK() window functions referenced in same SELECT scope
--     they were defined — split into a second CTE (ranked).
--   • Integer division in fulfillment_rate fixed with CAST.
--   • Added 3rd pillar: avg_order_value rank (margin signal).
--   • Lower composite_score = better combined opportunity.
-- ============================================================

USE market_analysis;

WITH state_metrics AS (
    SELECT
        ship_state,
        SUM(amount)                                                           AS total_revenue,
        ROUND(
            CAST(SUM(amount) AS DECIMAL(18,4)) /
            (SELECT SUM(amount) FROM amazon_sales WHERE amount_valid = 1) * 100,
            2
        )                                                                     AS revenue_share_pct,
        ROUND(
            CAST(SUM(is_fulfilled) AS DECIMAL(10,4)) / COUNT(*) * 100,
            2
        )                                                                     AS fulfillment_rate,
        ROUND(AVG(amount), 2)                                                 AS avg_order_value,
        COUNT(*)                                                              AS total_orders
    FROM amazon_sales
    WHERE amount_valid = 1
    GROUP BY ship_state
),
ranked AS (
    SELECT
        ship_state,
        total_revenue,
        revenue_share_pct,
        fulfillment_rate,
        avg_order_value,
        total_orders,
        RANK() OVER (ORDER BY total_revenue    DESC) AS revenue_rank,
        RANK() OVER (ORDER BY fulfillment_rate DESC) AS fulfillment_rank,
        RANK() OVER (ORDER BY avg_order_value  DESC) AS aov_rank
    FROM state_metrics
)
SELECT
    ship_state,
    total_revenue,
    revenue_share_pct,
    fulfillment_rate,
    avg_order_value,
    total_orders,
    revenue_rank,
    fulfillment_rank,
    aov_rank,
    (revenue_rank + fulfillment_rank + aov_rank) AS composite_score
FROM ranked
ORDER BY composite_score ASC;
