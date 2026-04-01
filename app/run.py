"""
run.py — Automation Entry Point
Amazon Sales Automated Insight System

Modes:
  python run.py amazon_sales.csv                          → run once
  python run.py amazon_sales.csv --email you@gmail.com   → run + email
  python run.py amazon_sales.csv --schedule               → daily at 8 AM
  python run.py amazon_sales.csv --watch                  → trigger on new CSV
"""

import argparse, sys, time
from pathlib import Path
import schedule


def run_pipeline(csv_path, email=None, save_path="report.html"):
    import report
    html, insights = report.run(csv_path, email_to=email, save_path=save_path)
    high = [i for i in insights if i.impact == "High"]
    print(f"\n✓ {len(insights)} insights | {len(high)} HIGH-impact")
    for ins in high:
        print(f"  ⚠  {ins.title}")
    return insights


def schedule_daily(csv_path, email, run_time="08:00"):
    print(f"[Scheduler] Daily at {run_time}. Ctrl+C to stop.")
    schedule.every().day.at(run_time).do(run_pipeline, csv_path=csv_path, email=email)
    run_pipeline(csv_path, email)
    while True:
        schedule.run_pending()
        time.sleep(30)


def watch_folder(csv_path, email=None):
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("Install watchdog: pip install watchdog")
        sys.exit(1)

    class Handler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.src_path.endswith(".csv"):
                print(f"[Watch] Changed: {event.src_path}")
                run_pipeline(event.src_path, email)
        def on_created(self, event):
            if event.src_path.endswith(".csv"):
                print(f"[Watch] New file: {event.src_path}")
                run_pipeline(event.src_path, email)

    watch_dir = str(Path(csv_path).parent.resolve())
    obs = Observer()
    obs.schedule(Handler(), watch_dir, recursive=False)
    obs.start()
    print(f"[Watch] Watching {watch_dir} for CSV changes. Ctrl+C to stop.")
    run_pipeline(csv_path, email)
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Amazon Sales Automated Insight System")
    p.add_argument("csv",            help="Path to Amazon sales CSV")
    p.add_argument("--email",        default=None, help="Deliver report to this email")
    p.add_argument("--save",         default="report.html", help="Output HTML path")
    p.add_argument("--schedule",     action="store_true", help="Run daily at --time")
    p.add_argument("--watch",        action="store_true", help="Watch folder for new CSVs")
    p.add_argument("--time",         default="08:00", help="Daily run time HH:MM")
    a = p.parse_args()

    if a.watch:         watch_folder(a.csv, a.email)
    elif a.schedule:    schedule_daily(a.csv, a.email, a.time)
    else:               run_pipeline(a.csv, a.email, a.save)
