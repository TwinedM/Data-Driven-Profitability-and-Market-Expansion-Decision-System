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
client = genai.Client(api_key=GEMINI_API_KEY)



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
You are a senior business consultant for Indian D2C brands selling on Amazon and Flipkart.

Based on the data below, write a FOUNDER-READY ACTION PLAN report.

═══════════════════════════════════════
BUSINESS PERFORMANCE SUMMARY
═══════════════════════════════════════
Total Revenue    : ₹{total_revenue:,.0f}
Total Orders     : {total_orders:,}
Fulfillment Rate : {fulfillment_rate:.1f}%

═══════════════════════════════════════
MARKET OVERVIEW
═══════════════════════════════════════
{market_overview}

═══════════════════════════════════════
BUSINESS PROBLEMS DETECTED
═══════════════════════════════════════
{insights_text if insights_text else "No major issues detected."}

═══════════════════════════════════════
RESEARCH & COMPETITIVE INTELLIGENCE
═══════════════════════════════════════
{research_text if research_text else "No research data available."}

═══════════════════════════════════════
YOUR TASK
═══════════════════════════════════════
Write a structured founder report with these exact sections:

1. EXECUTIVE SUMMARY (3-4 sentences on overall business health)

2. TOP 3 CRITICAL ACTIONS (specific, numbered, actionable steps for next 30 days)

3. REVENUE OPPORTUNITIES (where to grow revenue in next 90 days)

4. RISKS TO WATCH (top 2-3 risks if no action taken)

5. 30-DAY PRIORITY CHECKLIST (5 bullet points, specific tasks)

Keep language direct and practical. Use Indian marketplace context.
No generic advice — everything must be specific to this data.
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