-- Composite Market Score
WITH state_metrics AS (
    SELECT
        ship_state,
        SUM(amount) AS total_revenue,
        ROUND(
            SUM(amount) / (SELECT SUM(amount) FROM amazon_sales) * 100,
            2
        ) AS revenue_share_pct,
        ROUND(
            SUM(CASE WHEN status = 'Shipped' THEN 1 ELSE 0 END)
            / COUNT(*) * 100,
            2
        ) AS fulfillment_rate
    FROM amazon_sales
    GROUP BY ship_state
)

SELECT
    ship_state,
    total_revenue,
    revenue_share_pct,
    fulfillment_rate,
    RANK() OVER (ORDER BY total_revenue DESC) AS revenue_rank,
    RANK() OVER (ORDER BY fulfillment_rate DESC) AS fulfillment_rank,
    (
        RANK() OVER (ORDER BY total_revenue DESC) +
        RANK() OVER (ORDER BY fulfillment_rate DESC)
    ) AS composite_score
FROM state_metrics
ORDER BY composite_score ASC;
