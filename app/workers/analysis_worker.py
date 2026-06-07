# app/workers/analysis_worker.py
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from database import get_database

def run(job_id: str) -> dict:
    print(f"[Analysis Worker] Starting for job: {job_id}")
    db = get_database()

    # Update job status
    db.processing_jobs.update_one(
        {"job_id": job_id},
        {"$set": {"stage": "analyzing", "updated_at": datetime.utcnow()}},
        upsert=True
    )

    # Read KPIs saved by ingestion worker
    kpi_doc = db.kpis.find_one({"job_id": job_id})
    if not kpi_doc:
        raise ValueError(f"No KPI data found for job_id: {job_id}")

    kpis = kpi_doc
    insights = []

    # Check 1 — Underperforming Categories
    rev_by_cat = kpis.get("revenue_by_category")
    if rev_by_cat is not None and hasattr(rev_by_cat, '__iter__'):
        cat_revenues = {}
        for row in rev_by_cat:
            if isinstance(row, dict) and "category" in row and "revenue" in row:
                cat_revenues[row["category"]] = row["revenue"]
        if cat_revenues:
            avg = sum(cat_revenues.values()) / len(cat_revenues)
            for cat, rev in cat_revenues.items():
                if rev < avg * 0.5:
                    insights.append({
                        "type": "underperforming_category",
                        "severity": "high",
                        "message": f"Category '{cat}' earns ₹{rev:.0f} vs avg ₹{avg:.0f}",
                        "category": cat,
                        "value": rev
                    })

    # Check 2 — Weak State Markets
    rev_by_state = kpis.get("revenue_by_state")
    if rev_by_state is not None and hasattr(rev_by_state, '__iter__'):
        state_revenues = {}
        for row in rev_by_state:
            if isinstance(row, dict) and "ship_state" in row and "revenue" in row:
                state_revenues[row["ship_state"]] = row["revenue"]
        if state_revenues:
            avg = sum(state_revenues.values()) / len(state_revenues)
            for state, rev in state_revenues.items():
                if rev < avg * 0.3:
                    insights.append({
                        "type": "weak_market",
                        "severity": "medium",
                        "message": f"'{state}' is a weak market — only ₹{rev:.0f} revenue",
                        "state": state,
                        "value": rev
                    })

    # Check 3 — Month-over-Month Revenue Drop
    monthly = kpis.get("monthly_trend")
    if monthly is not None and hasattr(monthly, '__iter__'):
        monthly_list = list(monthly)
        if len(monthly_list) >= 2:
            monthly_sorted = sorted(monthly_list, key=lambda x: x.get("year_month", ""))
            last = monthly_sorted[-1]
            prev = monthly_sorted[-2]
            last_rev = last.get("revenue", 0)
            prev_rev = prev.get("revenue", 0)
            if prev_rev > 0:
                drop_pct = ((prev_rev - last_rev) / prev_rev) * 100
                if drop_pct > 20:
                    insights.append({
                        "type": "mom_revenue_drop",
                        "severity": "critical",
                        "message": f"Revenue dropped {drop_pct:.1f}% from {prev.get('year_month')} to {last.get('year_month')}",
                        "drop_percent": round(drop_pct, 2)
                    })

    # Check 4 — Low Fulfillment Rate
    fulfillment_rate = kpis.get("fulfillment_rate", 100)
    if fulfillment_rate < 60:
        insights.append({
            "type": "low_fulfillment_rate",
            "severity": "critical",
            "message": f"Only {fulfillment_rate:.1f}% orders fulfilled — major operational risk",
            "fulfillment_rate": fulfillment_rate
        })

    # Check 5 — Expansion Opportunities
    expansion = kpis.get("expansion_targets")
    if expansion is not None and hasattr(expansion, '__iter__'):
        exp_list = list(expansion)
        if len(exp_list) > 0:
            insights.append({
                "type": "expansion_opportunity",
                "severity": "low",
                "message": f"{len(exp_list)} states identified as expansion targets",
                "states": [r.get("ship_state") for r in exp_list if isinstance(r, dict)]
            })

    # Save insights to MongoDB
    db.insights.delete_one({"job_id": job_id})
    db.insights.insert_one({
    "job_id": job_id,
    "insights": insights,
    "total_issues": len(insights),
    "created_at": datetime.utcnow()
})

    # Update job status
    db.processing_jobs.update_one(
        {"job_id": job_id},
        {"$set": {"stage": "analysis_complete", "updated_at": datetime.utcnow()}}
    )

    print(f"[Analysis Worker] Done. {len(insights)} insights found.")
    return {"job_id": job_id, "insights_count": len(insights)}

if __name__ == "__main__":
    TEST_JOB_ID = "test_job_001"
    result = run(TEST_JOB_ID)
    print(f"\nResult: {result}")
    
    from database import get_database
    db = get_database()
    findings = db.insights.find_one({"job_id": TEST_JOB_ID})
    print(f"Insights in MongoDB: {findings['total_issues'] if findings else 'None'}")
    job = db.processing_jobs.find_one({"job_id": TEST_JOB_ID})
    print(f"Job status: {job['stage'] if job else 'None'}")