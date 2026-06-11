# app/workers/report_worker.py
# Worker 4 — Report Agent
# Job:
#   1. Read insights from MongoDB (insights collection)
#   2. Read research from MongoDB (research collection)
#   3. Read KPIs from MongoDB (kpis collection)
#   4. Send everything to Gemini
#   5. Generate founder-ready report
#   6. Save to MongoDB (reports collection)
#   7. Update job status -> "completed"

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import traceback
from datetime import datetime
from database import get_database

# Configure Gemini AFTER loading env
from google import genai
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))



def run(job_id: str) -> dict:
    db = get_database()
    _update_job(db, job_id, "reporting")
    print(f"[Report] Starting job {job_id}")

    try:
        # Step 1: Read KPIs from MongoDB
        kpi_doc = db.kpis.find_one({"job_id": job_id})
        if not kpi_doc:
            raise ValueError(f"No KPI data found for job_id: {job_id}")

        total_revenue = kpi_doc.get("total_revenue", 0)
        total_orders = kpi_doc.get("total_orders", 0)
        fulfillment_rate = kpi_doc.get("fulfillment_rate", 0)

        print(f"[Report] KPIs loaded — Revenue: ₹{total_revenue:,.0f}")

        # Step 2: Read insights from MongoDB
        insights_doc = db.insights.find_one({"job_id": job_id})
        if not insights_doc:
            raise ValueError(f"No insights found for job_id: {job_id}")

        insights = insights_doc.get("insights", [])
        print(f"[Report] {len(insights)} insights loaded")

        # Step 3: Read research from MongoDB
        research_doc = db.research.find_one({"job_id": job_id})
        research_results = []
        market_overview = "Market overview unavailable"

        if research_doc:
            research_results = research_doc.get("research_results", [])
            market_overview = research_doc.get("market_overview", market_overview)
            print(f"[Report] {len(research_results)} research results loaded")
        else:
            print(f"[Report] No research found, continuing without it")

        # Step 4: Build prompt for Gemini
        prompt = _build_prompt(
            total_revenue=total_revenue,
            total_orders=total_orders,
            fulfillment_rate=fulfillment_rate,
            insights=insights,
            research_results=research_results,
            market_overview=market_overview
        )

        # Step 5: Call Gemini
        print(f"[Report] Calling Gemini to generate report...")
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )
        report_text = response.text
        print(f"[Report] Report generated — {len(report_text)} characters")

        # Step 6: Save report to MongoDB
        db.reports.delete_one({"job_id": job_id})
        db.reports.insert_one({
    "job_id":           job_id,
    "report_id":        job_id,  # ADD THIS LINE
    "report_text":      report_text,
    "total_revenue":    total_revenue,
    "total_orders":     total_orders,
    "fulfillment_rate": fulfillment_rate,
    "insights_count":   len(insights),
    "research_count":   len(research_results),
    "created_at":       datetime.utcnow(),
        })
        print(f"[Report] Report saved to MongoDB")

        # Step 7: Update job status
        _update_job(db, job_id, "completed", {
            "report_summary": {
                "report_length":    len(report_text),
                "insights_used":    len(insights),
                "research_used":    len(research_results),
            }
        })

        print(f"[Report] ✅ Job {job_id} completed")
        return {
            "status":        "success",
            "job_id":        job_id,
            "report_length": len(report_text),
        }

    except Exception as e:
        error_msg = str(e)
        print(f"[Report] ❌ Job {job_id} failed: {error_msg}")
        print(traceback.format_exc())
        _update_job(db, job_id, "failed", {
            "error":           error_msg,
            "failed_at_stage": "report"
        })
        return {
            "status":  "failed",
            "job_id":  job_id,
            "error":   error_msg,
        }


