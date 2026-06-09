"""
dashboard.py - Revenue Intelligence Dashboard
Dark theme, multi-agent pipeline output, Gemini report section
"""

import sys
import threading
import time
import markdown

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

DARK_LAYOUT = dict(
    font_family="'DM Sans', -apple-system, sans-serif",
    font_color="#e2e8f0",
    plot_bgcolor="#0f1117",
    paper_bgcolor="#0f1117",
    margin=dict(l=16, r=16, t=44, b=16),
    title_font_size=14,
    title_font_color="#a78bfa",
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font_color="#94a3b8",
        font_size=11,
    ),
    xaxis=dict(gridcolor="#1e2433", tickfont_color="#64748b", tickfont_size=10),
    yaxis=dict(gridcolor="#1e2433", tickfont_color="#64748b", tickfont_size=10),
)


def refresh_data() -> None:
    try:
        kpis, _df = kpi_engine.run(CSV_PATH)
        _cache["kpis"] = kpis
        _cache["insights"] = ins_module.generate_insights(kpis)
        _cache["refreshed_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"[Dashboard] Error: {e}")


def auto_refresh(interval: int = 60) -> None:
    while True:
        time.sleep(interval)
        refresh_data()


def _html(fig) -> str:
    return pio.to_html(fig, full_html=False, config=PLOTLY_CFG)


def fig_trend(kpis: dict) -> str:
    df = kpis["monthly_trend"].tail(12)
    fig = px.area(
        df, x="year_month", y="revenue",
        title="📈 Revenue Trend",
        color_discrete_sequence=["#a78bfa"],
    )
    fig.update_layout(**DARK_LAYOUT)
    fig.update_traces(line_width=2.5, fillcolor="rgba(167,139,250,0.12)")
    return _html(fig)


def fig_category(kpis) -> str:
    df = kpis["revenue_by_category"]
    fig = go.Figure(data=[
        go.Bar(name="Revenue", x=df["category"], y=df["revenue"], marker_color="#a78bfa"),
        go.Bar(name="Avg Order ₹", x=df["category"], y=df["avg_order_value"], marker_color="#34d399"),
    ])
    fig.update_layout(barmode="group", title="🛍️ Category Performance", **DARK_LAYOUT)
    return _html(fig)


def fig_state(kpis) -> str:
    df = kpis["revenue_by_state"].head(12)
    fig = px.bar(
        df, x="revenue", y="ship_state", orientation="h",
        color="fulfillment_rate",
        color_continuous_scale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#34d399"]],
        title="🗺️ Revenue & Fulfillment by State",
        labels={"revenue": "Revenue (₹)", "fulfillment_rate": "Fulfillment %"},
    )
    fig.update_layout(**DARK_LAYOUT)
    fig.update_yaxes(autorange="reversed")
    return _html(fig)


def fig_quadrant(kpis) -> str:
    df = kpis["revenue_by_state"].head(25).copy()
    avg_ff = kpis["fulfillment_rate"]
    avg_rev = df["revenue"].mean()

    def quadrant(row):
        if row["revenue"] > avg_rev and row["fulfillment_rate"] >= avg_ff:
            return "⭐ Star market"
        if row["revenue"] > avg_rev and row["fulfillment_rate"] < avg_ff:
            return "🚨 Revenue leakage"
        if row["revenue"] <= avg_rev and row["fulfillment_rate"] >= avg_ff:
            return "🚀 Expansion target"
        return "⬇️ Low priority"

    df["quadrant"] = df.apply(quadrant, axis=1)
    color_map = {
        "⭐ Star market":       "#34d399",
        "🚨 Revenue leakage":   "#ef4444",
        "🚀 Expansion target":  "#f59e0b",
        "⬇️ Low priority":      "#475569",
    }

    fig = px.scatter(
        df, x="revenue", y="fulfillment_rate",
        text="ship_state", color="quadrant",
        color_discrete_map=color_map,
        title="🎯 Market Quadrant — Fulfillment vs Revenue",
        labels={"revenue": "Revenue (₹)", "fulfillment_rate": "Fulfillment %"},
    )
    fig.update_traces(
        textposition="top center", marker_size=12, mode="markers+text",
        textfont=dict(size=9, color="#94a3b8"),
        hovertemplate="<b>%{text}</b><br>Revenue: ₹%{x:,.0f}<br>Fulfillment: %{y:.1f}%<extra></extra>",
    )
    fig.add_vline(x=avg_rev, line_dash="dash", line_color="#334155", line_width=1)
    fig.add_hline(y=avg_ff, line_dash="dash", line_color="#334155", line_width=1)
    fig.update_layout(**DARK_LAYOUT)
    return _html(fig)


def fig_fulfillment_method(kpis) -> str:
    df = kpis["by_fulfillment_method"]
    fig = go.Figure(data=[
        go.Bar(name="Revenue", x=df["fulfillment"], y=df["revenue"], marker_color="#a78bfa"),
        go.Bar(name="Fulfillment Rate %", x=df["fulfillment"], y=df["fulfillment_rate"],
               marker_color="#34d399", yaxis="y2"),
    ])
    fig.update_layout(
        barmode="group", title="📦 Amazon vs Merchant Fulfillment",
        yaxis2=dict(overlaying="y", side="right", showgrid=False, tickfont_color="#64748b"),
        **DARK_LAYOUT
    )
    return _html(fig)


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revenue Intelligence — Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #080b12;
    --surface:   #0f1117;
    --surface2:  #151a24;
    --border:    #1e2433;
    --purple:    #a78bfa;
    --green:     #34d399;
    --amber:     #f59e0b;
    --red:       #ef4444;
    --blue:      #60a5fa;
    --text:      #e2e8f0;
    --muted:     #64748b;
    --subtle:    #94a3b8;
  }

  body {
    font-family: 'DM Sans', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    line-height: 1.5;
  }

  /* ── Header ── */
  .header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 16px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(12px);
  }
  .header-left { display: flex; align-items: center; gap: 12px; }
  .logo-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--purple);
    box-shadow: 0 0 12px var(--purple);
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.6; transform: scale(0.85); }
  }
  .header h1 { font-size: 15px; font-weight: 600; color: var(--text); }
  .header-meta { font-size: 11px; color: var(--muted); }
  .badge-live {
    background: rgba(52,211,153,0.15);
    color: var(--green);
    border: 1px solid rgba(52,211,153,0.3);
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
  }

  /* ── Layout ── */
  .page { max-width: 1400px; margin: 0 auto; padding: 24px 20px; }

  /* ── KPI Cards ── */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
  }
  .kpi-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s;
  }
  .kpi-card:hover { border-color: var(--purple); }
  .kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent, var(--purple));
  }
  .kpi-label { font-size: 11px; color: var(--muted); font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
  .kpi-value { font-size: 26px; font-weight: 700; color: var(--accent, var(--purple)); line-height: 1; }
  .kpi-sub { font-size: 11px; color: var(--muted); margin-top: 6px; }

  /* ── Agent Status Bar ── */
  .agent-bar {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 24px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    align-items: center;
  }
  .agent-bar-label { font-size: 11px; color: var(--muted); font-weight: 600; margin-right: 8px; text-transform: uppercase; letter-spacing: 0.05em; }
  .agent-pill {
    background: rgba(52,211,153,0.1);
    border: 1px solid rgba(52,211,153,0.25);
    color: var(--green);
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .agent-pill::before { content: '✓'; font-weight: 700; }

  /* ── Charts Grid ── */
  .chart-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }
  .chart-full { margin-bottom: 16px; }
  .chart-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    overflow: hidden;
  }

  /* ── Section Header ── */
  .section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 28px 0 16px;
  }
  .section-header h2 {
    font-size: 15px;
    font-weight: 600;
    color: var(--text);
  }
  .section-line {
    flex: 1;
    height: 1px;
    background: var(--border);
  }
  .section-count {
    background: rgba(167,139,250,0.15);
    color: var(--purple);
    border: 1px solid rgba(167,139,250,0.3);
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
  }

  /* ── Insight Cards ── */
  .insights-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 14px;
    margin-bottom: 24px;
  }
  .insight-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px;
    border-left: 3px solid var(--card-accent, var(--purple));
    transition: transform 0.15s, border-color 0.15s;
  }
  .insight-card:hover { transform: translateY(-2px); }
  .insight-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
  .severity-badge {
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .sev-high { background: rgba(239,68,68,0.15); color: var(--red); border: 1px solid rgba(239,68,68,0.3); }
  .sev-medium { background: rgba(245,158,11,0.15); color: var(--amber); border: 1px solid rgba(245,158,11,0.3); }
  .sev-low { background: rgba(52,211,153,0.15); color: var(--green); border: 1px solid rgba(52,211,153,0.3); }
  .insight-type { font-size: 10px; color: var(--muted); font-weight: 500; text-transform: uppercase; }
  .insight-title { font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 6px; }
  .insight-detail { font-size: 12px; color: var(--subtle); margin-bottom: 10px; line-height: 1.5; }
  .insight-metric { font-family: 'DM Mono', monospace; font-size: 13px; color: var(--purple); font-weight: 500; margin-bottom: 10px; }
  .insight-action {
    background: var(--surface2);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 12px;
    color: var(--subtle);
    border-left: 2px solid var(--blue);
  }
  .insight-action strong { color: var(--blue); display: block; margin-bottom: 3px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; }

  /* ── Gemini Report Section ── */
  .gemini-report {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    margin-bottom: 24px;
  }
  .gemini-header {
    background: linear-gradient(135deg, rgba(167,139,250,0.12), rgba(96,165,250,0.08));
    border-bottom: 1px solid var(--border);
    padding: 20px 24px;
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .gemini-icon {
    width: 40px; height: 40px;
    border-radius: 10px;
    background: linear-gradient(135deg, var(--purple), var(--blue));
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
  }
  .gemini-title { font-size: 16px; font-weight: 700; color: var(--text); }
  .gemini-subtitle { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .gemini-body {
    padding: 24px;
    font-size: 14px;
    color: var(--subtle);
    line-height: 1.8;
    font-family: 'DM Sans', sans-serif;
  }
  .gemini-body strong, .gemini-body b { color: var(--text); font-weight: 700; }
  .gemini-body h1, .gemini-body h2 {
    color: var(--purple);
    margin: 28px 0 12px;
    font-size: 15px;
    font-weight: 700;
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    letter-spacing: 0.03em;
  }
  .gemini-body h3 {
    color: var(--blue);
    margin: 20px 0 8px;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .gemini-body table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 13px;
  }
  .gemini-body th {
    background: var(--surface2);
    color: var(--purple);
    padding: 10px 14px;
    text-align: left;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border: 1px solid var(--border);
  }
  .gemini-body td {
    padding: 10px 14px;
    border: 1px solid var(--border);
    color: var(--subtle);
    vertical-align: top;
  }
  .gemini-body tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
  .gemini-body ul, .gemini-body ol {
    margin: 10px 0 10px 20px;
    color: var(--subtle);
  }
  .gemini-body li { margin-bottom: 6px; }
  .gemini-body hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 24px 0;
  }
  .gemini-body p { margin-bottom: 12px; }
  .severity-critical {
    background: rgba(239,68,68,0.15);
    color: #ef4444;
    border: 1px solid rgba(239,68,68,0.3);
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
  }
  .severity-high {
    background: rgba(245,158,11,0.15);
    color: #f59e0b;
    border: 1px solid rgba(245,158,11,0.3);
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
  }
  .severity-medium {
    background: rgba(96,165,250,0.15);
    color: #60a5fa;
    border: 1px solid rgba(96,165,250,0.3);
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
  }
  .gemini-empty {
    padding: 40px 24px;
    text-align: center;
    color: var(--muted);
    font-size: 13px;
  }
  .gemini-empty-icon { font-size: 32px; margin-bottom: 12px; }

  /* ── Footer ── */
  .footer {
    text-align: center;
    padding: 24px;
    font-size: 11px;
    color: var(--muted);
    border-top: 1px solid var(--border);
    margin-top: 32px;
  }

  @media (max-width: 768px) {
    .chart-grid-2 { grid-template-columns: 1fr; }
    .kpi-grid { grid-template-columns: repeat(2, 1fr); }
    .insights-grid { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <div class="logo-dot"></div>
    <h1>Revenue Intelligence</h1>
  </div>
  <div style="display:flex;align-items:center;gap:12px;">
    <span class="header-meta">{{ filename }} · {{ refreshed_at }}</span>
    <span class="badge-live">● Live</span>
  </div>
</div>

<div class="page">

  <!-- Agent Status Bar -->
  <div class="agent-bar">
    <span class="agent-bar-label">🤖 Agents</span>
    <span class="agent-pill">Agent 1: Ingestion</span>
    <span class="agent-pill">Agent 2: Analysis</span>
    <span class="agent-pill">Agent 3: Research</span>
    <span class="agent-pill">Agent 4: Report</span>
    <span style="margin-left:auto;font-size:11px;color:var(--muted);">{{ total_orders | int | format_num }} orders processed via MongoDB Atlas</span>
  </div>

  <!-- KPI Cards -->
  <div class="kpi-grid">
    <div class="kpi-card" style="--accent:#a78bfa">
      <div class="kpi-label">Total Revenue</div>
      <div class="kpi-value">₹{{ (total_revenue/1e7)|round(2) }}Cr</div>
      <div class="kpi-sub">Lifetime from dataset</div>
    </div>
    <div class="kpi-card" style="--accent:#60a5fa">
      <div class="kpi-label">Total Orders</div>
      <div class="kpi-value">{{ '{:,}'.format(total_orders|int) }}</div>
      <div class="kpi-sub">All order statuses</div>
    </div>
    <div class="kpi-card" style="--accent:#f59e0b">
      <div class="kpi-label">Avg Order Value</div>
      <div class="kpi-value">₹{{ '{:,.0f}'.format(avg_order_value) }}</div>
      <div class="kpi-sub">Revenue per order</div>
    </div>
    <div class="kpi-card" style="--accent:#34d399">
      <div class="kpi-label">Fulfillment Rate</div>
      <div class="kpi-value">{{ '{:.1f}'.format(fulfillment_rate) }}%</div>
      <div class="kpi-sub">Target: 85% minimum</div>
    </div>
    <div class="kpi-card" style="--accent:#f472b6">
      <div class="kpi-label">B2B Revenue Share</div>
      <div class="kpi-value">{{ '{:.1f}'.format(b2b_share) }}%</div>
      <div class="kpi-sub">Business orders</div>
    </div>
    <div class="kpi-card" style="--accent:#ef4444">
      <div class="kpi-label">Issues Detected</div>
      <div class="kpi-value">{{ insight_count }}</div>
      <div class="kpi-sub">By AI analysis agent</div>
    </div>
  </div>

  <!-- Charts -->
  <div class="chart-full">
    <div class="chart-card">{{ trend | safe }}</div>
  </div>

  <div class="chart-grid-2">
    <div class="chart-card">{{ state | safe }}</div>
    <div class="chart-card">{{ cat | safe }}</div>
  </div>

  <div class="chart-full">
    <div class="chart-card">{{ quadrant | safe }}</div>
  </div>

  <div class="chart-full">
    <div class="chart-card">{{ ff_method | safe }}</div>
  </div>

  <!-- Business Insights -->
  <div class="section-header">
    <h2>🔍 AI-Detected Business Problems</h2>
    <div class="section-line"></div>
    <span class="section-count">{{ insight_count }} insights</span>
  </div>

  <div class="insights-grid">
  {% for ins in insights %}
  {% if ins is mapping %}
  <div class="insight-card" style="--card-accent:{% if ins.get('severity','') == 'critical' or ins.get('impact','') == 'High' %}#ef4444{% elif ins.get('severity','') == 'medium' or ins.get('impact','') == 'Medium' %}#f59e0b{% else %}#34d399{% endif %}">
    <div class="insight-header">
      <span class="severity-badge {% if ins.get('severity','') == 'critical' or ins.get('impact','') == 'High' %}sev-high{% elif ins.get('severity','') == 'medium' or ins.get('impact','') == 'Medium' %}sev-medium{% else %}sev-low{% endif %}">
        {{ ins.get('severity', ins.get('impact', 'Low')) }}
      </span>
      <span class="insight-type">{{ ins.get('type', ins.get('category', 'Insight')) }}</span>
    </div>
    <div class="insight-title">{{ ins.get('message', ins.get('title', '')) }}</div>
    <div class="insight-detail">{{ ins.get('detail', '') }}</div>
    {% if ins.get('metric_value') or ins.get('value') %}
    <div class="insight-metric">{{ ins.get('metric_value', ins.get('value', '')) }}</div>
    {% endif %}
    {% if ins.get('action') %}
    <div class="insight-action">
      <strong>Recommended Action</strong>
      {{ ins.get('action', '') }}
    </div>
    {% endif %}
  </div>
  {% else %}
  <div class="insight-card">
    <div class="insight-header">
      <span class="severity-badge {% if ins.impact == 'High' %}sev-high{% elif ins.impact == 'Medium' %}sev-medium{% else %}sev-low{% endif %}">{{ ins.impact }}</span>
      <span class="insight-type">{{ ins.category }}</span>
    </div>
    <div class="insight-title">{{ ins.title }}</div>
    <div class="insight-detail">{{ ins.detail }}</div>
    <div class="insight-metric">{{ ins.metric_value }}</div>
    <div class="insight-action">
      <strong>Recommended Action</strong>
      {{ ins.action }}
    </div>
  </div>
  {% endif %}
  {% endfor %}
  </div>

  <!-- Gemini AI Report -->
  <div class="section-header">
    <h2>🤖 Gemini AI — Founder Action Plan</h2>
    <div class="section-line"></div>
    <span class="section-count">Generated by Agent 4</span>
  </div>

  <div class="gemini-report">
    <div class="gemini-header">
      <div class="gemini-icon">✦</div>
      <div>
        <div class="gemini-title">AI-Generated Founder Report</div>
        <div class="gemini-subtitle">Powered by Gemini 2.5 Flash · Google Cloud Agent Platform · MongoDB Atlas</div>
      </div>
    </div>
    {% if gemini_report %}
    <div class="gemini-body">{{ gemini_report | markdown | safe }}</div>
    {% else %}
    <div class="gemini-empty">
      <div class="gemini-empty-icon">✦</div>
      <div>Gemini report not available for this job.</div>
      <div style="margin-top:6px;font-size:11px;">Re-upload your CSV to generate a fresh AI action plan.</div>
    </div>
    {% endif %}
  </div>

</div>

<div class="footer">
  Revenue Intelligence System · Multi-Agent Pipeline · Google Cloud + MongoDB Atlas + Gemini
</div>

</body></html>"""


@app.route("/")
def index():
    kpis = _cache.get("kpis")
    if not kpis:
        return "<h2 style='padding:40px;color:white;background:#080b12'>Loading... refresh in a moment.</h2>"
    return render_template_string(
        TEMPLATE,
        total_revenue=kpis["total_revenue"],
        total_orders=kpis["total_orders"],
        avg_order_value=kpis["avg_order_value"],
        fulfillment_rate=kpis["fulfillment_rate"],
        b2b_share=kpis["b2b_revenue_share"],
        insights=_cache["insights"],
        insight_count=len(_cache["insights"]),
        refreshed_at="on demand",
        filename="amazon_sales.csv",
        gemini_report=None,
        trend=fig_trend(kpis),
        state=fig_state(kpis),
        cat=fig_category(kpis),
        quadrant=fig_quadrant(kpis),
        ff_method=fig_fulfillment_method(kpis),
    )


def render_dashboard(kpis: dict, insights: list, gemini_report: str = None, filename: str = "", job_id: str = None) -> str:
    """
    Renders the full HTML dashboard and returns it as a string.
    Called by main.py's /dashboard/{report_id} route.
    gemini_report: the full text from MongoDB reports collection
    """
    from jinja2 import Environment

    env = Environment()
    env.filters['format_num'] = lambda x: '{:,}'.format(int(x))
    env.filters['markdown'] = lambda text: markdown.markdown(
        text or '',
        extensions=['tables', 'nl2br']
    )
    t = env.from_string(TEMPLATE)

    # If no gemini_report passed but job_id available, try to fetch from MongoDB
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

    return t.render(
        total_revenue=kpis.get("total_revenue", 0),
        total_orders=kpis.get("total_orders", 0),
        avg_order_value=kpis.get("avg_order_value", 0),
        fulfillment_rate=kpis.get("fulfillment_rate", 0),
        b2b_share=kpis.get("b2b_revenue_share", 0),
        insights=insights,
        insight_count=len(insights) if insights else 0,
        refreshed_at="just now",
        filename=filename or "sales_data.csv",
        gemini_report=gemini_report,
        trend=fig_trend(kpis) if "monthly_trend" in kpis else "",
        state=fig_state(kpis) if "revenue_by_state" in kpis else "",
        cat=fig_category(kpis) if "revenue_by_category" in kpis else "",
        quadrant=fig_quadrant(kpis) if "revenue_by_state" in kpis else "",
        ff_method=fig_fulfillment_method(kpis) if "by_fulfillment_method" in kpis else "",
    )


if __name__ == "__main__":
    CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "amazon_sales.csv"
    print(f"[Dashboard] Loading {CSV_PATH}...")
    refresh_data()
    threading.Thread(target=auto_refresh, args=(60,), daemon=True).start()
    print("[Dashboard] → http://localhost:5000")
    app.run(debug=False, port=5000)