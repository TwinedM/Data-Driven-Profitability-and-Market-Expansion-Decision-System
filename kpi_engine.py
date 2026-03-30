"""
kpi_engine.py
Amazon Sales — KPI Engine
Rebuilt for actual schema:
  order_id, order_date, status, fulfillment, sales_channel,
  ship_city, ship_state, ship_country, category, quantity, amount, b2b_flag

Run standalone:
    python kpi_engine.py your_sales.csv
"""

import pandas as pd
from pathlib import Path

# ── Column mapping: right side = your actual CSV headers ──────────────────────
# Change the VALUES to match your CSV exactly (case-sensitive).
COLUMN_MAP = {
    "order_id":      "Order ID",
    "order_date":    "Date",
    "status":        "Status",
    "fulfillment":   "Fulfilment",       # Amazon / Merchant
    "sales_channel": "Sales Channel",
    "ship_city":     "ship-city",
    "ship_state":    "ship-state",
    "ship_country":  "ship-country",
    "category":      "Category",
    "quantity":      "Qty",
    "amount":        "Amount",
    "b2b_flag":      "B2B",
}
# ─────────────────────────────────────────────────────────────────────────────

FULFILLED_STATUSES = {"Shipped", "Shipped - Delivered to Buyer"}


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Rename to internal names
    reverse_map = {v: k for k, v in COLUMN_MAP.items()}
    df = df.rename(columns=reverse_map)

    # ── Data cleaning ──────────────────────────────────────────
    # Fix case inconsistency: Bihar/bihar/BIHAR → BIHAR
    df["ship_state"] = df["ship_state"].astype(str).str.upper().str.strip()
    df["ship_city"]  = df["ship_city"].astype(str).str.upper().str.strip()
    df["category"]   = df["category"].astype(str).str.strip()

    # Parse dates
    df["order_date"] = pd.to_datetime(df["order_date"], dayfirst=True, errors="coerce")
    df["year_month"] = df["order_date"].dt.to_period("M").astype(str)

    # Fulfillment flag
    df["is_fulfilled"] = df["status"].isin(FULFILLED_STATUSES).astype(int)

    # B2B flag
    df["is_b2b"] = df["b2b_flag"].astype(str).str.upper().str.strip().isin(
        {"TRUE", "1", "YES", "B2B"}
    ).astype(int)

    # Drop invalid amounts
    df = df[df["amount"].notna() & (df["amount"] > 0)].copy()

    return df