def _build_prompt(
    total_revenue: float,
    total_orders: int,
    fulfillment_rate: float,
    insights: list,
    research_results: list,
    market_overview: str
) -> str:
    """Build the Gemini prompt from all worker outputs."""

    # Format insights
    insights_text = ""
    for i, ins in enumerate(insights, 1):
        insights_text += f"""
{i}. [{ins.get('severity', '').upper()}] {ins.get('type', '')}
   Finding: {ins.get('message', '')}
"""

    # Format research
    research_text = ""
    for i, res in enumerate(research_results, 1):
        research_text += f"""
{i}. Issue: {res.get('original_finding', '')}
   Research: {res.get('research', '')}
"""
    prompt = f"""
You are a senior strategy consultant from BCG (Boston Consulting Group) specializing in Indian D2C e-commerce.

Write a CONFIDENTIAL CLIENT REPORT for a D2C founder. Use precise consulting language, specific metrics, and McKinsey-style structure.

═══════════════════════════════════════════════════════
BUSINESS PERFORMANCE DATA
═══════════════════════════════════════════════════════
Total GMV (Gross Merchandise Value) : ₹{total_revenue:,.0f}
Total Orders (Unique SKUs Sold)     : {total_orders:,}
Fulfillment Rate                    : {fulfillment_rate:.1f}%

═══════════════════════════════════════════════════════
MARKET INTELLIGENCE
═══════════════════════════════════════════════════════
{market_overview}

═══════════════════════════════════════════════════════
DIAGNOSTIC FINDINGS
═══════════════════════════════════════════════════════
{insights_text if insights_text else "No critical issues detected."}

═══════════════════════════════════════════════════════
COMPETITIVE INTELLIGENCE
═══════════════════════════════════════════════════════
{research_text if research_text else "Competitive data unavailable."}

═══════════════════════════════════════════════════════
DELIVERABLE
═══════════════════════════════════════════════════════

Write a structured consulting report with EXACTLY these sections:

---

## EXECUTIVE BRIEFING

Write 3-4 sentences using consulting language. Reference GMV, fulfillment rate, MoM trends, and SKU concentration. End with the single biggest risk if no action is taken.

---

## DIAGNOSTIC SUMMARY

| Issue | Severity | Business Impact | Urgency |
|---|---|---|---|
[Fill with actual findings from the data above. Use terms like "revenue leakage", "SKU concentration risk", "fulfillment gap", "CAC pressure". Mark severity as CRITICAL / HIGH / MEDIUM / LOW]

---

## STRATEGIC PRIORITIES — 30-DAY ACTION PLAN

**Priority 1 — [Name the action] [CRITICAL]**
- Hypothesis: [Why this is happening in Indian D2C context]
- Action: [Specific step with timeline]
- Expected Impact: [Quantified outcome — use % or ₹ estimates]
- Owner: Founder / Marketing / Operations

**Priority 2 — [Name the action] [HIGH]**
[Same structure]

**Priority 3 — [Name the action] [HIGH]**
[Same structure]

---

## REVENUE OPPORTUNITY SIZING — 90-DAY HORIZON

| Opportunity | Estimated GMV Uplift | Effort | Timeline |
|---|---|---|---|
[List 3 specific opportunities with ₹ estimates based on the actual revenue data above]

---

## RISK REGISTER

| Risk | Probability | Revenue Impact | Mitigation |
|---|---|---|---|
[List top 3 risks with specific impact estimates]

---

## 30-DAY EXECUTION CHECKLIST

- [ ] Week 1: [Specific task]
- [ ] Week 1: [Specific task]
- [ ] Week 2: [Specific task]
- [ ] Week 2: [Specific task]
- [ ] Week 3-4: [Specific task]

---

IMPORTANT RULES:
- Use Indian marketplace terminology — Amazon.in, Flipkart, Meesho, GMV, AOV, CAC, LTV, ROAS, SKU
- Every recommendation must reference the actual data provided
- Use ₹ for all monetary values
- No generic advice — everything must be specific to this founder's numbers
- Write like a BCG consultant presenting to a Series A D2C founder
"""
    return prompt


def _update_job(db, job_id: str, status: str, extra: dict = None):
    """Update the processing_jobs collection with current status."""
    update = {"status": status, "updated_at": datetime.utcnow()}
    if extra:
        update.update(extra)
    db.processing_jobs.update_one(
        {"job_id": job_id},
        {"$set": update},
        upsert=True
    )


if __name__ == "__main__":
    TEST_JOB_ID = "test_job_001"
    result = run(TEST_JOB_ID)
    print(f"\nResult: {result}")

    db = get_database()
    report = db.reports.find_one({"job_id": TEST_JOB_ID})
    if report:
        print(f"\nReport saved successfully!")
        print(f"Report preview (first 500 chars):")
        print(report["report_text"][:500])