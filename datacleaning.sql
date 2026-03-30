-- ============================================================
-- datacleaning.sql
-- Amazon Sales Data — Cleaning & Standardisation
-- Fixes: case inconsistency (Bihar/bihar/BIHAR), nulls, status values
-- ============================================================

USE market_analysis;

-- ── 1. Audit before cleaning ──────────────────────────────────

-- Total rows
SELECT COUNT(*) AS total_rows FROM amazon_sales;

-- Date range
SELECT MIN(order_date) AS start_date, MAX(order_date) AS end_date FROM amazon_sales;

-- Null amounts
SELECT COUNT(*) AS null_amount_rows FROM amazon_sales WHERE amount IS NULL;

-- Distinct raw status values (shows the mess)
SELECT status, COUNT(*) AS cnt FROM amazon_sales GROUP BY status ORDER BY cnt DESC;

-- Case inconsistency in ship_state (the Bihar/bihar/BIHAR problem)
SELECT ship_state, COUNT(*) AS cnt
FROM amazon_sales
GROUP BY ship_state
HAVING COUNT(DISTINCT UPPER(ship_state)) >= 1
ORDER BY UPPER(ship_state);

-- ── 2. Fix case inconsistency — standardise ship_state to UPPER ──

UPDATE amazon_sales
SET ship_state = UPPER(TRIM(ship_state));

-- Verify: should now see only one row per state
SELECT ship_state, COUNT(*) AS cnt
FROM amazon_sales
GROUP BY ship_state
ORDER BY ship_state;

-- ── 3. Fix ship_city similarly ───────────────────────────────

UPDATE amazon_sales
SET ship_city = UPPER(TRIM(ship_city));

-- ── 4. Standardise status values ────────────────────────────
-- Shipped = fulfilled successfully
-- Cancelled, Returned = not fulfilled
-- All others → review

SELECT DISTINCT status FROM amazon_sales;

-- Add a clean derived column for fulfilled flag
ALTER TABLE amazon_sales ADD COLUMN IF NOT EXISTS is_fulfilled TINYINT(1);

UPDATE amazon_sales
SET is_fulfilled = CASE
    WHEN UPPER(TRIM(status)) IN ('SHIPPED', 'SHIPPED - DELIVERED TO BUYER') THEN 1
    ELSE 0
END;

-- ── 5. Handle null amounts ───────────────────────────────────
-- Do not delete — flag them for exclusion in analysis
ALTER TABLE amazon_sales ADD COLUMN IF NOT EXISTS amount_valid TINYINT(1);
UPDATE amazon_sales SET amount_valid = CASE WHEN amount IS NULL OR amount <= 0 THEN 0 ELSE 1 END;

-- ── 6. Standardise b2b_flag ─────────────────────────────────
UPDATE amazon_sales
SET b2b_flag = CASE
    WHEN UPPER(TRIM(b2b_flag)) IN ('TRUE', '1', 'YES', 'B2B') THEN 'B2B'
    ELSE 'B2C'
END;

-- ── 7. Final audit after cleaning ───────────────────────────

SELECT
    COUNT(*)                                      AS total_rows,
    COUNT(DISTINCT ship_state)                    AS distinct_states,
    SUM(CASE WHEN amount_valid = 0 THEN 1 END)   AS invalid_amount_rows,
    SUM(is_fulfilled)                             AS fulfilled_orders,
    ROUND(SUM(is_fulfilled)/COUNT(*)*100, 2)      AS overall_fulfillment_rate_pct,
    COUNT(DISTINCT category)                      AS distinct_categories,
    SUM(CASE WHEN b2b_flag = 'B2B' THEN 1 END)  AS b2b_orders,
    SUM(CASE WHEN b2b_flag = 'B2C' THEN 1 END)  AS b2c_orders
FROM amazon_sales;
