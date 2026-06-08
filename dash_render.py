"""
dashboard.py
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
    font_family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=10, r=10, t=40, b=10),
)


def _to_df(val):
    """MongoDB returns lists; kpi_engine returns DataFrames. Handle both."""
    if isinstance(val, pd.DataFrame):
        return val
    return pd.DataFrame(val) if val else pd.DataFrame()


def refresh_data() -> None:
    try:
        kpis, _df = kpi_engine.run(CSV_PATH)
        _cache["kpis"] = kpis
        _cache["insights"] = ins_module.generate_insights(kpis)
        _cache["refreshed_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[Dashboard] Refreshed at {_cache['refreshed_at']}")
    except Exception as e:
        print(f"[Dashboard] Error: {e}")


def auto_refresh(interval: int = 60) -> None:
    while True:
        time.sleep(interval)
        refresh_data()


def _html(fig) -> str:
    return pio.to_html(fig, full_html=False, config=PLOTLY_CFG)


def fig_trend(kpis: dict) -> str:
    df = _to_df(kpis.get("monthly_trend")).tail(12)
    if df.empty:
        return ""
    fig = px.area(
        df, x="year_month", y="revenue",
        title="Monthly Revenue Trend",
        color_discrete_sequence=["#185FA5"],
    )
    fig.update_layout(**PLOTLY_LAYOUT)
    fig.update_traces(line_width=2.5)
    return _html(fig)


def fig_state(kpis: dict) -> str:
    df = _to_df(kpis.get("revenue_by_state")).head(15)
    if df.empty:
        return ""
    fig = px.bar(
        df, x="revenue", y="ship_state", orientation="h",
        title="Revenue by State",
        color_discrete_sequence=["#185FA5"],
    )
    fig.update_layout(**PLOTLY_LAYOUT)
    return _html(fig)


def fig_category(kpis: dict) -> str:
    df = _to_df(kpis.get("revenue_by_category"))
    if df.empty:
        return ""
    fig = go.Figure(data=[
        go.Bar(name="Revenue",     x=df["category"], y=df["revenue"],         marker_color="#185FA5"),
        go.Bar(name="Avg Order ₹", x=df["category"], y=df["avg_order_value"], marker_color="#EF9F27"),
    ])
    fig.update_layout(barmode="group", title="Category Performance", **PLOTLY_LAYOUT)
    return _html(fig)


def fig_quadrant(kpis: dict) -> str:
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
        "Star market":      "#1D9E75",
        "Revenue leakage":  "#E24B4A",
        "Expansion target": "#EF9F27",
        "Low priority":     "#B4B2A9",
    }
    fig = px.scatter(
        df, x="revenue", y="fulfillment_rate",
        text="ship_state", color="quadrant",
        color_discrete_map=color_map,
        title="Fulfillment Quality vs Revenue — Market Quadrant",
        labels={"revenue": "Revenue (₹)", "fulfillment_rate": "Fulfillment %"},
    )
    fig.update_traces(
        textposition="top center", marker_size=10, mode="markers",
        hovertemplate="<b>%{text}</b><br>Revenue: ₹%{x:,.0f}<br>Fulfillment: %{y:.1f}%<extra></extra>",
    )
    fig.add_vline(x=avg_rev, line_dash="dash", line_color="#aaa")
    fig.add_hline(y=avg_ff,  line_dash="dash", line_color="#aaa")
    fig.update_layout(**PLOTLY_LAYOUT)
    return _html(fig)


def fig_fulfillment_method(kpis: dict) -> str:
    df = _to_df(kpis.get("by_fulfillment_method"))
    if df.empty:
        return ""
    fig = go.Figure(data=[
        go.Bar(name="Revenue",          x=df["fulfillment"], y=df["revenue"],          marker_color="#185FA5"),
        go.Bar(name="Fulfillment Rate", x=df["fulfillment"], y=df["fulfillment_rate"], marker_color="#1D9E75", yaxis="y2"),
    ])
    fig.update_layout(
        barmode="group", title="Amazon vs Merchant Fulfillment",
        yaxis2=dict(overlaying="y", side="right", showgrid=False),
        **PLOTLY_LAYOUT,
    )
    return _html(fig)


TEMPLATE = """<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta http-equiv="refresh" content="60">
<title>Revenue Intelligence Dashboard</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f5f7}
  .hdr{background:#1a1a2e;color:#fff;padding:18px 28px;display:flex;justify-content:space-between;align-items:center}
  .hdr h1{font-size:17px;font-weight:700}
  .sub{font-size:11px;color:#aab}
  .kpi-row{display:flex;gap:12px;padding:18px 24px;flex-wrap:wrap}
  .kc{background:#fff;border-radius:10px;padding:14px 18px;flex:1;min-width:130px;box-shadow:0 1px 4px rgba(0,0,0,.07)}
  .kc .lbl{font-size:11px;color:#888;margin-bottom:5px}
  .kc .val{font-size:22px;font-weight:700}
  .g2{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:0 24px 14px}
  .gf{padding:0 24px 14px}
  .card{background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 4px rgba(0,0,0,.07)}
  .sec{font-size:14px;font-weight:600;padding:6px 24px 10px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{background:#f0f1f5;padding:9px;text-align:left;font-size:12px;font-weight:600;color:#555}
  td{padding:9px;border-bottom:1px solid #f0f0f0;vertical-align:top}
  .badge{display:inline-block;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700;color:#fff}
  .high{background:#E24B4A}.medium{background:#EF9F27}.low{background:#1D9E75}
  @media(max-width:700px){.g2{grid-template-columns:1fr}}
</style></head><body>

<div class="hdr">
  <h1>Revenue Intelligence Dashboard</h1>
  <span class="sub">{{ refreshed_at }}</span>
</div>

<div class="kpi-row">
  <div class="kc"><div class="lbl">Total Revenue</div>
    <div class="val" style="color:#185FA5">₹{{ '{:.1f}'.format(total_revenue/1e6) }}M</div></div>
  <div class="kc"><div class="lbl">Total Orders</div>
    <div class="val" style="color:#534AB7">{{ '{:,}'.format(total_orders) }}</div></div>
  <div class="kc"><div class="lbl">Avg Order Value</div>
    <div class="val" style="color:#854F0B">₹{{ '{:,.0f}'.format(avg_order_value) }}</div></div>
  <div class="kc"><div class="lbl">Fulfillment Rate</div>
    <div class="val" style="color:#0F6E56">{{ '{:.1f}'.format(fulfillment_rate) }}%</div></div>
  <div class="kc"><div class="lbl">B2B Share</div>
    <div class="val" style="color:#993C1D">{{ '{:.1f}'.format(b2b_share) }}%</div></div>
  <div class="kc"><div class="lbl">Insights Found</div>
    <div class="val" style="color:#E24B4A">{{ insight_count }}</div></div>
</div>

{% if gemini_report %}
<div style="margin:0 24px 14px;background:#1a1d2e;border:1px solid #2a2d3e;border-radius:12px;padding:24px;">
  <div style="font-size:13px;font-weight:700;color:#a78bfa;margin-bottom:12px;">✦ AI Founder Action Plan</div>
  <div style="font-size:13px;color:#94a3b8;line-height:1.8;white-space:pre-wrap;">{{ gemini_report }}</div>
</div>
{% endif %}

<div class="gf"><div class="card">{{ trend | safe }}</div></div>
<div class="g2">
  <div class="card">{{ state | safe }}</div>
  <div class="card">{{ cat | safe }}</div>
</div>
<div class="gf"><div class="card">{{ quadrant | safe }}</div></div>
<div class="gf"><div class="card">{{ ff_method | safe }}</div></div>

<div class="sec">{{ insight_count }} Automated Insights &amp; Actions</div>
<div class="gf"><div class="card"><table>
  <thead><tr>
    <th style="width:70px">Impact</th><th>Insight</th>
    <th style="width:110px">Metric</th><th>Action</th>
  </tr></thead>
  <tbody>
  {% for ins in insights %}
  <tr>
    <td><span class="badge {{ ins.impact|lower }}">{{ ins.impact }}</span></td>
    <td><strong>{{ ins.title }}</strong><br>
        <span style="color:#666;font-size:12px">{{ ins.detail }}</span></td>
    <td style="color:#555;font-size:12px">{{ ins.metric_value }}</td>
    <td style="font-size:12px">
      <span style="font-weight:600;color:#185FA5">[{{ ins.category }}]</span><br>{{ ins.action }}
    </td>
  </tr>
  {% endfor %}
  </tbody>
</table></div></div>

<div style="padding:14px 24px;font-size:11px;color:#aaa">
  Revenue Intelligence · Automated Analysis
</div></body></html>"""


def render_dashboard(kpis: dict, insights: list, gemini_report: str = "", filename: str = "", job_id: str = None) -> str:
    """Called by FastAPI's /dashboard/{report_id} route."""
    from jinja2 import Template

    if not gemini_report and job_id:
        try:
            from database import get_database
            db = get_database()
            rpt = db.reports.find_one({"job_id": job_id})
            if rpt:
                gemini_report = rpt.get("report_text", "")
        except Exception:
            pass

    # Insights may be dicts (from MongoDB) or dataclass objects
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
        gemini_report    = gemini_report,
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
        return "<h2 style='padding:40px'>Loading... refresh in a moment.</h2>"
    return render_template_string(
        TEMPLATE,
        total_revenue    = kpis["total_revenue"],
        total_orders     = kpis["total_orders"],
        avg_order_value  = kpis["avg_order_value"],
        fulfillment_rate = kpis["fulfillment_rate"],
        b2b_share        = kpis["b2b_revenue_share"],
        insights         = _cache["insights"],
        insight_count    = len(_cache["insights"]),
        refreshed_at     = _cache.get("refreshed_at", "—"),
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
    app.run(debug=False, port=5000)