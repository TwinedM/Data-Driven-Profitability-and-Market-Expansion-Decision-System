"""
kpi_engine.py
Amazon Sales — KPI Engine

FIX LOG vs original:
  • COLUMN_MAP updated to handle both B2B and fulfilled-by columns.
  • b2b_flag now correctly reads the real 'B2B' CSV column.
  • Date format '%m-%d-%y' matching "04-30-22" style.
  • FULFILLED_STATUSES expanded to cover "Shipped - Delivered to Buyer".
  • amount_valid filter applied before KPI aggregations.
  • by_fulfillment_method uses 'fulfillment' (Fulfilment column).

Run standalone:
    python kpi_engine.py "Amazon Sale Report.csv"
"""

import pandas as pd
from pathlib import Path

COLUMN_MAP = {
    "order_id":           "Order ID",
    "order_date":         "Date",
    "status":             "Status",
    "fulfillment":        "Fulfilment",
    "sales_channel":      "Sales Channel",
    "ship_service":       "ship-service-level",
    "style":              "Style",
    "sku":                "SKU",
    "category":           "Category",
    "size":               "Size",
    "asin":               "ASIN",
    "courier_status":     "Courier Status",
    "quantity":           "Qty",
    "currency":           "currency",
    "amount":             "Amount",
    "ship_city":          "ship-city",
    "ship_state":         "ship-state",
    "is_b2b_raw":         "B2B",
    "fulfillment_type":   "fulfilled-by",
}

FULFILLED_STATUSES = {"Shipped", "Shipped - Delivered to Buyer"}


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, low_memory=False)
    df.columns = df.columns.str.strip()

    reverse_map = {v: k for k, v in COLUMN_MAP.items() if v in df.columns}
    df = df.rename(columns=reverse_map)

    df["ship_state"] = df["ship_state"].astype(str).str.upper().str.strip()
    df["ship_city"]  = df["ship_city"].astype(str).str.upper().str.strip()
    df["category"]   = df["category"].astype(str).str.strip()
    df["status"]     = df["status"].astype(str).str.strip()

    df["order_date"] = pd.to_datetime(df["order_date"], format="%m-%d-%y", errors="coerce")
    df["year_month"] = df["order_date"].dt.to_period("M").astype(str)

    df["is_fulfilled"] = df["status"].isin(FULFILLED_STATUSES).astype(int)

    if "is_b2b_raw" in df.columns:
        df["is_b2b"] = df["is_b2b_raw"].astype(str).str.upper().str.strip().isin(
            ["TRUE", "1", "YES"]
        ).astype(int)
    else:
        df["is_b2b"] = 0

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df[df["amount"].notna() & (df["amount"] > 0)].copy()

    return df


def compute_kpis(df: pd.DataFrame) -> dict:
    kpis = {}

    kpis["total_revenue"]     = float(df["amount"].sum())
    kpis["total_orders"]      = int(df["order_id"].nunique())
    kpis["total_quantity"]    = int(df["quantity"].sum()) if "quantity" in df.columns else 0
    kpis["avg_order_value"]   = float(df["amount"].mean())
    kpis["fulfillment_rate"]  = float(df["is_fulfilled"].mean() * 100)
    kpis["b2b_revenue_share"] = float(
        df[df["is_b2b"] == 1]["amount"].sum() / df["amount"].sum() * 100
    )

    kpis["revenue_by_state"] = (
        df.groupby("ship_state")
        .agg(revenue=("amount", "sum"), orders=("order_id", "nunique"),
             fulfillment_rate=("is_fulfilled", "mean"))
        .assign(revenue_share_pct=lambda x: x["revenue"] / x["revenue"].sum() * 100,
                fulfillment_rate=lambda x: x["fulfillment_rate"] * 100)
        .sort_values("revenue", ascending=False)
        .reset_index()
    )

    kpis["revenue_by_category"] = (
        df.groupby("category")
        .agg(revenue=("amount", "sum"), orders=("order_id", "nunique"),
             fulfillment_rate=("is_fulfilled", "mean"))
        .assign(fulfillment_rate=lambda x: x["fulfillment_rate"] * 100,
                avg_order_value=lambda x: x["revenue"] / x["orders"])
        .sort_values("revenue", ascending=False)
        .reset_index()
    )

    monthly = (
        df.groupby("year_month")
        .agg(revenue=("amount", "sum"), orders=("order_id", "nunique"))
        .reset_index()
        .sort_values("year_month")
    )
    monthly["revenue_mom_pct"] = monthly["revenue"].pct_change() * 100
    kpis["monthly_trend"] = monthly

    kpis["fulfillment_by_state"] = (
        df.groupby("ship_state")
        .agg(total_orders=("order_id", "nunique"), fulfilled=("is_fulfilled", "sum"),
             revenue=("amount", "sum"))
        .assign(fulfillment_rate=lambda x: x["fulfilled"] / x["total_orders"] * 100,
                revenue_share_pct=lambda x: x["revenue"] / x["revenue"].sum() * 100)
        .reset_index()
    )

    state_df = kpis["fulfillment_by_state"].copy()
    aov_map  = df.groupby("ship_state")["amount"].mean().rename("avg_order_value")
    state_df = state_df.join(aov_map, on="ship_state")
    state_df["revenue_rank"]     = state_df["revenue"].rank(ascending=False)
    state_df["fulfillment_rank"] = state_df["fulfillment_rate"].rank(ascending=False)
    state_df["aov_rank"]         = state_df["avg_order_value"].rank(ascending=False)
    state_df["composite_score"]  = (
        state_df["revenue_rank"] + state_df["fulfillment_rank"] + state_df["aov_rank"]
    )
    kpis["expansion_model"] = state_df.sort_values("composite_score").reset_index(drop=True)

    median_rev      = state_df["revenue"].median()
    avg_fulfillment = state_df["fulfillment_rate"].mean()
    kpis["expansion_targets"] = state_df[
        (state_df["revenue"] < median_rev) &
        (state_df["fulfillment_rate"] > avg_fulfillment)
    ].sort_values("fulfillment_rate", ascending=False).head(10)

    kpis["b2b_vs_b2c"] = (
        df.groupby("is_b2b")
        .agg(revenue=("amount", "sum"), orders=("order_id", "nunique"))
        .rename(index={0: "B2C", 1: "B2B"})
        .reset_index()
        .rename(columns={"is_b2b": "segment"})
    )

    kpis["by_channel"] = (
        df.groupby("sales_channel")
        .agg(revenue=("amount", "sum"), orders=("order_id", "nunique"))
        .assign(avg_order_value=lambda x: x["revenue"] / x["orders"])
        .reset_index()
        .sort_values("revenue", ascending=False)
    )

    kpis["by_fulfillment_method"] = (
        df.groupby("fulfillment")
        .agg(revenue=("amount", "sum"), orders=("order_id", "nunique"),
             fulfillment_rate=("is_fulfilled", "mean"))
        .assign(fulfillment_rate=lambda x: x["fulfillment_rate"] * 100)
        .reset_index()
        .sort_values("revenue", ascending=False)
    )

    return kpis


def run(csv_path: str) -> tuple:
    df   = load_data(csv_path)
    kpis = compute_kpis(df)
    print(
        f"[KPI Engine] {len(df):,} rows | "
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
    print("\nExpansion Targets:")
    print(kpis["expansion_targets"][["ship_state","revenue","fulfillment_rate"]].to_string(index=False))
