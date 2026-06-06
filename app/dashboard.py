"""
dashboard.py
Revenue Intelligence — Executive Dashboard
Dark-themed, with KPI cards, Plotly charts, and AI insights panel.
"""
import os
import sys
import threading
import time
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from flask import Flask, render_template_string
import kpi_engine, insights as ins_module

app = Flask(__name__)
CSV_PATH = "amazon_sales.csv"
_cache   = {}

PLOTLY_CFG = dict(displayModeBar=False, responsive=True)

# Dark theme layout applied to every Plotly chart
PLOTLY_LAYOUT = dict(
    font=dict(
        family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",
        color="#9ca3af",
        size=11,
    ),
    plot_bgcolor="#1a1d2e",
    paper_bgcolor="#1a1d2e",
    margin=dict(l=10, r=10, t=40, b=10),
    title_font=dict(color="#e2e8f0", size=13),
    xaxis=dict(
        gridcolor="#2a2d3e",
        linecolor="#2a2d3e",
        tickfont=dict(color="#6b7280", size=10),
    ),
    yaxis=dict(
        gridcolor="#2a2d3e",
        linecolor="#2a2d3e",
        tickfont=dict(color="#6b7280", size=10),
    ),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9ca3af", size=11),
    ),
)


def refresh_data():
    try:
        kpis, df = kpi_engine.run(CSV_PATH)
        _cache["kpis"]         = kpis
        _cache["insights"]     = ins_module.generate_insights(kpis)
        _cache["refreshed_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[Dashboard] Refreshed at {_cache['refreshed_at']}")
    except Exception as e:
        print(f"[Dashboard] Error: {e}")


def auto_refresh(interval=60):
    while True:
        time.sleep(interval)
        refresh_data()


def _html(fig):
    return pio.to_html(fig, full_html=False, config=PLOTLY_CFG)


def fig_trend(kpis):
    df = kpis["monthly_trend"].tail(12)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["year_month"], y=df["revenue"],
        fill="tozeroy",
        line=dict(color="#a78bfa", width=2.5),
        fillcolor="rgba(167,139,250,0.15)",
        name="Revenue",
    ))
    fig.update_layout(
        title="Revenue & Profit Trend",
        **PLOTLY_LAYOUT,
    )
    return _html(fig)


def fig_state(kpis):
    df = kpis["revenue_by_state"].head(15)
    fig = px.bar(
        df, x="revenue", y="ship_state", orientation="h",
        color="fulfillment_rate",
        color_continuous_scale=[[0, "#3b1f2b"], [0.5, "#7c3aed"], [1, "#a78bfa"]],
        title="Revenue & Fulfillment by State",
        labels={"revenue": "Revenue (₹)", "fulfillment_rate": "Fulfillment %"},
    )
    fig.update_layout(**PLOTLY_LAYOUT)
    fig.update_yaxes(autorange="reversed", gridcolor="#2a2d3e", tickfont=dict(color="#6b7280", size=10))
    return _html(fig)


def fig_category(kpis):
    df = kpis["revenue_by_category"]
    fig = go.Figure(data=[
        go.Bar(name="Revenue",     x=df["category"], y=df["revenue"],         marker_color="#60a5fa"),
        go.Bar(name="Avg Order ₹", x=df["category"], y=df["avg_order_value"], marker_color="#a78bfa"),
    ])
    fig.update_layout(barmode="group", title="Category Performance", **PLOTLY_LAYOUT)
    return _html(fig)


