"""
ai_insights.py — Phase 4: AI-powered insight generation via Claude API
Replaces the rule-based insights.py with actual reasoning.

Flow:
  kpi_engine.py computes structured KPIs (numbers, DataFrames)
  → serialize to JSON summary
  → send to Claude API with a business analyst prompt
  → parse response into Insight dataclass format
  → display in dashboard exactly like before
"""

import json
import os
import requests
import pandas as pd
from dataclasses import dataclass
from typing import List

# Re-use the same Insight dataclass so dashboard.py needs zero changes
from insights import Insight


CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL   = "claude-opus-4-20250514"


def _serialize_kpis(kpis: dict) -> dict:
    """
    Convert kpis dict to JSON-safe format.
    DataFrames → list of dicts (top 10 rows only to stay within token limit).
    """
    safe = {}
    for key, val in kpis.items():
        if isinstance(val, pd.DataFrame):
            safe[key] = val.head(10).to_dict(orient="records")
        elif isinstance(val, float) and pd.isna(val):
            safe[key] = None
        elif isinstance(val, (pd.Timestamp,)):
            safe[key] = str(val)
        else:
            try:
                json.dumps(val)  # test if serializable
                safe[key] = val
            except (TypeError, ValueError):
                safe[key] = str(val)
    return safe


def _build_prompt(kpis_json: dict, filename: str) -> str:
    """
    Build the business analyst prompt.
    The more specific the context, the better Claude's output.
    """
    return f"""You are a senior e-commerce business analyst specializing in D2C and marketplace brands in India.

You have been given structured KPI data from a sales CSV file: "{filename}"

Here is the complete KPI data:
{json.dumps(kpis_json, indent=2)}

Analyze this data and generate exactly 5-8 business insights. Each insight must be specific to the actual numbers — no generic advice.

Respond ONLY with a JSON array. No preamble, no explanation, no markdown. Just the raw JSON array.

Each insight object must have exactly these fields:
- "title": short punchy title (max 12 words)
- "detail": specific analysis with actual numbers from the data (2-3 sentences)
- "impact": exactly one of "High", "Medium", or "Low"
- "action": specific actionable recommendation with numbers/targets
- "category": exactly one of "Revenue", "Fulfillment", "Expansion", "Growth", "Alert"
- "metric_value": the key metric as a short string (e.g. "₹32.3M revenue", "67% fulfillment")

Focus on:
1. Revenue concentration risk (which states/categories dominate)
2. Fulfillment gaps (where orders are failing)
3. Growth opportunities (high fulfillment, low revenue markets)
4. Month-over-month trends (improving or declining)
5. Category performance outliers

Be brutally specific. Use the actual state names, category names, and rupee amounts from the data."""


def generate_ai_insights(kpis: dict, filename: str = "sales data") -> List[Insight]:
    """
    Main function — replaces insights.generate_insights().
    Sends KPI data to Claude API, parses response into Insight objects.
    Falls back to rule-based insights if API call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[AI Insights] No ANTHROPIC_API_KEY found, falling back to rule-based insights")
        from insights import generate_insights
        return generate_insights(kpis)

    kpis_json = _serialize_kpis(kpis)
    prompt    = _build_prompt(kpis_json, filename)

    try:
        response = requests.post(
            CLAUDE_API_URL,
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      CLAUDE_MODEL,
                "max_tokens": 2000,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        # Extract text from Claude's response
        raw_text = data["content"][0]["text"].strip()

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        insight_dicts = json.loads(raw_text)

        # Convert to Insight dataclass objects
        insights = []
        for d in insight_dicts:
            insights.append(Insight(
                title        = d.get("title", "Insight"),
                detail       = d.get("detail", ""),
                impact       = d.get("impact", "Medium"),
                action       = d.get("action", ""),
                category     = d.get("category", "Revenue"),
                metric_value = d.get("metric_value", ""),
            ))

        # Sort by impact: High → Medium → Low
        order = {"High": 0, "Medium": 1, "Low": 2}
        insights.sort(key=lambda x: order.get(x.impact, 3))

        print(f"[AI Insights] Generated {len(insights)} insights via Claude API")
        return insights

    except Exception as e:
        print(f"[AI Insights] Claude API failed: {e}. Falling back to rule-based insights.")
        from insights import generate_insights
        return generate_insights(kpis)