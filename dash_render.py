"""
dash_render.py
Revenue Intelligence — Dashboard
"""

import os
import sys
import threading
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from flask import Flask, render_template_string

import insights as ins_module
import kpi_engine

app = Flask(__name__)
CSV_PATH = "amazon_sales.csv"
_cache = {}

PLOTLY_CFG = dict(displayModeBar=False, responsive=True)
PLOTLY_LAYOUT = dict(
    height=320,
    font=dict(
        family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",
        color="#9ca3af",
        size=11,
    ),
    plot_bgcolor="#1a1d2e",
    paper_bgcolor="#1a1d2e",
    margin=dict(l=10, r=10, t=40, b=30),
    title_font=dict(color="#e2e8f0", size=13),
    xaxis=dict(gridcolor="#2a2d3e", linecolor="#2a2d3e", tickfont=dict(color="#6b7280", size=10)),
    yaxis=dict(gridcolor="#2a2d3e", linecolor="#2a2d3e", tickfont=dict(color="#6b7280", size=10)),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#9ca3af", size=11)),
)


def _to_df(val):
    """MongoDB returns lists; kpi_engine returns DataFrames. Handle both."""
    if isinstance(val, pd.DataFrame):
        return val
    return pd.DataFrame(val) if val else pd.DataFrame()


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
    df = _to_df(kpis.get("monthly_trend")).tail(12)
    if df.empty:
        return ""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["year_month"], y=df["revenue"],
        fill="tozeroy",
        line=dict(color="#a78bfa", width=2.5),
        fillcolor="rgba(167,139,250,0.15)",
        name="Revenue",
    ))
    fig.update_layout(title="Revenue Trend", **PLOTLY_LAYOUT)
    return _html(fig)


def fig_state(kpis):
    df = _to_df(kpis.get("revenue_by_state")).head(15)
    if df.empty:
        return ""
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
    df = _to_df(kpis.get("revenue_by_category"))
    if df.empty:
        return ""
    fig = go.Figure(data=[
        go.Bar(name="Revenue",     x=df["category"], y=df["revenue"],         marker_color="#60a5fa"),
        go.Bar(name="Avg Order ₹", x=df["category"], y=df["avg_order_value"], marker_color="#a78bfa"),
    ])
    fig.update_layout(barmode="group", title="Category Performance", **PLOTLY_LAYOUT)
    return _html(fig)


