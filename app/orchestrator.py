import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import uuid
from datetime import datetime
from database import get_database

# Import all 4 workers
from workers.ingestion_worker import run as ingestion_run
from workers.analysis_worker import run as analysis_run
from workers.research_worker import run as research_run
from workers.report_worker import run as report_run


def run_pipeline(csv_path: str, filename: str, user_id: str = "anonymous", job_id: str = None) -> dict:
    db = get_database()
    
    # Generate unique job ID
    if not job_id:
        job_id = str(uuid.uuid4())[:8]
    
    print(f"\n{'='*50}")
    print(f"[Pipeline] Starting job {job_id}")
    print(f"[Pipeline] File: {filename}")
    print(f"{'='*50}\n")

    # Create job record
    db.processing_jobs.insert_one({
        "job_id":     job_id,
        "user_id":    user_id,
        "filename":   filename,
        "status":     "uploaded",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    # Store CSV path for ingestion worker
    db.uploads.delete_one({"job_id": job_id})
    db.uploads.insert_one({
        "job_id":      job_id,
        "filename":    filename,
        "csv_path":    csv_path,
        "uploaded_at": datetime.utcnow(),
    })

    # ── Agent 1: Ingestion ─────────────────────────────────────
    print(f"[Pipeline] → Running Agent 1: Ingestion")
    result1 = ingestion_run(job_id)
    if result1["status"] == "failed":
        return _pipeline_failed(db, job_id, "ingestion", result1["error"])
    print(f"[Pipeline] ✅ Agent 1 complete\n")

    # ── Agent 2: Analysis ──────────────────────────────────────
    print(f"[Pipeline] → Running Agent 2: Analysis")
    result2 = analysis_run(job_id)
    if result2.get("status") == "failed":
        return _pipeline_failed(db, job_id, "analysis", result2.get("error"))
    print(f"[Pipeline] ✅ Agent 2 complete\n")

    # ── Agent 3: Research ──────────────────────────────────────
    print(f"[Pipeline] → Running Agent 3: Research")
    result3 = research_run(job_id)
    if result3["status"] == "failed":
        return _pipeline_failed(db, job_id, "research", result3["error"])
    print(f"[Pipeline] ✅ Agent 3 complete\n")

    # ── Agent 4: Report ────────────────────────────────────────
    print(f"[Pipeline] → Running Agent 4: Report")
    result4 = report_run(job_id)
    if result4["status"] == "failed":
        return _pipeline_failed(db, job_id, "report", result4["error"])
    print(f"[Pipeline] ✅ Agent 4 complete\n")

    # ── Pipeline Complete ──────────────────────────────────────
    print(f"{'='*50}")
    print(f"[Pipeline] 🎉 Job {job_id} COMPLETE")
    print(f"{'='*50}\n")

    return {
        "status":        "success",
        "job_id":        job_id,
        "filename":      filename,
        "total_orders":  result1.get("total_orders", 0),
        "total_revenue": result1.get("total_revenue", 0),
        "insights":      result2.get("insights_count", 0),
        "researched":    result3.get("insights_researched", 0),
        "report_length": result4.get("report_length", 0),
    }


def get_job_status(job_id: str) -> dict:
    """
    Returns current status of a pipeline job.
    Called by /status/{job_id} endpoint in main.py
    """
    db = get_database()
    job = db.processing_jobs.find_one({"job_id": job_id})
    
    if not job:
        return {"error": "Job not found", "job_id": job_id}

    # Get report if completed
    report_preview = None
    if job.get("status") == "completed":
        report = db.reports.find_one({"job_id": job_id})
        if report:
            report_preview = report.get("report_text", "")[:500]

    return {
        "job_id":         job_id,
        "status":         job.get("status"),
        "filename":       job.get("filename"),
        "created_at":     str(job.get("created_at", "")),
        "updated_at":     str(job.get("updated_at", "")),
        "ingestion_summary": job.get("ingestion_summary"),
        "analysis_summary":  job.get("analysis_summary"),
        "research_summary":  job.get("research_summary"),
        "report_summary":    job.get("report_summary"),
        "report_preview":    report_preview,
        "error":          job.get("error"),
    }


def get_final_report(job_id: str) -> dict:
    """
    Returns the complete final report for a job.
    Called by /dashboard/{report_id} in main.py
    """
    db = get_database()
    report = db.reports.find_one({"job_id": job_id})
    
    if not report:
        return {"error": "Report not found"}

    return {
        "job_id":           job_id,
        "report_text":      report.get("report_text", ""),
        "total_revenue":    report.get("total_revenue", 0),
        "total_orders":     report.get("total_orders", 0),
        "fulfillment_rate": report.get("fulfillment_rate", 0),
        "insights_count":   report.get("insights_count", 0),
        "created_at":       str(report.get("created_at", "")),
    }


def _pipeline_failed(db, job_id: str, stage: str, error: str) -> dict:
    """Handle pipeline failure at any stage."""
    print(f"[Pipeline] ❌ Failed at stage: {stage}")
    print(f"[Pipeline] Error: {error}")
    
    db.processing_jobs.update_one(
        {"job_id": job_id},
        {"$set": {
            "status":     "failed",
            "error":      error,
            "failed_at":  stage,
            "updated_at": datetime.utcnow(),
        }}
    )
    
    return {
        "status":    "failed",
        "job_id":    job_id,
        "stage":     stage,
        "error":     error,
    }


if __name__ == "__main__":
    """Test the full pipeline end to end."""
    
    TEST_CSV = "/Users/devansh/Desktop/aiagent/Data-Driven-Profitability-and-Market-Expansion-Decision-System/amazon_sale_report.csv"
    
    result = run_pipeline(
        csv_path=TEST_CSV,
        filename="amazon_sale_report.csv",
        user_id="test_user"
    )
    
    print(f"\nFinal Result:")
    for key, val in result.items():
        print(f"  {key}: {val}")
    
    if result["status"] == "success":
        # Show job status
        status = get_job_status(result["job_id"])
        print(f"\nJob Status: {status['status']}")
        
        # Show report preview
        report = get_final_report(result["job_id"])
        if "report_text" in report:
            print(f"\nReport Preview:")
            print(report["report_text"][:800])