def fig_quadrant(kpis):
    df      = kpis["revenue_by_state"].head(25).copy()
    avg_ff  = kpis["fulfillment_rate"]
    avg_rev = df["revenue"].mean()

    def quadrant(row):
        if row["revenue"] > avg_rev and row["fulfillment_rate"] >= avg_ff:
            return "Star market"
        if row["revenue"] > avg_rev and row["fulfillment_rate"] < avg_ff:
            return "Revenue leakage"
        if row["revenue"] <= avg_rev and row["fulfillment_rate"] >= avg_ff:
            return "Expansion target"
        return "Low priority"

    df["quadrant"] = df.apply(quadrant, axis=1)
    color_map = {
        "Star market":      "#34d399",
        "Revenue leakage":  "#f87171",
        "Expansion target": "#fbbf24",
        "Low priority":     "#4b5563",
    }
    fig = px.scatter(
        df, x="revenue", y="fulfillment_rate",
        text="ship_state", color="quadrant",
        color_discrete_map=color_map,
        title="Fulfillment Quality vs Revenue — Market Quadrant",
        labels={"revenue": "Revenue (₹)", "fulfillment_rate": "Fulfillment %"},
    )
    fig.update_traces(textposition="top center", marker_size=10)
    fig.add_vline(x=avg_rev, line_dash="dash", line_color="#2a2d3e")
    fig.add_hline(y=avg_ff,  line_dash="dash", line_color="#2a2d3e")
    fig.update_layout(**PLOTLY_LAYOUT)
    return _html(fig)


def fig_fulfillment_method(kpis):
    df = kpis["by_fulfillment_method"]
    fig = go.Figure(data=[
        go.Bar(name="Revenue",          x=df["fulfillment"], y=df["revenue"],          marker_color="#60a5fa"),
        go.Bar(name="Fulfillment Rate", x=df["fulfillment"], y=df["fulfillment_rate"], marker_color="#34d399", yaxis="y2"),
    ])
    fig.update_layout(barmode="group", title="Amazon vs Merchant Fulfillment", **PLOTLY_LAYOUT)
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, tickfont=dict(color="#6b7280", size=10)))
    return _html(fig)


