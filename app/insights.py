"""
insights.py
Amazon Sales — Automated Insight + Action Generator
Rebuilt for actual columns: amount, status, ship_state, category,
fulfillment, sales_channel, quantity, b2b_flag

Every insight has: title, detail, impact, action, category, metric_value
"""

from dataclasses import dataclass
from typing import List
import pandas as pd

IMPACT_ORDER = {"High": 0, "Medium": 1, "Low": 2}


@dataclass
class Insight:
    title: str
    detail: str
    impact: str        # "High" / "Medium" / "Low"
    action: str
    category: str      # "Revenue" / "Fulfillment" / "Expansion" / "Growth" / "Alert"
    metric_value: str


def generate_insights(kpis: dict) -> List[Insight]:
    insights = []
    insights += _revenue_concentration(kpis)
    insights += _mom_trend(kpis)
    insights += _low_fulfillment_high_revenue(kpis)
    insights += _expansion_opportunities(kpis)
    insights += _category_underperformers(kpis)
    insights += _b2b_opportunity(kpis)
    insights += _fulfillment_method_gap(kpis)
    insights += _high_fulfillment_low_revenue(kpis)
    insights.sort(key=lambda x: IMPACT_ORDER.get(x.impact, 3))
    return insights


# ── Insight rules ──────────────────────────────────────────────────────────────

def _revenue_concentration(kpis: dict) -> List[Insight]:
    """Flag if top 3 states hold > 50% of revenue — concentration risk."""
    df = kpis["revenue_by_state"]
    top3 = df.head(3)
    pct = top3["revenue_share_pct"].sum()
    names = ", ".join(top3["ship_state"].tolist())
    if pct > 50:
        return [Insight(
            title=f"Revenue dangerously concentrated: {names}",
            detail=f"These 3 states account for {pct:.0f}% of total revenue. One logistics disruption hits the whole business.",
            impact="High",
            action=f"Run targeted campaigns in mid-tier states (RAJASTHAN, PUNJAB, ODISHA). Goal: reduce top-3 concentration below 45%.",
            category="Revenue",
            metric_value=f"{pct:.0f}% in top 3 states"
        )]
    return []


def _mom_trend(kpis: dict) -> List[Insight]:
    """Flag significant month-over-month revenue movements."""
    monthly = kpis["monthly_trend"].dropna(subset=["revenue_mom_pct"])
    if len(monthly) < 2:
        return []
    last = monthly.iloc[-1]
    mom = last["revenue_mom_pct"]
    if mom < -10:
        return [Insight(
            title=f"Revenue dropped {abs(mom):.1f}% last month",
            detail=f"Month {last['year_month']}: Revenue fell to ₹{last['revenue']:,.0f}. Needs immediate investigation.",
            impact="High",
            action="Check if top states (MAHARASHTRA, KARNATAKA) saw order drops. Cross-check with fulfilment method — Merchant-fulfilled may be slower.",
            category="Alert",
            metric_value=f"{mom:.1f}% MoM"
        )]
    elif mom < -5:
        return [Insight(
            title=f"Moderate revenue dip of {abs(mom):.1f}% last month",
            detail=f"Month {last['year_month']}: ₹{last['revenue']:,.0f}. Watch next cycle closely.",
            impact="Medium",
            action="Review category mix — check if low-AOV categories (Blouse, Bottom) are crowding out high-value ones (Set, Kurta).",
            category="Alert",
            metric_value=f"{mom:.1f}% MoM"
        )]
    elif mom > 15:
        return [Insight(
            title=f"Strong revenue growth of +{mom:.1f}% last month",
            detail=f"Month {last['year_month']}: Revenue reached ₹{last['revenue']:,.0f}.",
            impact="Low",
            action="Identify what drove growth — new state, category spike, or B2B order. Replicate the conditions.",
            category="Growth",
            metric_value=f"+{mom:.1f}% MoM"
        )]
    return []


def _low_fulfillment_high_revenue(kpis: dict) -> List[Insight]:
    """High revenue states with below-average fulfillment = revenue leakage."""
    df = kpis["revenue_by_state"]
    avg_ff = kpis["fulfillment_rate"]
    avg_rev = df["revenue"].mean()
    problem = df[(df["revenue"] > avg_rev) & (df["fulfillment_rate"] < avg_ff)]
    insights = []
    for _, row in problem.iterrows():
        insights.append(Insight(
            title=f"{row['ship_state']}: High revenue, poor fulfillment",
            detail=f"₹{row['revenue']:,.0f} revenue but only {row['fulfillment_rate']:.1f}% fulfillment rate (avg: {avg_ff:.1f}%).",
            impact="High",
            action=f"Switch {row['ship_state']} orders to Amazon-fulfilled (FBA). Merchant fulfillment is costing you completed sales in your best market.",
            category="Fulfillment",
            metric_value=f"{row['fulfillment_rate']:.1f}% fulfillment"
        ))
    return insights


def _expansion_opportunities(kpis: dict) -> List[Insight]:
    """States with high fulfillment but low revenue = ready to scale."""
    df = kpis["expansion_targets"]
    if df.empty:
        return []
    top = df.iloc[0]
    all_states = ", ".join(df["ship_state"].head(5).tolist())
    return [Insight(
        title=f"{len(df)} states show strong logistics but low penetration",
        detail=f"Top target: {top['ship_state']} — {top['fulfillment_rate']:.1f}% fulfillment on only ₹{top['revenue']:,.0f} revenue.",
        impact="Medium",
        action=f"Prioritise ad spend and seller promotions in: {all_states}. Infrastructure is ready — only demand generation is missing.",
        category="Expansion",
        metric_value=f"{len(df)} expansion markets"
    )]


