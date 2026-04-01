"""
report.py
Amazon Sales — Automated HTML Email Report
Builds a professional report with embedded charts (no Tableau needed).
Sends via Gmail SMTP.

Usage:
    python report.py amazon_sales.csv --save report.html
    python report.py amazon_sales.csv --email you@gmail.com

Gmail setup:
    export SMTP_USER="your@gmail.com"
    export SMTP_PASS="your-16-char-app-password"
"""

import base64, io, os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

import kpi_engine
import insights as ins_module

RUPEE = "₹"
IMPACT_COLORS = {"High": "#E24B4A", "Medium": "#EF9F27", "Low": "#1D9E75"}
CAT_COLORS = {
    "Alert": "#E24B4A", "Fulfillment": "#993C1D",
    "Revenue": "#185FA5", "Expansion": "#0F6E56", "Growth": "#534AB7"
}


def _b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    enc = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return enc


def chart_revenue_by_state(kpis):
    df = kpis["revenue_by_state"].head(12)
    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor="#fff")
    colors = ["#185FA5" if i < 3 else "#5E9BD4" for i in range(len(df))]
    ax.barh(df["ship_state"][::-1], df["revenue"][::-1], color=colors[::-1], height=0.65)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x/1e6:.1f}M"))
    ax.set_title("Revenue by State (Top 12)", fontsize=12, fontweight="bold", pad=10)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(left=False)
    fig.tight_layout()
    return _b64(fig)


