-- Overall Revenue & AOV
SELECT
    SUM(amount) AS total_revenue,
    ROUND(AVG(amount),2) AS avg_order_value
FROM amazon_sales;

-- Revenue by State
SELECT
    ship_state,
    SUM(amount) AS total_revenue,
    COUNT(*) AS total_orders
FROM amazon_sales
GROUP BY ship_state
ORDER BY total_revenue DESC;

-- Revenue Share %
SELECT
    ship_state,
    SUM(amount) AS total_revenue,
    ROUND(
        SUM(amount) / (SELECT SUM(amount) FROM amazon_sales) * 100,
        2
    ) AS revenue_share_pct
FROM amazon_sales
GROUP BY ship_state
ORDER BY total_revenue DESC;
