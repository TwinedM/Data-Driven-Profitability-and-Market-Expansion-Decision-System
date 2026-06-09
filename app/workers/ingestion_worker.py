"""
ingestion_worker.py — Worker 1: Ingestion
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import io
import gc
import traceback
from datetime import datetime

import pandas as pd

from database import get_database
from column_mapper import auto_detect_columns, apply_mapping, get_missing_required
from kpi_engine import load_data_from_df, compute_kpis


def run(job_id: str) -> dict:
    db = get_database()
    _update_job(db, job_id, "ingesting")
    print(f"[Ingestion] Starting job {job_id}")

    try:
        # Step 1: Load CSV
        upload = db.uploads.find_one({"job_id": job_id})
        if not upload:
            raise ValueError(f"No upload found for job_id: {job_id}")

        if "csv_path" in upload:
            df_raw = pd.read_csv(upload["csv_path"], low_memory=False)
        else:
            df_raw = pd.read_csv(io.BytesIO(upload["csv_bytes"]))

        filename = upload.get("filename", "unknown.csv")
        print(f"[Ingestion] Loaded CSV: {filename} — {len(df_raw)} rows")

        # Step 2: Detect and map columns
        headers = df_raw.columns.tolist()
        mapping = auto_detect_columns(headers)
        missing = get_missing_required(mapping)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        df_mapped = apply_mapping(df_raw.copy(), mapping)
        try:
            del df_raw
        except NameError:
            pass
        gc.collect()

        # Step 3: Clean and compute KPIs
        df_clean = load_data_from_df(df_mapped)
        del df_mapped
        gc.collect()

        kpis = compute_kpis(df_clean)
        print(f"[Ingestion] KPIs computed — "
              f"Revenue: ₹{kpis['total_revenue']:,.0f} | "
              f"Orders: {kpis['total_orders']:,} | "
              f"Fulfillment: {kpis['fulfillment_rate']:.1f}%")

        # Step 4: Save sample to MongoDB
        sample_records = df_clean.head(10).to_dict(orient="records")
        sample_records = _clean_for_mongo(sample_records)
        total_rows = len(df_clean)
        columns = list(df_clean.columns)
        del df_clean
        gc.collect()

        db.cleaned_orders.delete_many({"job_id": job_id})
        db.cleaned_orders.insert_one({
            "job_id": job_id,
            "total_rows": total_rows,
            "sample_rows": sample_records,
            "columns": columns,
            "stored_at": datetime.utcnow(),
        })
        print(f"[Ingestion] Saved summary of {total_rows} orders to MongoDB (sample only)")

        # Step 5: Save KPIs
        kpi_doc = _serialize_kpis(kpis, job_id)
        del kpis
        gc.collect()

        db.kpis.delete_one({"job_id": job_id})
        db.kpis.insert_one(kpi_doc)
        print(f"[Ingestion] KPIs saved to MongoDB")

        # Step 6: Update status
        _update_job(db, job_id, "analyzing", {
            "ingestion_summary": {
                "total_rows": total_rows,
                "clean_rows": total_rows,
                "total_revenue": kpi_doc.get("total_revenue"),
                "total_orders": kpi_doc.get("total_orders"),
                "fulfillment_rate": kpi_doc.get("fulfillment_rate"),
                "filename": filename,
            }
        })

        print(f"[Ingestion] ✅ Job {job_id} ingestion complete")

        return {
            "status": "success",
            "job_id": job_id,
            "rows_processed": total_rows,
            "total_revenue": kpi_doc.get("total_revenue"),
            "total_orders": kpi_doc.get("total_orders"),
        }

    except Exception as e:
        error_msg = str(e)
        print(f"[Ingestion] ❌ Job {job_id} failed: {error_msg}")
        print(traceback.format_exc())
        _update_job(db, job_id, "failed", {"error": error_msg, "failed_at_stage": "ingestion"})
        return {"status": "failed", "job_id": job_id, "error": error_msg}


def _update_job(db, job_id: str, status: str, extra: dict = None):
    update = {"status": status, "updated_at": datetime.utcnow()}
    if extra:
        update.update(extra)
    db.processing_jobs.update_one({"job_id": job_id}, {"$set": update}, upsert=True)


def _clean_for_mongo(records: list) -> list:
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
                clean_record[key] = value.item()
            else:
                clean_record[key] = value
        cleaned.append(clean_record)
    return cleaned


def _serialize_kpis(kpis: dict, job_id: str) -> dict:
    import math
    import numpy as np
    safe = {"job_id": job_id, "created_at": datetime.utcnow()}
    for key, val in kpis.items():
        if isinstance(val, pd.DataFrame):
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