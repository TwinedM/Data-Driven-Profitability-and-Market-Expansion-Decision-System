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
    _update_job(db, job_id, "researching")
    print(f"[Research] Starting job {job_id}")

    try:
        # Step 1: Read insights from MongoDB
        findings = db.insights.find_one({"job_id": job_id})
        if not findings:
            raise ValueError(f"No insights found for job_id: {job_id}")

        insights = findings.get("insights", [])
        if not insights:
            raise ValueError("No insights to research")

        print(f"[Research] Found {len(insights)} insights to research")

        # Step 2: Read KPIs for context
        kpi_doc = db.kpis.find_one({"job_id": job_id})
        total_revenue = kpi_doc.get("total_revenue", 0) if kpi_doc else 0
        fulfillment_rate = kpi_doc.get("fulfillment_rate", 0) if kpi_doc else 0

        # Step 3: Get top 3 high severity insights to research
        high_insights = [i for i in insights if i.get("severity") in ["high", "critical"]]
        top_insights = high_insights[:3] if high_insights else insights[:3]

        # Step 4: Research each insight with Gemini
        research_results = []
        for insight in top_insights:
            print(f"[Research] Researching: {insight.get('message', '')[:50]}...")
            research = _research_insight(insight)
            research_results.append(research)

        # Step 5: Get market overview
        print(f"[Research] Getting D2C market overview...")
        market_overview = _get_market_overview(total_revenue, fulfillment_rate)

        # Step 6: Save research to MongoDB
        db.research.delete_one({"job_id": job_id})
        db.research.insert_one({
            "job_id":          job_id,
            "research_results": research_results,
            "market_overview":  market_overview,
            "insights_researched": len(research_results),
            "created_at":      datetime.utcnow(),
        })

        print(f"[Research] Saved {len(research_results)} research results to MongoDB")

        # Step 7: Update job status
        _update_job(db, job_id, "reporting", {
            "research_summary": {
                "insights_researched": len(research_results),
                "market_overview_generated": True,
            }
        })

        print(f"[Research] ✅ Job {job_id} research complete")
        return {
            "status": "success",
            "job_id": job_id,
            "insights_researched": len(research_results),
        }

    except Exception as e:
        error_msg = str(e)
        print(f"[Research] ❌ Job {job_id} failed: {error_msg}")
        print(traceback.format_exc())
        _update_job(db, job_id, "failed", {
            "error": error_msg,
            "failed_at_stage": "research"
        })
        return {"status": "failed", "job_id": job_id, "error": error_msg}


def _research_insight(insight: dict) -> dict:
    """Use Gemini to research a specific business insight."""
    insight_type = insight.get("type", "")
    message = insight.get("message", "")
    severity = insight.get("severity", "medium")

    prompt = f"""
You are a D2C e-commerce business analyst specializing in Indian marketplaces.

A business insight has been detected:
- Type: {insight_type}
- Severity: {severity}
- Finding: {message}

Provide a brief research response with:
1. WHY this is happening (2-3 sentences, India D2C context)
2. BENCHMARK: What top Indian D2C brands achieve for this metric
3. QUICK FIX: One specific action to improve this in 30 days
4. EXPECTED IMPACT: What improvement to expect (use numbers)

Keep it under 150 words. Be specific to Indian marketplace context.
"""

    try:
        client.models.generate_content(
    model="gemini-1.5-flash",
    contents=prompt
)
        return {
            "insight_type":  insight_type,
            "original_finding": message,
            "severity":      severity,
            "research":      response.text,
            "researched_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "insight_type":  insight_type,
            "original_finding": message,
            "severity":      severity,
            "research":      f"Research unavailable: {str(e)}",
            "researched_at": datetime.utcnow().isoformat(),
        }


def _get_market_overview(total_revenue: float, fulfillment_rate: float) -> str:
    """Use Gemini to generate a market context overview."""
    prompt = f"""
You are a D2C market analyst for Indian e-commerce.

A D2C brand has:
- Total Revenue: ₹{total_revenue:,.0f}
- Fulfillment Rate: {fulfillment_rate:.1f}%

In 100 words, give:
1. How this compares to average Indian D2C brands on Amazon/Flipkart
2. The single biggest opportunity for growth right now
3. One risk to watch out for

Be specific, use Indian market context, mention real platforms.
"""

    try:
        response = client.models.generate_content(
    model="gemini-1.5-flash",
    contents=prompt
)
        return response.text
    except Exception as e:
        return f"Market overview unavailable: {str(e)}"


def _update_job(db, job_id: str, status: str, extra: dict = None):
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
    research = db.research.find_one({"job_id": TEST_JOB_ID})
    if research:
        print(f"\nResearch results: {research['insights_researched']} insights researched")
        print(f"\nMarket Overview:")
        print(research["market_overview"])
        print(f"\nFirst Research Result:")
        if research["research_results"]:
            print(research["research_results"][0]["research"])
    job = db.processing_jobs.find_one({"job_id": TEST_JOB_ID})
    print(f"\nJob status: {job['status'] if job else 'None'}")