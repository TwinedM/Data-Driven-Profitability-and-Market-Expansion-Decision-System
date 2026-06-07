"""
ingestion_worker.py
Worker 1 — Ingestion

Job:
  1. Read uploaded CSV bytes from MongoDB (uploads collection)
  2. Parse + clean using existing column_mapper.py
  3. Compute KPIs using existing kpi_engine.py
  4. Save cleaned orders → MongoDB cleaned_orders collection
  5. Save KPI snapshot → MongoDB kpis collection
  6. Update job status → "analyzing"

Called by:
  orchestrator.py → run_pipeline(job_id)
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import io
import traceback
from datetime import datetime

import pandas as pd

# Your existing modules — zero changes to them
from database import get_database
from column_mapper import auto_detect_columns, apply_mapping, get_missing_required
from kpi_engine import load_data_from_df, compute_kpis

def run(job_id: str) -> dict:
    """
    Main entry point. Called by orchestrator.
    Returns a result dict with status and summary.
    """
    db = get_database()

    # ── Step 1: Update job status to ingesting ─────────────────
    _update_job(db, job_id, "ingesting")
    print(f"[Ingestion] Starting job {job_id}")

    try:
        # ── Step 2: Read CSV from MongoDB uploads collection ───
        upload = db.uploads.find_one({"job_id": job_id})
        if not upload:
            raise ValueError(f"No upload found for job_id: {job_id}")

        # CSV was stored as bytes — read it into pandas
        if "csv_path" in upload:
            df_raw = pd.read_csv(upload["csv_path"],low_memory=False)
        else: 
            csv_bytes = upload["csv_bytes"]
            df_raw = pd.read_csv(io.BytesIO(csv_bytes))
        filename = upload.get("filename", "unknown.csv")
        print(f"[Ingestion] Loaded CSV: {filename} — {len(df_raw)} rows")

        # ── Step 3: Auto-detect and map columns ───────────────
        headers = df_raw.columns.tolist()
        mapping = auto_detect_columns(headers)

        # Check required fields are mapped
        missing = get_missing_required(mapping)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Apply column mapping
        df_mapped = apply_mapping(df_raw.copy(), mapping)

        # ── Step 4: Clean data + compute KPIs ─────────────────
        # Uses your existing kpi_engine functions — zero changes
        df_clean = load_data_from_df(df_mapped)
        kpis = compute_kpis(df_clean)

        print(f"[Ingestion] KPIs computed — "
              f"Revenue: ₹{kpis['total_revenue']:,.0f} | "
              f"Orders: {kpis['total_orders']:,} | "
              f"Fulfillment: {kpis['fulfillment_rate']:.1f}%")

        # ── Step 5: Save cleaned orders to MongoDB ────────────
        # Convert DataFrame to list of dicts for MongoDB
        orders_data = df_clean.to_dict(orient="records")

        # Clean any NaN values (MongoDB doesn't accept NaN)
        orders_data = _clean_for_mongo(orders_data)

        # Delete previous data for this job if re-running
        db.cleaned_orders.delete_many({"job_id": job_id})
        db.cleaned_orders.insert_one({
            "job_id": job_id,
            "total_rows": len(orders_data),
            "sample_rows": orders_data[:10],  # store only 10 sample rows
            "columns": list(orders_data[0].keys()) if orders_data else [],
            "stored_at": datetime.utcnow(),
        })

        print(f"[Ingestion] Saved summary of {len(orders_data)} orders to MongoDB (sample only)")


           
           
        

        # ── Step 6: Save KPI snapshot to MongoDB ──────────────
        kpi_doc = _serialize_kpis(kpis, job_id)
        db.kpis.delete_one({"job_id": job_id})
        db.kpis.insert_one(kpi_doc)
        print(f"[Ingestion] KPIs saved to MongoDB")

        # ── Step 7: Update job status → ready for Agent 2 ─────
        _update_job(db, job_id, "analyzing", {
            "ingestion_summary": {
                "total_rows": len(df_raw),
                "clean_rows": len(df_clean),
                "total_revenue": kpis["total_revenue"],
                "total_orders": kpis["total_orders"],
                "fulfillment_rate": kpis["fulfillment_rate"],
                "filename": filename,
            }
        })

        print(f"[Ingestion] ✅ Job {job_id} ingestion complete")

        return {
            "status": "success",
            "job_id": job_id,
            "rows_processed": len(df_clean),
            "total_revenue": kpis["total_revenue"],
            "total_orders": kpis["total_orders"],
        }

    except Exception as e:
        # Save error to job so dashboard can show it
        error_msg = str(e)
        print(f"[Ingestion] ❌ Job {job_id} failed: {error_msg}")
        print(traceback.format_exc())

        _update_job(db, job_id, "failed", {
            "error": error_msg,
            "failed_at_stage": "ingestion"
        })

        return {
            "status": "failed",
            "job_id": job_id,
            "error": error_msg,
        }


# ─────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────

def _update_job(db, job_id: str, status: str, extra: dict = None):
    """Update the processing_jobs collection with current status."""
    update = {
        "status": status,
        "updated_at": datetime.utcnow(),
    }
    if extra:
        update.update(extra)

    db.processing_jobs.update_one(
        {"job_id": job_id},
        {"$set": update},
        upsert=True  # create if doesn't exist
    )


def _clean_for_mongo(records: list) -> list:
    """
    MongoDB doesn't accept float NaN values.
    Replace NaN with None (which becomes null in MongoDB).
    """
    import math
    cleaned = []
    for record in records:
        clean_record = {}
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                clean_record[key] = None
            elif isinstance(value, pd.Timestamp):
                clean_record[key] = value.to_pydatetime()
            elif hasattr(value, 'item'):
                # Convert numpy types to Python native
                clean_record[key] = value.item()
            else:
                clean_record[key] = value
        cleaned.append(clean_record)
    return cleaned


def _serialize_kpis(kpis: dict, job_id: str) -> dict:
    """
    Convert KPI dict to MongoDB-safe format.
    DataFrames → list of dicts.
    Timestamps → Python datetime.
    Numpy types → Python native types.
    """
    import math
    import numpy as np

    safe = {"job_id": job_id, "created_at": datetime.utcnow()}

    for key, val in kpis.items():
        if isinstance(val, pd.DataFrame):
            # Convert DataFrame to list of dicts (top 50 rows)
            records = val.head(50).to_dict(orient="records")
            safe[key] = _clean_for_mongo(records)
        elif isinstance(val, float) and math.isnan(val):
            safe[key] = None
        elif isinstance(val, (np.integer,)):
            safe[key] = int(val)
        elif isinstance(val, (np.floating,)):
            safe[key] = float(val)
        elif isinstance(val, pd.Timestamp):
            safe[key] = val.to_pydatetime()
        else:
            safe[key] = val

    return safe


# ─────────────────────────────────────────────────────────────
# Standalone test — run this file directly to test
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    import sys
    
    TEST_CSV_PATH = "/Users/devansh/Desktop/aiagent/Data-Driven-Profitability-and-Market-Expansion-Decision-System/amazon_sale_report.csv"
    TEST_JOB_ID = "test_job_001"

    db = get_database()

    # Store CSV path instead of bytes
    db.uploads.delete_one({"job_id": TEST_JOB_ID})
    db.uploads.insert_one({
        "job_id": TEST_JOB_ID,
        "filename": "amazon_sale_report.csv",
        "csv_path": TEST_CSV_PATH,  # store path not bytes
        "uploaded_at": datetime.utcnow(),
    })

    result = run(TEST_JOB_ID)
    print(f"\nResult: {result}")

    order_count = db.cleaned_orders.count_documents({"job_id": TEST_JOB_ID})
    kpi_doc = db.kpis.find_one({"job_id": TEST_JOB_ID})
    job_doc = db.processing_jobs.find_one({"job_id": TEST_JOB_ID})

    print(f"Orders in MongoDB: {order_count}")
    print(f"KPIs saved: {list(kpi_doc.keys()) if kpi_doc else 'None'}")
    print(f"Job status: {job_doc['status'] if job_doc else 'None'}")