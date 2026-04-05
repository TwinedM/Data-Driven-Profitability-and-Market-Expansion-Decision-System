-- ============================================================
-- FILE: 01_schema.sql
-- PURPOSE: Create database and main sales table
-- RUN THIS FIRST before loading CSV data
-- ============================================================

CREATE DATABASE IF NOT EXISTS market_analysis;
USE market_analysis;

DROP TABLE IF EXISTS amazon_sales;

CREATE TABLE amazon_sales (
    order_id        VARCHAR(50),
    order_date      DATE,
    status          VARCHAR(100),
    fulfillment     VARCHAR(50),
    sales_channel   VARCHAR(100),
    ship_service    VARCHAR(100),
    style           VARCHAR(100),
    sku             VARCHAR(100),
    category        VARCHAR(100),
    size            VARCHAR(50),
    asin            VARCHAR(50),
    courier_status  VARCHAR(100),
    quantity        INT,
    currency        VARCHAR(10),
    amount          DECIMAL(12,2),
    ship_city       VARCHAR(100),
    ship_state      VARCHAR(100),
    b2b_flag        VARCHAR(10),
    is_fulfilled    TINYINT(1) DEFAULT 0,
    amount_valid    TINYINT(1) DEFAULT 1
);
