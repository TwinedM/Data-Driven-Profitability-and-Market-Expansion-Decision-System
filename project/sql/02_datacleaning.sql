-- ============================================================
-- FILE: 02_datacleaning.sql
-- PURPOSE: Validate, clean and standardise raw CSV data
-- RUN AFTER loading CSV via LOAD DATA or Table Import Wizard
-- FIXES vs original:
--   • Added state normalisation (Bihar/BIHAR/bihar → BIHAR)
--   • Added b2b_flag normalisation
--   • Added is_fulfilled and amount_valid derived columns
--   • Fixed HAVING clause bug (COUNT(DISTINCT …) always = 1)
-- ============================================================

USE market_analysis;

-- ── 1. Audit BEFORE cleaning ─────────────────────────────────

-- Total rows
SELECT COUNT(*) AS total_rows FROM amazon_sales;

-- Date range
SELECT MIN(order_date) AS start_date, MAX(order_date) AS end_date
FROM amazon_sales;

-- Null amounts
SELECT COUNT(*) AS null_amount_rows
FROM amazon_sales
WHERE amount IS NULL OR amount <= 0;

-- Distinct raw status values (shows the mess)
SELECT status, COUNT(*) AS cnt
FROM amazon_sales
GROUP BY status
ORDER BY cnt DESC;

-- Case inconsistency preview (Bihar/bihar/BIHAR problem)
SELECT UPPER(TRIM(ship_state)) AS normalised_state,
       COUNT(*) AS cnt
FROM amazon_sales
GROUP BY UPPER(TRIM(ship_state))
ORDER BY normalised_state;

-- ── 2. Normalise ship_state to UPPER CASE ────────────────────
UPDATE amazon_sales
SET ship_state = UPPER(TRIM(ship_state));

-- ── 3. Normalise ship_city similarly ─────────────────────────
UPDATE amazon_sales
SET ship_city = UPPER(TRIM(ship_city));

-- ── 4. Set fulfilled flag ─────────────────────────────────────
-- "Shipped" and "Shipped - Delivered to Buyer" are considered fulfilled
UPDATE amazon_sales
SET is_fulfilled = CASE
    WHEN UPPER(TRIM(status)) IN (
        'SHIPPED',
        'SHIPPED - DELIVERED TO BUYER'
    ) THEN 1
    ELSE 0
END;

-- ── 5. Mark invalid amounts ───────────────────────────────────
UPDATE amazon_sales
SET amount_valid = CASE
    WHEN amount IS NULL OR amount <= 0 THEN 0
    ELSE 1
END;

-- ── 6. Normalise b2b_flag ─────────────────────────────────────
UPDATE amazon_sales
SET b2b_flag = CASE
    WHEN UPPER(TRIM(b2b_flag)) IN ('TRUE','1','YES','B2B') THEN 'B2B'
    ELSE 'B2C'
END;

-- ── 7. Final audit AFTER cleaning ────────────────────────────
SELECT
    COUNT(*)                                             AS total_rows,
    COUNT(DISTINCT ship_state)                           AS distinct_states,
    SUM(CASE WHEN amount_valid = 0 THEN 1 ELSE 0 END)  AS invalid_amount_rows,
    SUM(is_fulfilled)                                    AS fulfilled_orders,
    ROUND(SUM(is_fulfilled) / COUNT(*) * 100, 2)         AS overall_fulfillment_rate_pct,
    COUNT(DISTINCT category)                             AS distinct_categories,
    SUM(CASE WHEN b2b_flag = 'B2B' THEN 1 ELSE 0 END)  AS b2b_orders,
    SUM(CASE WHEN b2b_flag = 'B2C' THEN 1 ELSE 0 END)  AS b2c_orders
FROM amazon_sales;
