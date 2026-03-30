# Data-Driven Profitability & Market Expansion — Automated Insight System

> **Amazon India Sales Analytics** — SQL pipeline + Python automation that ingests raw sales data, detects anomalies, generates ranked business insights, and delivers HTML reports and a live dashboard automatically.

---

## What this does

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
├── datacleaning.sql           SQL: audit + fix case inconsistency, null handling
├── kpi_analysis.sql           SQL: revenue by state, AOV, revenue share %
├── fulfillment_analysis.sql   SQL: fulfillment rate by state
├── market_expansion_model.sql SQL: composite market scoring (rank + fulfillment)
│
├── kpi_engine.py              Python: loads CSV, computes all KPIs (ports SQL logic)
├── insights.py                Python: rule engine → ranked insights + action table
├── report.py                  Python: builds HTML email report with embedded charts
├── dashboard.py               Python: live browser dashboard (Flask + Plotly)
└── run.py                     Python: entry point — one-shot / scheduler / file watcher
```

---

## Dataset

Amazon India sales data with columns:
`order_id`, `order_date`, `status`, `fulfillment` (Amazon/Merchant), `sales_channel`,
`ship_city`, `ship_state`, `category`, `quantity`, `amount`, `b2b_flag`

**Key data quality fix applied:** `ship_state` values were stored inconsistently
(e.g. `Bihar`, `bihar`, `BIHAR` as separate rows). The cleaning pipeline normalises
all state names to UPPER CASE before any aggregation.

---

## Analytical Framework

### 1. Revenue Share by State
Identifies high-contributing markets and concentration risk.

### 2. Fulfillment Quality Analysis
Tracks operational efficiency across states and fulfillment methods (Amazon FBA vs Merchant).

### 3. Market Quadrant Model
Classifies every state into:
- **Star markets** — high revenue, high fulfillment (protect)
- **Revenue leakage** — high revenue, low fulfillment (fix urgently)
- **Expansion targets** — low revenue, high fulfillment (scale with low risk)
- **Low priority** — low on both (monitor only)

### 4. Composite Expansion Score
Ports the SQL `RANK() OVER` logic into Python — scores every state by
`revenue_rank + fulfillment_rank` to surface the best expansion candidates.

### 5. Automated Insight Rules
8 rule functions that generate ranked findings:
- Revenue concentration risk
- Month-over-month alerts
- Low-fulfillment high-revenue state detection
- Expansion opportunity identification
- Category underperformer detection
- B2B revenue opportunity sizing
- Amazon vs Merchant fulfillment gap
- Risk-free scaling markets

---

## Setup

```bash
pip install pandas matplotlib flask plotly schedule watchdog
```

Update `COLUMN_MAP` in `kpi_engine.py` if your CSV headers differ from the defaults.

---

## Usage

```bash
# Run once — generates report.html
python run.py amazon_sales.csv

# Run + email the report (set env vars first)
export SMTP_USER="your@gmail.com"
export SMTP_PASS="your-app-password"
python run.py amazon_sales.csv --email you@gmail.com

# Schedule daily at 8 AM
python run.py amazon_sales.csv --email you@gmail.com --schedule

# Auto-trigger when new CSV is dropped
python run.py amazon_sales.csv --watch

# Start live dashboard
python dashboard.py amazon_sales.csv
# → open http://localhost:5000
```

---

## Business Outcome

Transforms raw Amazon sales exports into an automated decision-support system.
A non-technical stakeholder receives a daily email with the top insights and
exact actions — no Tableau licence, no manual analysis, no dashboard reading required.

---

## Architecture

```
Raw CSV
  → kpi_engine.py   (clean + compute KPIs)
  → insights.py     (rule engine → ranked insights + actions)
  → report.py       (HTML email with embedded charts)
  → dashboard.py    (live browser dashboard, auto-refresh)
  → run.py          (scheduler / file watcher / one-shot)
```
