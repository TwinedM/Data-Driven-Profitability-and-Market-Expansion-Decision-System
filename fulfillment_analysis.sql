-- Fulfillment Rate by State
SELECT
    ship_state,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN status = 'Shipped' THEN 1 ELSE 0 END) AS shipped_orders,
    ROUND(
        SUM(CASE WHEN status = 'Shipped' THEN 1 ELSE 0 END)
        / COUNT(*) * 100,
        2
    ) AS fulfillment_rate
FROM amazon_sales
GROUP BY ship_state
ORDER BY fulfillment_rate DESC;