def chart_monthly_trend(kpis):
    df = kpis["monthly_trend"].tail(12)
    fig, ax = plt.subplots(figsize=(8, 3), facecolor="#fff")
    ax.plot(df["year_month"], df["revenue"], marker="o", color="#185FA5", linewidth=2.5, markersize=5)
    ax.fill_between(df["year_month"], df["revenue"], alpha=0.10, color="#185FA5")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x/1e6:.1f}M"))
    ax.set_title("Monthly Revenue Trend", fontsize=12, fontweight="bold", pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(rotation=30, ha="right", fontsize=9)
    fig.tight_layout()
    return _b64(fig)


def chart_category(kpis):
    df = kpis["revenue_by_category"]
    fig, ax = plt.subplots(figsize=(7, 3.5), facecolor="#fff")
    bars = ax.bar(df["category"], df["revenue"] / 1e6, color="#5E6AD2", width=0.55)
    ax.set_ylabel("Revenue (₹M)", fontsize=10)
    ax.set_title("Revenue by Category", fontsize=12, fontweight="bold", pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(rotation=20, ha="right", fontsize=9)
    fig.tight_layout()
    return _b64(fig)


def chart_fulfillment_vs_revenue(kpis):
    df = kpis["revenue_by_state"].head(20)
    avg_ff  = kpis["fulfillment_rate"]
    avg_rev = df["revenue"].mean()
    fig, ax = plt.subplots(figsize=(7, 4), facecolor="#fff")
    colors = []
    for _, row in df.iterrows():
        if row["revenue"] > avg_rev and row["fulfillment_rate"] >= avg_ff:
            colors.append("#1D9E75")   # star markets
        elif row["revenue"] > avg_rev and row["fulfillment_rate"] < avg_ff:
            colors.append("#E24B4A")   # leaking revenue
        elif row["revenue"] <= avg_rev and row["fulfillment_rate"] >= avg_ff:
            colors.append("#EF9F27")   # expansion targets
        else:
            colors.append("#B4B2A9")   # low priority
    ax.scatter(df["revenue"] / 1e6, df["fulfillment_rate"], c=colors, s=80, alpha=0.85, edgecolors="#fff", linewidths=0.5)
    for _, row in df.iterrows():
        ax.annotate(row["ship_state"][:8], (row["revenue"] / 1e6, row["fulfillment_rate"]),
                    fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.axvline(avg_rev / 1e6, color="#aaa", linewidth=0.8, linestyle="--")
    ax.axhline(avg_ff,        color="#aaa", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Revenue (₹M)", fontsize=10)
    ax.set_ylabel("Fulfillment Rate (%)", fontsize=10)
    ax.set_title("Fulfillment Quality vs Revenue by State", fontsize=12, fontweight="bold", pad=10)
    ax.spines[["top", "right"]].set_visible(False)
    # Legend
    from matplotlib.patches import Patch
    legend = [
        Patch(color="#1D9E75", label="Star markets"),
        Patch(color="#E24B4A", label="Revenue leakage"),
        Patch(color="#EF9F27", label="Expansion targets"),
        Patch(color="#B4B2A9", label="Low priority"),
    ]
    ax.legend(handles=legend, fontsize=8, loc="lower right")
    fig.tight_layout()
    return _b64(fig)


def build_html(kpis, insights, generated_at):
    c_state   = chart_revenue_by_state(kpis)
    c_trend   = chart_monthly_trend(kpis)
    c_cat     = chart_category(kpis)
    c_scatter = chart_fulfillment_vs_revenue(kpis)

    cards = [
        ("Total Revenue",     f"₹{kpis['total_revenue']/1e6:.1f}M",    "#185FA5"),
        ("Total Orders",      f"{kpis['total_orders']:,}",               "#534AB7"),
        ("Avg Order Value",   f"₹{kpis['avg_order_value']:,.0f}",        "#854F0B"),
        ("Fulfillment Rate",  f"{kpis['fulfillment_rate']:.1f}%",        "#0F6E56"),
        ("B2B Revenue Share", f"{kpis['b2b_revenue_share']:.1f}%",       "#993C1D"),
    ]
    card_html = "".join(f"""
        <div style="background:{c};color:#fff;border-radius:10px;padding:16px 20px;
                    min-width:130px;text-align:center;flex:1">
            <div style="font-size:11px;opacity:0.85;margin-bottom:5px">{lbl}</div>
            <div style="font-size:20px;font-weight:700">{val}</div>
        </div>""" for lbl, val, c in cards)

    rows = ""
    for ins in insights:
        bg = {"High": "#fff8f8", "Medium": "#fffdf5", "Low": "#f5fff9"}.get(ins.impact, "#fff")
        rows += f"""
        <tr style="background:{bg};border-bottom:1px solid #f0f0f0">
            <td style="padding:11px 10px;font-size:11px">
                <span style="background:{IMPACT_COLORS[ins.impact]};color:#fff;
                      border-radius:4px;padding:2px 8px;font-weight:700">{ins.impact}</span>
            </td>
            <td style="padding:11px 10px">
                <div style="font-weight:600;font-size:13px;color:#1a1a1a">{ins.title}</div>
                <div style="font-size:12px;color:#666;margin-top:3px">{ins.detail}</div>
            </td>
            <td style="padding:11px 10px;font-size:12px;color:#555;white-space:nowrap">{ins.metric_value}</td>
            <td style="padding:11px 10px;font-size:12px">
                <span style="color:{CAT_COLORS.get(ins.category,'#444')};font-weight:600">[{ins.category}]</span><br>
                {ins.action}
            </td>
        </tr>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Amazon Sales Insight Report</title></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f5f7;margin:0;padding:24px">
<div style="max-width:860px;margin:0 auto;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)">

  <div style="background:#1a1a2e;padding:26px 32px">
    <div style="font-size:20px;font-weight:700;color:#fff">Amazon India Sales — Automated Insight Report</div>
    <div style="font-size:12px;color:#aab;margin-top:4px">Auto-generated · {generated_at}</div>
  </div>

  <div style="padding:26px 32px">
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:28px">{card_html}</div>

    <h2 style="font-size:15px;font-weight:600;margin:0 0 12px">Monthly Revenue Trend</h2>
    <img src="data:image/png;base64,{c_trend}" style="max-width:100%;border-radius:8px;margin-bottom:20px">

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
      <div><img src="data:image/png;base64,{c_state}" style="width:100%;border-radius:8px"></div>
      <div><img src="data:image/png;base64,{c_cat}" style="width:100%;border-radius:8px"></div>
    </div>

    <h2 style="font-size:15px;font-weight:600;margin:0 0 12px">Fulfillment Quality vs Revenue — Market Quadrant</h2>
    <img src="data:image/png;base64,{c_scatter}" style="max-width:100%;border-radius:8px;margin-bottom:24px">

    <h2 style="font-size:15px;font-weight:600;margin:0 0 12px">{len(insights)} Automated Insights &amp; Actions</h2>
    <table style="width:100%;border-collapse:collapse;font-family:inherit">
      <thead>
        <tr style="background:#f0f1f5;text-align:left">
          <th style="padding:10px;font-size:12px;color:#555;width:70px">Impact</th>
          <th style="padding:10px;font-size:12px;color:#555">Insight</th>
          <th style="padding:10px;font-size:12px;color:#555;width:110px">Metric</th>
          <th style="padding:10px;font-size:12px;color:#555">Action</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>

    <div style="margin-top:28px;padding-top:16px;border-top:1px solid #f0f0f0;font-size:11px;color:#999">
      Automated Insight System · Amazon India Sales Analysis · {generated_at}
    </div>
  </div>
</div></body></html>"""


def send_email(html, to_addr, subject):
    user = os.environ.get("SMTP_USER")
    pw   = os.environ.get("SMTP_PASS")
    if not user or not pw:
        print("[Email] Set SMTP_USER and SMTP_PASS env vars to enable sending.")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = user
    msg["To"]      = to_addr
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pw)
            s.sendmail(user, to_addr, msg.as_string())
        print(f"[Email] Sent to {to_addr}")
        return True
    except Exception as e:
        print(f"[Email] Failed: {e}")
        return False


def run(csv_path, email_to=None, save_path="report.html"):
    kpis, df   = kpi_engine.run(csv_path)
    insights   = ins_module.generate_insights(kpis)
    ts         = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    html       = build_html(kpis, insights, ts)
    Path(save_path).write_text(html, encoding="utf-8")
    print(f"[Report] Saved → {save_path}  ({len(insights)} insights)")
    if email_to:
        send_email(html, email_to, f"📊 Amazon Insight Report · {ts} · {len(insights)} findings")
    return html, insights


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("--email", default=None)
    p.add_argument("--save",  default="report.html")
    a = p.parse_args()
    run(a.csv, a.email, a.save)