def _category_underperformers(kpis: dict) -> List[Insight]:
    """Categories with below-average AOV AND below-average fulfillment."""
    df = kpis["revenue_by_category"]
    avg_aov = df["avg_order_value"].mean()
    avg_ff  = df["fulfillment_rate"].mean()
    weak = df[(df["avg_order_value"] < avg_aov) & (df["fulfillment_rate"] < avg_ff)]
    insights = []
    for _, row in weak.iterrows():
        insights.append(Insight(
            title=f"{row['category']}: low AOV and poor fulfillment",
            detail=f"Avg order ₹{row['avg_order_value']:,.0f} (avg ₹{avg_aov:,.0f}) and {row['fulfillment_rate']:.1f}% fulfillment (avg {avg_ff:.1f}%).",
            impact="Medium",
            action=f"Consider bundling {row['category']} with high-AOV items (Set, Kurta) to raise basket size. Review delivery SLA for this category.",
            category="Revenue",
            metric_value=f"AOV ₹{row['avg_order_value']:,.0f}"
        ))
    return insights


def _b2b_opportunity(kpis: dict) -> List[Insight]:
    """Flag if B2B is a significant but under-leveraged revenue source."""
    b2b_share = kpis["b2b_revenue_share"]
    if 5 < b2b_share < 30:
        return [Insight(
            title=f"B2B orders are {b2b_share:.1f}% of revenue — growth lever",
            detail="B2B exists and is generating revenue, but is not the primary channel. B2B orders typically have higher AOV and repeat rates.",
            impact="Medium",
            action="Build a dedicated B2B landing page on Amazon Business. Offer bulk pricing for categories like Kurta and Set. Target corporate gifting season.",
            category="Growth",
            metric_value=f"{b2b_share:.1f}% B2B share"
        )]
    elif b2b_share >= 30:
        return [Insight(
            title=f"B2B is {b2b_share:.1f}% of revenue — protect this channel",
            detail="B2B is a significant revenue driver. Retention and account management matter more than acquisition at this stage.",
            impact="Low",
            action="Ensure dedicated account manager for top B2B buyers. Set up auto-reorder or subscription model for repeat B2B customers.",
            category="Revenue",
            metric_value=f"{b2b_share:.1f}% B2B share"
        )]
    return []


def _fulfillment_method_gap(kpis: dict) -> List[Insight]:
    """Compare Amazon-fulfilled vs Merchant-fulfilled performance."""
    df = kpis["by_fulfillment_method"]
    if len(df) < 2:
        return []
    amazon_row   = df[df["fulfillment"].str.upper() == "AMAZON"]
    merchant_row = df[df["fulfillment"].str.upper() == "MERCHANT"]
    if amazon_row.empty or merchant_row.empty:
        return []
    amz_ff  = amazon_row.iloc[0]["fulfillment_rate"]
    merch_ff = merchant_row.iloc[0]["fulfillment_rate"]
    gap = amz_ff - merch_ff
    if gap > 5:
        return [Insight(
            title=f"Amazon-fulfilled orders are {gap:.1f}% better at fulfillment",
            detail=f"Amazon: {amz_ff:.1f}% vs Merchant: {merch_ff:.1f}%. Merchant-fulfilled orders are leaking revenue through cancellations.",
            impact="High",
            action="Migrate top-selling SKUs (Set, Kurta) from Merchant to FBA. Calculate FBA fee vs cancellation loss — the math almost always favours FBA.",
            category="Fulfillment",
            metric_value=f"{gap:.1f}% fulfillment gap"
        )]
    return []


def _high_fulfillment_low_revenue(kpis: dict) -> List[Insight]:
    """Goa-type states: tiny revenue but 100% fulfillment = risk-free to scale."""
    df = kpis["revenue_by_state"]
    p10_rev = df["revenue"].quantile(0.10)
    perfect = df[(df["fulfillment_rate"] >= 95) & (df["revenue"] <= p10_rev)]
    if perfect.empty:
        return []
    names = ", ".join(perfect["ship_state"].head(4).tolist())
    return [Insight(
        title=f"{names}: near-perfect fulfillment, almost no revenue",
        detail=f"{len(perfect)} states with ≥95% fulfillment but bottom-10% revenue. Zero operational risk to scale here.",
        impact="Low",
        action=f"Run low-budget test campaigns in {names}. If demand exists, logistics is already proven — scale quickly.",
        category="Expansion",
        metric_value=f"{len(perfect)} risk-free markets"
    )]


# ── Text summary ───────────────────────────────────────────────────────────────

def format_summary(insights: List[Insight], kpis: dict) -> str:
    lines = [
        "=" * 64,
        "AUTOMATED INSIGHT REPORT — Amazon India Sales",
        f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 64,
        f"  Total Revenue    : ₹{kpis['total_revenue']:>14,.0f}",
        f"  Total Orders     : {kpis['total_orders']:>15,}",
        f"  Avg Order Value  : ₹{kpis['avg_order_value']:>14,.0f}",
        f"  Fulfillment Rate : {kpis['fulfillment_rate']:>14.1f}%",
        f"  B2B Revenue Share: {kpis['b2b_revenue_share']:>14.1f}%",
        "=" * 64,
        f"\n{len(insights)} insights found:\n",
    ]
    for i, ins in enumerate(insights, 1):
        lines.append(f"[{ins.impact.upper():<6}] {i}. {ins.title}")
        lines.append(f"         {ins.detail}")
        lines.append(f"  → ACTION: {ins.action}")
        lines.append(f"  → METRIC: {ins.metric_value}\n")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    import kpi_engine
    csv = sys.argv[1] if len(sys.argv) > 1 else "amazon_sales.csv"
    kpis, df = kpi_engine.run(csv)
    insights = generate_insights(kpis)
    print(format_summary(insights, kpis))
