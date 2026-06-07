from difflib import SequenceMatcher

# ── The internal names kpi_engine.py needs, with their aliases ───────────────
# Each internal name maps to a list of possible CSV header names
# (lowercase, stripped — we normalize before matching)
FIELD_ALIASES = {
    "order_id": [
        "order id", "order_id", "orderid", "id", "order no", "order number",
        "transaction id", "sale id"
    ],
    "order_date": [
        "date", "order date", "order_date", "sale date", "created at",
        "created_at", "purchase date", "transaction date"
    ],
    "status": [
        "status", "order status", "order_status", "fulfillment status",
        "shipment status", "delivery status"
    ],
    "fulfillment": [
        "fulfilment", "fulfillment", "fulfilled by", "fulfillment type",
        "shipping type", "dispatch type"
    ],
    "sales_channel": [
        "sales channel", "sales_channel", "channel", "platform", "source",
        "marketplace"
    ],
    "category": [
        "category", "product category", "item category", "type",
        "product type", "department"
    ],
    "quantity": [
        "qty", "quantity", "units", "count", "items", "pieces", "no of items"
    ],
    "amount": [
    "amount", "revenue", "price", "total", "sale amount", "order value",
    "gmv", "selling price", "total amount", "net amount", "gross amount",
    "total_price", "totalprice", "total price", "unit price", "sale value"
],

    "ship_city": [
        "ship city", "ship-city", "shipping city", "city", "delivery city",
        "customer city"
    ],
    "ship_state": [
        "ship state", "ship-state", "shipping state", "state",
        "delivery state", "customer state", "province"
    ],
    # Optional fields — nice to have but not required
    "sku":            ["sku", "product sku", "item sku", "product code"],
    "category":       ["category", "product category", "item type"],
    "courier_status": ["courier status", "courier_status", "tracking status"],
    "currency":       ["currency", "currency code"],
}

# These fields MUST be mapped for the engine to work
REQUIRED_FIELDS = {"order_id", "order_date", "status", "amount", "ship_state"}

# Optional — engine handles missing gracefully
OPTIONAL_FIELDS = {"fulfillment", "sales_channel", "category", "quantity",
                   "ship_city", "sku", "courier_status", "currency"}


def _similarity(a: str, b: str) -> float:
    """
    Returns 0.0–1.0 similarity score between two strings.
    SequenceMatcher finds the longest common subsequences.
    Score of 1.0 = identical, 0.0 = nothing in common.
    """
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def auto_detect_columns(csv_headers: list[str]) -> dict[str, str | None]:
    """
    Given a list of CSV column headers, returns a mapping:
      { internal_name → best_matching_csv_header }

    If no good match found, value is None (user must pick manually).

    How it works:
    1. Normalize all CSV headers (lowercase, strip spaces)
    2. For each internal field, check its aliases list
    3. First try exact match — if found, confidence = 1.0
    4. Then try fuzzy match using SequenceMatcher
    5. Pick the CSV header with highest similarity score
    6. Only accept if score > 0.6 (threshold to avoid bad guesses)
    """
    normalized = {h: h.lower().strip().replace("-", " ").replace("_", " ")
                  for h in csv_headers}

    mapping = {}  # internal_name → original CSV header

    for internal_name, aliases in FIELD_ALIASES.items():
        best_header = None
        best_score = 0.0

        for csv_header, csv_norm in normalized.items():
            # Check against all aliases for this internal field
            for alias in aliases:
                score = _similarity(csv_norm, alias)
                if score > best_score:
                    best_score = score
                    best_header = csv_header

        # Only accept matches above threshold
        mapping[internal_name] = best_header if best_score >= 0.6 else None

    return mapping


def get_missing_required(mapping: dict) -> list[str]:
    """Returns list of required fields that have no mapping."""
    return [f for f in REQUIRED_FIELDS if not mapping.get(f)]


def apply_mapping(df, mapping: dict):
    """
    Renames CSV columns to internal names using the confirmed mapping.
    Drops columns that weren't mapped (engine doesn't need them).
    Adds default values for optional fields that are missing.
    """
    import pandas as pd

    # Build rename dict: { original_csv_header → internal_name }
    rename = {v: k for k, v in mapping.items() if v is not None}
    df = df.rename(columns=rename)

    # Add defaults for missing optional columns
    if "fulfillment" not in df.columns:
        df["fulfillment"] = "Unknown"
    if "sales_channel" not in df.columns:
        df["sales_channel"] = "Unknown"
    if "category" not in df.columns:
        df["category"] = "General"
    if "quantity" not in df.columns:
        df["quantity"] = 1
    if "ship_city" not in df.columns:
        df["ship_city"] = "Unknown"
    if "currency" not in df.columns:
        df["currency"] = "INR"
    if "sku" not in df.columns:
        df["sku"] = "N/A"
    if "courier_status" not in df.columns:
        df["courier_status"] = "Unknown"

    return df