# Revenue Intelligence — AI-Powered Sales Analytics for D2C Founders

> Upload any sales CSV → get a founder-ready analytics report with AI insights in 30 seconds.

**Live:** [data-driven-profitability-and-market.onrender.com](https://data-driven-profitability-and-market.onrender.com)  &nbsp;|&nbsp; **Stack:** FastAPI · Claude AI · Plotly · SQLite · Docker · Razorpay · Render

---

## What It Does

Indian D2C founders selling on Amazon, Flipkart, Shopify, or Meesho upload their sales CSV and instantly get:

- **Revenue by state** — which markets are driving growth vs bleeding money
- **Fulfillment rate analysis** — where orders are failing and why
- **Category performance** — which SKUs to scale, which to cut
- **Market quadrant map** — expansion targets with zero logistics risk
- **AI-generated report** — Claude reads your actual numbers and writes a founder-ready action plan

No data engineering. No waiting for an analyst. No generic advice.

---

## Screenshots
<img width="1280" height="832" alt="dash" src="https://github.com/user-attachments/assets/eda8ad37-603c-4903-845e-2722910418cb" />


---

## Architecture

```
User (Browser)
      │
      ▼
┌─────────────────────────────────────────┐
│           FastAPI (Uvicorn/ASGI)        │  ← REST API, async routing
│                                         │
│  /upload     → KPI Engine              │
│  /dashboard  → Plotly Chart Renderer   │
│  /pricing    → Razorpay Checkout       │
│  /login      → Session Auth (cookie)   │
└──────────┬──────────────────┬──────────┘
           │                  │
           ▼                  ▼
┌──────────────────┐  ┌───────────────────┐
│   KPI Engine     │  │   Claude API      │
│  (pandas)        │  │  (AI Insights)    │
│                  │  │                   │
│ • Revenue/state  │  │ Rule engine runs  │
│ • Fulfillment %  │  │ first → top 3     │
│ • Category perf  │  │ insights + KPI    │
│ • MoM trends     │  │ snapshot sent to  │
│ • Market quad    │  │ Claude → founder  │
└──────────────────┘  │ prose generated   │
                       └───────────────────┘
           │
           ▼
┌──────────────────┐
│  SQLite + ORM    │  ← Users, Subscriptions, Reports
│  (SQLAlchemy)    │
└──────────────────┘
           │
           ▼
┌──────────────────┐
│  Docker Container│  → Deployed on Render
└──────────────────┘
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Backend | FastAPI (Python) | Async, fast, auto-docs |
| AI Layer | Anthropic Claude API | Founder-language insights |
| Data Engine | pandas + custom KPI engine | Flexible CSV processing |
| Charts | Plotly | Interactive, embeddable |
| Auth | itsdangerous + bcrypt | Signed cookies, hashed passwords |
| Payments | Razorpay | UPI + Cards for Indian market |
| Database | SQLite + SQLAlchemy ORM | Zero-config, production-ready for MVP |
| Column Detection | Fuzzy matching (difflib) | Works with any CSV format |
| Deployment | Docker + Render | One-command deploy |

---

## Key Features

**Smart CSV ingestion** — fuzzy column auto-detection maps any CSV format (Amazon, Flipkart, Shopify, Meesho, custom) to a unified schema. No manual column mapping required.

**Hybrid AI insights** — rule-based engine runs first (never fails, no API cost), then Claude API enriches the top 3 findings into a founder-ready prose report. Falls back gracefully if API key is missing.

**Subscription gate** — users without active subscriptions are blocked from `/upload` and `/dashboard`. Razorpay payment activates access instantly via webhook verification (HMAC signature check).

**Stateless report store** — each upload generates a short report ID (`/dashboard/a3f9c1b2`). Reports live in-memory for the session. Phase 2 will persist to PostgreSQL.

---

## Project Structure

```
automation/
├── Dockerfile
└── app/
    ├── main.py           ← FastAPI app, all routes
    ├── kpi_engine.py     ← KPI computation (revenue, fulfillment, trends)
    ├── insights.py       ← Rule-based insight engine (fallback)
    ├── ai_insights.py    ← Claude API hybrid insight generation
    ├── column_mapper.py  ← Fuzzy CSV column auto-detection
    ├── dashboard.py      ← Plotly chart rendering + HTML template
    ├── models.py         ← SQLAlchemy: User, Subscription, Report
    ├── database.py       ← SQLite init
    ├── dependencies.py   ← Auth + subscription gate middleware
    ├── requirements.txt
    └── templates/
        ├── index.html    ← Landing page
        ├── upload.html   ← CSV upload + column mapping UI
        ├── pricing.html  ← Razorpay checkout
        ├── login.html
        └── signup.html
```

---

## Run Locally

```bash
# 1. Clone
git clone https://github.com/gitdev77/Data-Driven-Profitability-and-Market-Expansion-Decision-System.git
cd Data-Driven-Profitability-and-Market-Expansion-Decision-System/app

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
export SECRET_KEY="your-secret-key"
export RAZORPAY_KEY_ID="your-razorpay-key"
export RAZORPAY_KEY_SECRET="your-razorpay-secret"
export ANTHROPIC_API_KEY="your-claude-key"   # optional — fallback works without it

# 4. Run
uvicorn main:app --reload --port 8000

# Open http://localhost:8000
```

**Docker:**
```bash
docker build -t revenue-intel .
docker run -p 8000:8000 \
  -e SECRET_KEY=xxx \
  -e RAZORPAY_KEY_ID=xxx \
  -e RAZORPAY_KEY_SECRET=xxx \
  revenue-intel
```

---

## Pricing

| Plan | Price | Access |
|---|---|---|
| Monthly | ₹2,000/month | 30 days |
| 6 Months | ₹10,000 | 180 days · save ₹2,000 |

Payments via Razorpay — UPI, Cards, NetBanking, GPay accepted.

---

## Roadmap

- [x] CSV upload with fuzzy column detection
- [x] KPI engine (revenue, fulfillment, trends, market quadrant)
- [x] Rule-based insight engine
- [x] Claude AI hybrid insight generation
- [x] Interactive Plotly dashboard
- [x] User auth (signup/login/logout)
- [x] Razorpay subscription payments
- [x] Docker + Render deployment
- [ ] Redis caching layer (dashboard load time < 200ms)
- [ ] PostgreSQL migration (persistent reports)
- [ ] Background job queue (async Claude API calls)
- [ ] Multi-platform support (Meesho, Shopify native connectors)
- [ ] Month-over-month comparison (baseline vs current)

---

## Resume Bullet

> Built and deployed a full-stack AI SaaS product — **Revenue Intelligence** — using FastAPI, Claude API, Plotly, SQLAlchemy, and Docker; features fuzzy CSV ingestion, hybrid rule+AI insight generation, Razorpay subscription payments, and session-based auth; live at [data-driven-profitability-and-market.onrender.com](https://data-driven-profitability-and-market.onrender.com)

---

## About

Built by **Devansh** — B.Tech Engineering Physics, NIT Hamirpur  
Targeting: D2C founders selling on Indian marketplaces who need analyst-grade insights without hiring an analyst.

---

*© 2025 Revenue Intelligence · Built for Indian D2C founders*