def compute_kpis(df: pd.DataFrame) -> dict:
    kpis = {}

    # ── Scalars ────────────────────────────────────────────────
    kpis["total_revenue"]      = df["amount"].sum()
    kpis["total_orders"]       = df["order_id"].nunique()
    kpis["total_quantity"]     = df["quantity"].sum()
    kpis["avg_order_value"]    = df["amount"].mean()
    kpis["fulfillment_rate"]   = df["is_fulfilled"].mean() * 100
    kpis["b2b_revenue_share"]  = (
        df[df["is_b2b"] == 1]["amount"].sum() / df["amount"].sum() * 100
    )

    # ── Revenue by State (with fulfillment rate) ───────────────
    kpis["revenue_by_state"] = (
        df.groupby("ship_state")
        .agg(
            revenue=("amount", "sum"),
            orders=("order_id", "nunique"),
            fulfillment_rate=("is_fulfilled", "mean"),
        )
        .assign(
            revenue_share_pct=lambda x: x["revenue"] / x["revenue"].sum() * 100,
            fulfillment_rate=lambda x: x["fulfillment_rate"] * 100,
        )
        .sort_values("revenue", ascending=False)
        .reset_index()
    )

    # ── Revenue by Category ────────────────────────────────────
    kpis["revenue_by_category"] = (
        df.groupby("category")
        .agg(
            revenue=("amount", "sum"),
            orders=("order_id", "nunique"),
            quantity=("quantity", "sum"),
            fulfillment_rate=("is_fulfilled", "mean"),
        )
        .assign(
            fulfillment_rate=lambda x: x["fulfillment_rate"] * 100,
            avg_order_value=lambda x: x["revenue"] / x["orders"],
        )
        .sort_values("revenue", ascending=False)
        .reset_index()
    )

    # ── Monthly Revenue Trend ──────────────────────────────────
    monthly = (
        df.groupby("year_month")
        .agg(revenue=("amount", "sum"), orders=("order_id", "nunique"))
        .reset_index()
        .sort_values("year_month")
    )
    monthly["revenue_mom_pct"] = monthly["revenue"].pct_change() * 100
    kpis["monthly_trend"] = monthly

    # ── Fulfillment by State (your market_expansion_model logic) ──
    kpis["fulfillment_by_state"] = (
        df.groupby("ship_state")
        .agg(
            total_orders=("order_id", "nunique"),
            fulfilled=("is_fulfilled", "sum"),
            revenue=("amount", "sum"),
        )
        .assign(
            fulfillment_rate=lambda x: x["fulfilled"] / x["total_orders"] * 100,
            revenue_share_pct=lambda x: x["revenue"] / x["revenue"].sum() * 100,
        )
        .reset_index()
    )

    # ── Composite Market Expansion Score (your SQL logic, ported) ──
    state_df = kpis["fulfillment_by_state"].copy()
    state_df["revenue_rank"]     = state_df["revenue"].rank(ascending=False)
    state_df["fulfillment_rank"] = state_df["fulfillment_rate"].rank(ascending=False)
    state_df["composite_score"]  = state_df["revenue_rank"] + state_df["fulfillment_rank"]
    kpis["expansion_model"] = state_df.sort_values("composite_score").reset_index(drop=True)

    # ── Expansion targets: high fulfillment, low revenue (under-penetrated) ──
    median_rev = state_df["revenue"].median()
    avg_fulfillment = state_df["fulfillment_rate"].mean()
    kpis["expansion_targets"] = state_df[
        (state_df["revenue"] < median_rev) &
        (state_df["fulfillment_rate"] > avg_fulfillment)
    ].sort_values("fulfillment_rate", ascending=False).head(10)

    # ── B2B vs B2C split ──────────────────────────────────────
    kpis["b2b_vs_b2c"] = (
        df.groupby("is_b2b")
        .agg(revenue=("amount", "sum"), orders=("order_id", "nunique"))
        .rename(index={0: "B2C", 1: "B2B"})
        .reset_index()
        .rename(columns={"is_b2b": "segment"})
    )

    # ── Sales channel breakdown ────────────────────────────────
    kpis["by_channel"] = (
        df.groupby("sales_channel")
        .agg(revenue=("amount", "sum"), orders=("order_id", "nunique"))
        .assign(avg_order_value=lambda x: x["revenue"] / x["orders"])
        .reset_index()
        .sort_values("revenue", ascending=False)
    )

    # ── Fulfillment method: Amazon vs Merchant ─────────────────
    kpis["by_fulfillment_method"] = (
        df.groupby("fulfillment")
        .agg(
            revenue=("amount", "sum"),
            orders=("order_id", "nunique"),
            fulfillment_rate=("is_fulfilled", "mean"),
        )
        .assign(fulfillment_rate=lambda x: x["fulfillment_rate"] * 100)
        .reset_index()
        .sort_values("revenue", ascending=False)
    )

    return kpis


def run(csv_path: str) -> tuple:
    df = load_data(csv_path)
    kpis = compute_kpis(df)
    print(
        f"[KPI Engine] {len(df):,} rows loaded | "
        f"Revenue: ₹{kpis['total_revenue']:,.0f} | "
        f"Orders: {kpis['total_orders']:,} | "
        f"Fulfillment: {kpis['fulfillment_rate']:.1f}%"
    )
    return kpis, df


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "amazon_sales.csv"
    kpis, df = run(path)
    print("\nTop 5 States by Revenue:")
    print(kpis["revenue_by_state"].head(5).to_string(index=False))
    print("\nCategory Performance:")
    print(kpis["revenue_by_category"].to_string(index=False))
    print("\nExpansion Targets:")
    print(kpis["expansion_targets"][["ship_state","revenue","fulfillment_rate"]].to_string(index=False))