# ─── HTML Template ─────────────────────────────────────────────────────────────
# This is the full dark dashboard template.
# Variables injected via Jinja2:
#   total_revenue, total_orders, avg_order_value, fulfillment_rate,
#   b2b_share, insights, insight_count, refreshed_at,
#   trend, state, cat, quadrant, ff_method
TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="60">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Revenue Intelligence Dashboard</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: #0f1117;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      min-height: 100vh;
    }

    /* ── Header ── */
    .hdr {
      background: #1a1d2e;
      border-bottom: 1px solid #2a2d3e;
      padding: 14px 28px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .hdr-left { display: flex; align-items: center; gap: 12px; }
    .hdr-logo {
      width: 36px; height: 36px;
      background: linear-gradient(135deg, #7c3aed, #db2777);
      border-radius: 8px;
      display: flex; align-items: center; justify-content: center;
      font-size: 16px; flex-shrink: 0;
    }
    .hdr h1 { font-size: 16px; font-weight: 700; color: #fff; }
    .hdr h1 span { color: #a78bfa; }
    .hdr-sub { font-size: 11px; color: #6b7280; margin-top: 2px; }
    .hdr-right { display: flex; gap: 10px; align-items: center; }
    .date-pill {
      background: #1e2035; border: 1px solid #2a2d3e;
      padding: 6px 14px; border-radius: 20px;
      font-size: 12px; color: #a78bfa;
    }
    .refresh-note { font-size: 11px; color: #4b5563; }

    /* ── Layout ── */
    .main { padding: 20px 24px 40px; max-width: 1400px; }

    /* ── KPI Cards (top row) ── */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin-bottom: 14px;
    }
    .kpi-card {
      background: #1a1d2e;
      border: 1px solid #2a2d3e;
      border-radius: 12px;
      padding: 18px 20px;
      position: relative;
      overflow: hidden;
    }
    .kpi-icon {
      width: 34px; height: 34px; border-radius: 8px;
      display: flex; align-items: center; justify-content: center;
      font-size: 15px; margin-bottom: 14px;
    }
    .kpi-badge {
      position: absolute; top: 14px; right: 14px;
      font-size: 11px; font-weight: 700;
      padding: 3px 8px; border-radius: 12px;
    }
    .badge-up   { background: rgba(16,185,129,.15); color: #10b981; }
    .badge-down { background: rgba(239,68,68,.15);  color: #ef4444; }
    .badge-warn { background: rgba(245,158,11,.15); color: #f59e0b; }
    .kpi-label {
      font-size: 11px; color: #6b7280;
      text-transform: uppercase; letter-spacing: .05em;
      margin-bottom: 6px;
    }
    .kpi-val { font-size: 26px; font-weight: 700; line-height: 1.1; }
    .kpi-sub { font-size: 11px; color: #6b7280; margin-top: 4px; }

    /* ── Metric Row (secondary numbers) ── */
    .metric-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin-bottom: 14px;
    }
    .metric-card {
      background: #1a1d2e; border: 1px solid #2a2d3e;
      border-radius: 10px; padding: 14px 18px; text-align: center;
    }
    .metric-val { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
    .metric-label {
      font-size: 10px; text-transform: uppercase;
      letter-spacing: .08em; color: #6b7280;
    }

    /* ── Charts Row ── */
    .charts-row {
      display: grid;
      grid-template-columns: 1fr 340px;
      gap: 14px;
      margin-bottom: 14px;
    }
    .chart-card {
      background: #1a1d2e; border: 1px solid #2a2d3e;
      border-radius: 12px; padding: 20px;
    }
    .chart-title {
      font-size: 13px; font-weight: 600; color: #e2e8f0;
      margin-bottom: 14px; display: flex; align-items: center; gap: 8px;
    }

    /* ── Full-width chart cards ── */
    .chart-full {
      background: #1a1d2e; border: 1px solid #2a2d3e;
      border-radius: 12px; padding: 20px;
      margin-bottom: 14px;
    }

    /* ── Insights Section ── */
    .section-hdr {
      display: flex; align-items: center; gap: 10px;
      margin-bottom: 14px;
    }
    .section-title { font-size: 14px; font-weight: 600; color: #e2e8f0; }
    .section-count {
      background: #2a2d3e; color: #9ca3af;
      font-size: 11px; padding: 2px 8px; border-radius: 10px;
    }
    .insights-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
    }
    .insight-card {
      background: #1a1d2e; border: 1px solid #2a2d3e;
      border-radius: 10px; padding: 16px;
      display: flex; flex-direction: column;
    }
    .insight-top {
      display: flex; justify-content: space-between;
      align-items: flex-start; margin-bottom: 10px; gap: 6px; flex-wrap: wrap;
    }
    .insight-badges { display: flex; gap: 6px; flex-wrap: wrap; }

    /* Impact badges */
    .impact-badge {
      font-size: 10px; font-weight: 700; padding: 2px 8px;
      border-radius: 10px; text-transform: uppercase; letter-spacing: .04em;
    }
    .imp-high { background: rgba(239,68,68,.15); color: #f87171; border: 1px solid rgba(239,68,68,.25); }
    .imp-med  { background: rgba(245,158,11,.15); color: #fbbf24; border: 1px solid rgba(245,158,11,.25); }
    .imp-low  { background: rgba(16,185,129,.15); color: #34d399; border: 1px solid rgba(16,185,129,.25); }

    /* Category tag */
    .cat-badge {
      font-size: 10px; padding: 2px 8px; border-radius: 10px;
      background: #2a2d3e; color: #9ca3af;
    }

    .insight-title { font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 6px; }
    .insight-detail { font-size: 12px; color: #6b7280; line-height: 1.5; margin-bottom: 10px; flex: 1; }
    .insight-metric { font-size: 12px; color: #a78bfa; font-weight: 600; margin-bottom: 8px; }
    .insight-action {
      font-size: 11px; color: #9ca3af;
      border-top: 1px solid #2a2d3e; padding-top: 8px; line-height: 1.5;
    }
    .insight-action .action-label { color: #60a5fa; font-weight: 600; }

    /* ── Plotly overrides ── */
    .js-plotly-plot .plotly .main-svg { border-radius: 8px; }

    /* ── Footer ── */
    .footer {
      margin-top: 20px; font-size: 11px; color: #374151; text-align: center;
    }

    @media (max-width: 900px) {
      .kpi-grid { grid-template-columns: repeat(2, 1fr); }
      .metric-row { grid-template-columns: repeat(2, 1fr); }
      .charts-row { grid-template-columns: 1fr; }
      .insights-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

<!-- ── Header ── -->
<div class="hdr-left">
    <a href="/" style="text-decoration:none;display:flex;align-items:center;gap:12px">
      <div class="hdr-logo">📊</div>
      <div>
        <h1>Revenue <span>Intelligence</span></h1>
        <div class="hdr-sub">Executive Dashboard · Automated Analysis</div>
      </div>
    </a>
  </div>
  <div class="hdr-right">
    <div class="date-pill">📅 {{ refreshed_at }}</div>
    <div class="refresh-note">Auto-refresh 60s</div>
  </div>
</div>

<div class="main">

  <!-- ── KPI Cards ── -->
  <div class="kpi-grid">

    <!-- Total Revenue -->
    <div class="kpi-card">
      <div class="kpi-icon" style="background:#1e3a5f">
        <span style="color:#60a5fa;font-weight:700">₹</span>
      </div>
      <div class="kpi-badge badge-up">↑ Strong</div>
      <div class="kpi-label">Total Revenue</div>
      <div class="kpi-val" style="color:#60a5fa">
        ₹{{ '{:.2f}'.format(total_revenue / 100000) }}L
      </div>
      <div class="kpi-sub">Lifetime total from dataset</div>
    </div>

    <!-- Total Orders -->
    <div class="kpi-card">
      <div class="kpi-icon" style="background:#1a3a2e">
        <span style="color:#34d399">📦</span>
      </div>
      <div class="kpi-badge badge-up">↑ Growing</div>
      <div class="kpi-label">Total Orders</div>
      <div class="kpi-val" style="color:#34d399">
        {{ '{:,}'.format(total_orders) }}
      </div>
      <div class="kpi-sub">All order statuses</div>
    </div>

    <!-- Avg Order Value -->
    <div class="kpi-card">
      <div class="kpi-icon" style="background:#2d1f4e">
        <span style="color:#a78bfa">⚡</span>
      </div>
      <div class="kpi-badge badge-up">↑ Healthy</div>
      <div class="kpi-label">Avg Order Value</div>
      <div class="kpi-val" style="color:#a78bfa">
        ₹{{ '{:,.0f}'.format(avg_order_value) }}
      </div>
      <div class="kpi-sub">Revenue per order</div>
    </div>

    <!-- Fulfillment Rate -->
    {% if fulfillment_rate >= 85 %}
    <div class="kpi-card">
      <div class="kpi-icon" style="background:#1a3a2e">
        <span style="color:#34d399">✅</span>
      </div>
      <div class="kpi-badge badge-up">↑ On Target</div>
      <div class="kpi-label">Fulfillment Rate</div>
      <div class="kpi-val" style="color:#34d399">{{ '{:.1f}'.format(fulfillment_rate) }}%</div>
      <div class="kpi-sub">Target: 85% minimum</div>
    </div>
    {% else %}
    <div class="kpi-card">
      <div class="kpi-icon" style="background:#3b1f2b">
        <span style="color:#f87171">⚠️</span>
      </div>
      <div class="kpi-badge badge-warn">! Below Target</div>
      <div class="kpi-label">Fulfillment Rate</div>
      <div class="kpi-val" style="color:#fbbf24">{{ '{:.1f}'.format(fulfillment_rate) }}%</div>
      <div class="kpi-sub">Target: 85% minimum</div>
    </div>
    {% endif %}

  </div>

  <!-- ── Metric Row ── -->
  <div class="metric-row">
    <div class="metric-card">
      <div class="metric-val" style="color:#f87171">{{ '{:.1f}'.format(b2b_share) }}%</div>
      <div class="metric-label">B2B Revenue Share</div>
    </div>
    <div class="metric-card">
      <div class="metric-val" style="color:#60a5fa">{{ insight_count }}</div>
      <div class="metric-label">Insights Generated</div>
    </div>
    <div class="metric-card">
      <div class="metric-val" style="color:#a78bfa">
        {% set high_count = insights | selectattr('impact', 'equalto', 'High') | list | length %}
        {{ high_count }}
      </div>
      <div class="metric-label">High Impact Alerts</div>
    </div>
    <div class="metric-card">
      <div class="metric-val" style="color:#34d399">
        {% set low_count = insights | selectattr('impact', 'equalto', 'Low') | list | length %}
        {{ insight_count - low_count }}
      </div>
      <div class="metric-label">Actions Prioritized</div>
    </div>
  </div>

  <!-- ── Charts Row: Trend + Quadrant ── -->
  <div class="charts-row">
    <div class="chart-card">
      <div class="chart-title">📈 Revenue Trend</div>
      {{ trend | safe }}
    </div>
    <div class="chart-card">
      <div class="chart-title">🗂️ Revenue by State</div>
      {{ state | safe }}
    </div>
  </div>

  <!-- ── Full width: Category + Fulfillment ── -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">
    <div class="chart-full">
      <div class="chart-title">📊 Category Performance</div>
      {{ cat | safe }}
    </div>
    <div class="chart-full">
      <div class="chart-title">🚚 Fulfillment Method</div>
      {{ ff_method | safe }}
    </div>
  </div>

  <!-- ── Full width: Quadrant ── -->
  <div class="chart-full">
    <div class="chart-title">🎯 Market Quadrant — Fulfillment vs Revenue</div>
    {{ quadrant | safe }}
  </div>

  <!-- ── Insights Panel ── -->
  <div style="margin-top:20px">
    <div class="section-hdr">
      <div class="section-title">Automated Insights &amp; Actions</div>
      <div class="section-count">{{ insight_count }} insights</div>
    </div>

    <div class="insights-grid">
      {% for ins in insights %}

      {# Choose card border color by impact #}
      {% if ins.impact == 'High' %}
        {% set border_color = '#3b1f2b' %}
        {% set badge_class  = 'imp-high' %}
      {% elif ins.impact == 'Medium' %}
        {% set border_color = '#3b2e1a' %}
        {% set badge_class  = 'imp-med' %}
      {% else %}
        {% set border_color = '#1a2e2b' %}
        {% set badge_class  = 'imp-low' %}
      {% endif %}

      <div class="insight-card" style="border-color: {{ border_color }}">
        <div class="insight-top">
          <div class="insight-badges">
            <span class="impact-badge {{ badge_class }}">{{ ins.impact }}</span>
            <span class="cat-badge">{{ ins.category }}</span>
          </div>
        </div>
        <div class="insight-title">{{ ins.title }}</div>
        <div class="insight-detail">{{ ins.detail }}</div>
        <div class="insight-metric">{{ ins.metric_value }}</div>
        <div class="insight-action">
          <span class="action-label">[Action]</span> {{ ins.action }}
        </div>
      </div>

      {% endfor %}
    </div>
  </div>

  <div class="footer">
    {% if gemini_report %}
<div style="margin:0 24px 24px;background:#0f1117;border:1px solid #1e2433;border-radius:16px;overflow:hidden;">
  <div style="background:linear-gradient(135deg,rgba(167,139,250,0.12),rgba(96,165,250,0.08));border-bottom:1px solid #1e2433;padding:20px 24px;display:flex;align-items:center;gap:14px;">
    <div style="width:40px;height:40px;border-radius:10px;background:linear-gradient(135deg,#a78bfa,#60a5fa);display:flex;align-items:center;justify-content:center;font-size:20px;">✦</div>
    <div>
      <div style="font-size:16px;font-weight:700;color:#e2e8f0;">AI Founder Action Plan</div>
      <div style="font-size:12px;color:#64748b;margin-top:2px;">Gemini 2.5 Flash · Google Cloud · MongoDB Atlas</div>
    </div>
  </div>
  <div style="padding:24px;font-size:14px;color:#94a3b8;line-height:1.8;white-space:pre-wrap;">{{ gemini_report }}</div>
</div>
{% else %}
<div style="margin:0 24px 24px;background:#0f1117;border:1px solid #1e2433;border-radius:16px;padding:40px;text-align:center;color:#64748b;">
  <div style="font-size:32px;margin-bottom:12px;">✦</div>
  <div>Gemini report not available. Re-upload your CSV to generate a fresh AI action plan.</div>
</div>
{% endif %}

Revenue Intelligence System · Automated Analysis · Refreshes every 60s
  </div>

</div>
</body>
</html>"""


@app.route("/")
def index():
    kpis = _cache.get("kpis")
    if not kpis:
        return "<h2 style='padding:40px;color:#fff;background:#0f1117'>Loading... refresh in a moment.</h2>"
    return render_template_string(
        TEMPLATE,
        total_revenue    = kpis["total_revenue"],
        total_orders     = kpis["total_orders"],
        avg_order_value  = kpis["avg_order_value"],
        fulfillment_rate = kpis["fulfillment_rate"],
        b2b_share        = kpis["b2b_revenue_share"],
        insights         = _cache["insights"],
        insight_count    = len(_cache["insights"]),
        refreshed_at     = _cache.get("refreshed_at", "on demand"),
        trend            = fig_trend(kpis),
        state            = fig_state(kpis),
        cat              = fig_category(kpis),
        quadrant         = fig_quadrant(kpis),
        ff_method        = fig_fulfillment_method(kpis),
    )


def render_dashboard(kpis: dict, insights: list, gemini_report: str = None, filename: str = "", job_id: str = None) -> str:
    """
    Called by main.py's /dashboard/{report_id} route.
    Signature unchanged — main.py needs zero edits.
    """
    from jinja2 import Template
    if not gemini_report and job_id:
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from database import get_database
            db = get_database()
            report_doc = db.reports.find_one({"job_id": job_id})
            if report_doc:
                gemini_report = report_doc.get("report_text", "")
        except Exception:
            pass
    t = Template(TEMPLATE)
    return t.render(
        total_revenue    = kpis.get("total_revenue", 0),
        total_orders     = kpis.get("total_orders", 0),
        avg_order_value  = kpis.get("avg_order_value", 0),
        fulfillment_rate = kpis.get("fulfillment_rate", 0),
        b2b_share        = kpis.get("b2b_revenue_share", 0),
        insights         = insights,
        insight_count    = len(insights) if insights else 0,
        refreshed_at     = "just now",
        filename         = filename or "sales_data.csv",
        gemini_report    = gemini_report,
        trend            = fig_trend(kpis) if "monthly_trend" in kpis else "",
        state            = fig_state(kpis) if "revenue_by_state" in kpis else "",
        cat              = fig_category(kpis) if "revenue_by_category" in kpis else "",
        quadrant         = fig_quadrant(kpis) if "revenue_by_state" in kpis else "",
        ff_method        = fig_fulfillment_method(kpis) if "by_fulfillment_method" in kpis else "",
    )


if __name__ == "__main__":
    CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "Amazon Sale Report.csv"
    print(f"[Dashboard] Loading {CSV_PATH}...")
    refresh_data()
    threading.Thread(target=auto_refresh, args=(60,), daemon=True).start()
    print("[Dashboard] → http://localhost:5000")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)