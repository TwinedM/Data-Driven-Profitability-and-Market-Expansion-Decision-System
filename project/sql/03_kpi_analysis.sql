-- ============================================================
-- FILE: 03_kpi_analysis.sql
-- PURPOSE: Core revenue KPIs
-- FIXES vs original:
--   • Uses amount_valid filter so nulls are excluded
--   • Added total_orders to overall summary
--   • DECIMAL cast in revenue_share_pct to avoid integer division
-- ============================================================

USE market_analysis;

-- ── 1. Overall Revenue, Orders & AOV ─────────────────────────
SELECT
    SUM(amount)            AS total_revenue,
    COUNT(*)               AS total_orders,
    ROUND(AVG(amount), 2)  AS avg_order_value
FROM amazon_sales
WHERE amount_valid = 1;

-- ── 2. Revenue by State ───────────────────────────────────────
SELECT
    ship_state,
    SUM(amount)  AS total_revenue,
    COUNT(*)     AS total_orders
FROM amazon_sales
WHERE amount_valid = 1
GROUP BY ship_state
ORDER BY total_revenue DESC;

-- ── 3. Revenue Share % by State ──────────────────────────────
SELECT
    ship_state,
    SUM(amount) AS total_revenue,
    ROUND(
        CAST(SUM(amount) AS DECIMAL(18,4)) /
        (SELECT SUM(amount) FROM amazon_sales WHERE amount_valid = 1) * 100,
        2
    ) AS revenue_share_pct
FROM amazon_sales
WHERE amount_valid = 1
GROUP BY ship_state
ORDER BY revenue_share_pct DESC;

-- ── 4. Revenue & Orders by Category ──────────────────────────
SELECT
    category,
    SUM(amount)            AS total_revenue,
    COUNT(*)               AS total_orders,
    ROUND(AVG(amount), 2)  AS avg_order_value
FROM amazon_sales
WHERE amount_valid = 1
GROUP BY category
ORDER BY total_revenue DESC;
