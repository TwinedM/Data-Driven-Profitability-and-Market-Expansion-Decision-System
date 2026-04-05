-- ============================================================
-- FILE: 04_fulfillment_analysis.sql
-- PURPOSE: Fulfillment rate by state and category
-- FIXES vs original:
--   • Integer division bug fixed with CAST(… AS DECIMAL)
--   • Uses is_fulfilled column set in datacleaning.sql so
--     "Shipped - Delivered to Buyer" is also counted
--   • Renamed column to fulfillment_rate_pct for clarity
-- ============================================================

USE market_analysis;

-- ── 1. Fulfillment Rate by State ─────────────────────────────
SELECT
    ship_state,
    COUNT(*)                                                       AS total_orders,
    SUM(is_fulfilled)                                              AS fulfilled_orders,
    ROUND(
        CAST(SUM(is_fulfilled) AS DECIMAL(10,4)) / COUNT(*) * 100,
        2
    )                                                              AS fulfillment_rate_pct
FROM amazon_sales
GROUP BY ship_state
ORDER BY fulfillment_rate_pct DESC;

-- ── 2. Overall Fulfillment Rate ───────────────────────────────
SELECT
    ROUND(
        CAST(SUM(is_fulfilled) AS DECIMAL(10,4)) / COUNT(*) * 100,
        2
    ) AS overall_fulfillment_rate_pct
FROM amazon_sales;

-- ── 3. Fulfillment Rate by Category ──────────────────────────
SELECT
    category,
    COUNT(*)                                                       AS total_orders,
    SUM(is_fulfilled)                                              AS fulfilled_orders,
    ROUND(
        CAST(SUM(is_fulfilled) AS DECIMAL(10,4)) / COUNT(*) * 100,
        2
    )                                                              AS fulfillment_rate_pct
FROM amazon_sales
GROUP BY category
ORDER BY fulfillment_rate_pct DESC;

-- ── 4. Amazon vs Merchant Fulfillment ────────────────────────
SELECT
    fulfillment,
    COUNT(*)                                                       AS total_orders,
    SUM(amount)                                                    AS total_revenue,
    ROUND(
        CAST(SUM(is_fulfilled) AS DECIMAL(10,4)) / COUNT(*) * 100,
        2
    )                                                              AS fulfillment_rate_pct
FROM amazon_sales
WHERE amount_valid = 1
GROUP BY fulfillment;
