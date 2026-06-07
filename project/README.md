git branch -M maingit branch -M main# Data-Driven Profitability & Market Expansion — Automated Insight System

> Amazon India Sales Analytics: SQL pipeline + Python automation that ingests raw sales data, detects anomalies, generates ranked business insights, and delivers HTML reports and a live dashboard automatically.

---

## What This Does

| Before | After |
|--------|-------|
| Manual SQL → Tableau | Automated Python pipeline |
| You read the dashboard | System generates ranked insights |
| You decide what to do | System produces a concrete action table |
| Static Tableau charts | Live browser dashboard (auto-refresh) + email report |
| You run it manually | Scheduler / file watcher runs it automatically |

---

## Project Structure

```
project/
├── sql/
│   ├── 01_schema.sql              Create database + table
│   ├── 02_datacleaning.sql        Audit + clean data (state normalisation etc.)
│   ├── 03_kpi_analysis.sql        Revenue by state, AOV, revenue share %
│   ├── 04_fulfillment_analysis.sql  Fulfillment rate by state & category
│   └── 05_market_expansion_model.sql  Composite market scoring (MySQL 8+)
│
├── app/
│   ├── kpi_engine.py              Loads CSV, computes all KPIs
│   ├── insights.py                Rule engine → ranked insights + action table
│   ├── report.py                  Builds HTML email report with embedded charts
│   ├── dashboard.py               Live browser dashboard (Flask + Plotly)
│   ├── run.py                     Entry point — one-shot / scheduler / watcher / dashboard
│   └── requirements.txt
│
├── Dockerfile
├── .env                           SMTP credentials (never commit to git)
└── .dockerignore
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.9+ |
| MySQL | 8.0+ (window functions for SQL file 05) |
| MySQL Workbench or CLI | any recent |

---

## SQL Setup (optional — for raw SQL analysis)

### Step 1 — Create the database & table
```sql
source sql/01_schema.sql
```

### Step 2 — Load your CSV
```sql
LOAD DATA LOCAL INFILE '/path/to/amazon_sales.csv'
INTO TABLE market_analysis.amazon_sales
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(order_id, @order_date, status, fulfillment, sales_channel,
 ship_service, style, sku, category, size, asin, courier_status,
 quantity, currency, amount, ship_city, ship_state, is_b2b_raw, fulfillment_type)
SET order_date = STR_TO_DATE(@order_date, '%m-%d-%Y');
```
> Adjust the date format string to match your CSV.

### Steps 3-5 — Run analysis scripts in order
```sql
source sql/02_datacleaning.sql
source sql/03_kpi_analysis.sql
source sql/04_fulfillment_analysis.sql
source sql/05_market_expansion_model.sql
```

---

## Python Automation Setup

```bash
pip install -r app/requirements.txt
```

### Environment variables (for email delivery)
Copy `.env` and fill in your Gmail app password:
```
SMTP_USER=your@gmail.com
SMTP_PASS=your-16-char-app-password
```

---

## Usage

```bash
# ── Run once → generates report.html ─────────────────────────
python app/run.py amazon_sales.csv

# ── Run + email the report ────────────────────────────────────
python app/run.py amazon_sales.csv --email you@gmail.com

# ── Schedule daily at 8 AM ────────────────────────────────────
python app/run.py amazon_sales.csv --email you@gmail.com --schedule

# ── Auto-trigger when new CSV is dropped ─────────────────────
python app/run.py amazon_sales.csv --watch

# ── Launch live dashboard (http://localhost:5000) ─────────────
python app/run.py amazon_sales.csv --dashboard

# ── Dashboard on a custom port ────────────────────────────────
python app/run.py amazon_sales.csv --dashboard --port 8080
```

---

## Docker

```bash
# Build
docker build -t amazon-insights .

# Run one-shot report
docker run --env-file .env \
  -v /local/path/amazon_sales.csv:/app/data/amazon_sales.csv \
  -v $(pwd)/outputs:/app/outputs \
  amazon-insights \
  python run.py /app/data/amazon_sales.csv --save /app/outputs/report.html

# Run live dashboard
docker run --env-file .env \
  -p 5000:5000 \
  -v /local/path/amazon_sales.csv:/app/data/amazon_sales.csv \
  amazon-insights \
  python run.py /app/data/amazon_sales.csv --dashboard
```

---

## Bugs Fixed

### SQL

| File | Bug | Fix |
|------|-----|-----|
| `sql.schema` | `DECIMAL(10,2)` too narrow for state-level totals | `DECIMAL(12,2)` |
| `datacleaning.sql` | No state normalisation — Bihar/BIHAR/bihar duplicated in charts | `UPDATE SET ship_state = UPPER(TRIM(...))` |
| `fulfillment_analysis.sql` | Integer division returns 0 for fractions in MySQL | `CAST(numerator AS DECIMAL(10,4))` |
| `market_expansion_model.sql` | `RANK()` defined and referenced in same `SELECT` (MySQL disallows) | Split into two CTEs |
| `market_expansion_model.sql` | Only 2 ranking pillars — weak signal | Added `avg_order_value` as 3rd pillar |

### Python

| File | Bug | Fix |
|------|-----|-----|
| `kpi_engine.py` | `COLUMN_MAP` missed `B2B` and `fulfilled-by` CSV columns | Added both columns |
| `kpi_engine.py` | `is_b2b` always 0 — real B2B column not read | Reads `B2B` column (TRUE/FALSE string) |
| `kpi_engine.py` | `avg_order_value` missing from `expansion_model` | Joined from per-state mean |
| `kpi_engine.py` | `by_fulfillment_method` used wrong column | Uses `fulfillment` (Fulfilment) column |
| `run.py` | `import schedule` at top-level — hard crash if not installed | Moved inside conditional branch |
| `run.py` | No way to launch dashboard from `run.py` | Added `--dashboard` flag |
| `Dockerfile` | Baked CSV into image at build time | CSV mounted at runtime with `-v` |
| `Dockerfile` | `watchdog` missing from pip install | Added to RUN command |

---

## Architecture

```
Raw CSV
  → kpi_engine.py   (clean + compute KPIs)
  → insights.py     (rule engine → ranked insights + actions)
  → report.py       (HTML email with embedded charts)
  → dashboard.py    (live browser dashboard, auto-refresh 60s)
  → run.py          (scheduler / file watcher / one-shot / dashboard)
```