def fig_quadrant(kpis):
    df = _to_df(kpis.get("revenue_by_state")).head(25).copy()
    if df.empty:
        return ""
    avg_ff  = kpis.get("fulfillment_rate", 0)
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
    df = _to_df(kpis.get("by_fulfillment_method"))
    if df.empty:
        return ""
    fig = go.Figure(data=[
        go.Bar(name="Revenue",          x=df["fulfillment"], y=df["revenue"],          marker_color="#60a5fa"),
        go.Bar(name="Fulfillment Rate", x=df["fulfillment"], y=df["fulfillment_rate"], marker_color="#34d399", yaxis="y2"),
    ])
    fig.update_layout(
        barmode="group", title="Amazon vs Merchant Fulfillment",
        yaxis2=dict(overlaying="y", side="right", showgrid=False, tickfont=dict(color="#6b7280", size=10)),
        **PLOTLY_LAYOUT,
    )
    return _html(fig)


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="60">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Revenue Intelligence Dashboard</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f1117; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }
    .hdr { background: #1a1d2e; border-bottom: 1px solid #2a2d3e; padding: 14px 28px; display: flex; justify-content: space-between; align-items: center; }
    .hdr h1 { font-size: 16px; font-weight: 700; color: #fff; }
    .hdr h1 span { color: #a78bfa; }
    .hdr-sub { font-size: 11px; color: #6b7280; margin-top: 2px; }
    .date-pill { background: #1e2035; border: 1px solid #2a2d3e; padding: 6px 14px; border-radius: 20px; font-size: 12px; color: #a78bfa; }
    .main { padding: 20px 24px 40px; }
    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 14px; }
    .kpi-card { background: #1a1d2e; border: 1px solid #2a2d3e; border-radius: 12px; padding: 18px 20px; }
    .kpi-label { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }
    .kpi-val { font-size: 26px; font-weight: 700; line-height: 1.1; }
    .kpi-sub { font-size: 11px; color: #6b7280; margin-top: 4px; }
    .charts-row { display: grid; grid-template-columns: 1fr 340px; gap: 14px; margin-bottom: 14px; }
    .chart-card { background: #1a1d2e; border: 1px solid #2a2d3e; border-radius: 12px; padding: 20px; }
    .chart-full { background: #1a1d2e; border: 1px solid #2a2d3e; border-radius: 12px; padding: 20px; margin-bottom: 14px; }
    .chart-title { font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 14px; }
    .section-hdr { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
    .section-title { font-size: 14px; font-weight: 600; color: #e2e8f0; }
    .section-count { background: #2a2d3e; color: #9ca3af; font-size: 11px; padding: 2px 8px; border-radius: 10px; }
    .insights-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
    .insight-card { background: #1a1d2e; border: 1px solid #2a2d3e; border-radius: 10px; padding: 16px; display: flex; flex-direction: column; }
    .impact-badge { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; text-transform: uppercase; }
    .imp-high { background: rgba(239,68,68,.15); color: #f87171; border: 1px solid rgba(239,68,68,.25); }
    .imp-med  { background: rgba(245,158,11,.15); color: #fbbf24; border: 1px solid rgba(245,158,11,.25); }
    .imp-low  { background: rgba(16,185,129,.15); color: #34d399; border: 1px solid rgba(16,185,129,.25); }
    .cat-badge { font-size: 10px; padding: 2px 8px; border-radius: 10px; background: #2a2d3e; color: #9ca3af; }
    .insight-title { font-size: 13px; font-weight: 600; color: #e2e8f0; margin: 8px 0 6px; }
    .insight-detail { font-size: 12px; color: #6b7280; line-height: 1.5; margin-bottom: 10px; flex: 1; }
    .insight-metric { font-size: 12px; color: #a78bfa; font-weight: 600; margin-bottom: 8px; }
    .insight-action { font-size: 11px; color: #9ca3af; border-top: 1px solid #2a2d3e; padding-top: 8px; line-height: 1.5; }
    .footer { margin-top: 20px; font-size: 11px; color: #374151; text-align: center; }
    @media (max-width: 900px) {
      .kpi-grid { grid-template-columns: repeat(2, 1fr); }
      .charts-row { grid-template-columns: 1fr; }
      .insights-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

<div class="hdr">
  <div>
    <h1>Revenue <span>Intelligence</span></h1>
    <div class="hdr-sub">Executive Dashboard · Automated Analysis</div>
  </div>
  <div class="date-pill">{{ refreshed_at }}</div>
</div>

<div class="main">

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Total Revenue</div>
      <div class="kpi-val" style="color:#60a5fa">₹{{ '{:.2f}'.format(total_revenue / 100000) }}L</div>
      <div class="kpi-sub">Lifetime total</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Total Orders</div>
      <div class="kpi-val" style="color:#34d399">{{ '{:,}'.format(total_orders) }}</div>
      <div class="kpi-sub">All statuses</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Avg Order Value</div>
      <div class="kpi-val" style="color:#a78bfa">₹{{ '{:,.0f}'.format(avg_order_value) }}</div>
      <div class="kpi-sub">Revenue per order</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Fulfillment Rate</div>
      <div class="kpi-val" style="color:{% if fulfillment_rate >= 85 %}#34d399{% else %}#f87171{% endif %}">
        {{ '{:.1f}'.format(fulfillment_rate) }}%
      </div>
      <div class="kpi-sub">Target: 85%</div>
    </div>
  </div>

  <div class="charts-row">
    <div class="chart-card">
      <div class="chart-title">📈 Revenue Trend</div>
      {{ trend | safe }}
    </div>
    <div class="chart-card">
      <div class="chart-title">🗺️ Revenue by State</div>
      {{ state | safe }}
    </div>
  </div>

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

  <div class="chart-full">
    <div class="chart-title">🎯 Market Quadrant</div>
    {{ quadrant | safe }}
  </div>

  {% if gemini_report %}
  <div style="margin:20px 0;background:#1a1d2e;border:1px solid #2a2d3e;border-radius:16px;overflow:hidden;">
    <div style="background:linear-gradient(135deg,rgba(167,139,250,0.12),rgba(96,165,250,0.08));border-bottom:1px solid #2a2d3e;padding:20px 24px;display:flex;align-items:center;gap:14px;">
      <div style="width:40px;height:40px;border-radius:10px;background:linear-gradient(135deg,#a78bfa,#60a5fa);display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0;">✦</div>
      <div>
        <div style="font-size:16px;font-weight:700;color:#e2e8f0;">AI Founder Action Plan</div>
        <div style="font-size:12px;color:#6b7280;margin-top:2px;">Gemini 2.5 Flash · Google Cloud Agent Platform · MongoDB Atlas</div>
      </div>
    </div>
    <div style="padding:24px;font-size:14px;color:#94a3b8;line-height:1.8;white-space:pre-wrap;">{{ gemini_report }}</div>
  </div>
  {% endif %}

  <div style="margin-top:20px">
    <div class="section-hdr">
      <div class="section-title">Automated Insights &amp; Actions</div>
      <div class="section-count">{{ insight_count }} insights</div>
    </div>
    <div class="insights-grid">
      {% for ins in insights %}
      {% if ins.impact == 'High' %}{% set badge_class = 'imp-high' %}{% set border_color = '#3b1f2b' %}
      {% elif ins.impact == 'Medium' %}{% set badge_class = 'imp-med' %}{% set border_color = '#3b2e1a' %}
      {% else %}{% set badge_class = 'imp-low' %}{% set border_color = '#1a2e2b' %}{% endif %}
      <div class="insight-card" style="border-color:{{ border_color }}">
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <span class="impact-badge {{ badge_class }}">{{ ins.impact }}</span>
          <span class="cat-badge">{{ ins.category }}</span>
        </div>
        <div class="insight-title">{{ ins.title }}</div>
        <div class="insight-detail">{{ ins.detail }}</div>
        <div class="insight-metric">{{ ins.metric_value }}</div>
        <div class="insight-action"><span style="color:#60a5fa;font-weight:600">[Action]</span> {{ ins.action }}</div>
      </div>
      {% endfor %}
    </div>
  </div>

  <div class="footer">Revenue Intelligence · Automated Analysis · refreshes every 60s</div>
</div>
</body>
</html>"""


def render_dashboard(kpis: dict, insights: list, gemini_report: str = None, filename: str = "", job_id: str = None) -> str:
    from jinja2 import Template

    if not gemini_report and job_id:
        try:
            from database import get_database
            db = get_database()
            report_doc = db.reports.find_one({"job_id": job_id})
            if report_doc:
                gemini_report = report_doc.get("report_text", "")
        except Exception:
            pass

    class _Ins:
        def __init__(self, d):
            self.title        = d.get("title", "")
            self.detail       = d.get("detail", "")
            self.impact       = d.get("impact", "Low")
            self.action       = d.get("action", "")
            self.category     = d.get("category", "")
            self.metric_value = d.get("metric_value", "")

    safe_insights = [
        i if hasattr(i, "title") else _Ins(i)
        for i in (insights or [])
    ]

    t = Template(TEMPLATE)
    return t.render(
        total_revenue    = kpis.get("total_revenue", 0),
        total_orders     = kpis.get("total_orders", 0),
        avg_order_value  = kpis.get("avg_order_value", 0),
        fulfillment_rate = kpis.get("fulfillment_rate", 0),
        b2b_share        = kpis.get("b2b_revenue_share", 0),
        insights         = safe_insights,
        insight_count    = len(safe_insights),
        refreshed_at     = "just now",
        gemini_report    = gemini_report or "",
        trend            = fig_trend(kpis) if kpis.get("monthly_trend") else "",
        state            = fig_state(kpis) if kpis.get("revenue_by_state") else "",
        cat              = fig_category(kpis) if kpis.get("revenue_by_category") else "",
        quadrant         = fig_quadrant(kpis) if kpis.get("revenue_by_state") else "",
        ff_method        = fig_fulfillment_method(kpis) if kpis.get("by_fulfillment_method") else "",
    )


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
        refreshed_at     = _cache.get("refreshed_at", "just now"),
        gemini_report    = "",
        trend            = fig_trend(kpis),
        state            = fig_state(kpis),
        cat              = fig_category(kpis),
        quadrant         = fig_quadrant(kpis),
        ff_method        = fig_fulfillment_method(kpis),
    )


if __name__ == "__main__":
    CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "amazon_sales.csv"
    print(f"[Dashboard] Loading {CSV_PATH}...")
    refresh_data()
    threading.Thread(target=auto_refresh, args=(60,), daemon=True).start()
    print("[Dashboard] → http://localhost:5000")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)