# ============================================================
# Dockerfile — Amazon Sales Automated Insight System
#
# FIX LOG vs original:
#   • Original copied app/data/amazon_sales.csv at build time
#     which bakes the CSV into the image (bad practice + fails
#     if the file isn't there). CSV is now mounted at runtime.
#   • Added watchdog to requirements for --watch mode.
#   • CMD changed to run.py so all modes work via docker run flags.
#   • EXPOSE updated to respect PORT env var.
#   • Added PYTHONUNBUFFERED so logs appear in real-time.
# ============================================================

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt watchdog

COPY app/ .

RUN mkdir -p /app/outputs /app/data

EXPOSE ${PORT}

# Mount your CSV at runtime:
#   docker run -v /local/path/amazon_sales.csv:/app/data/amazon_sales.csv ...
# Then run any mode, e.g.:
#   docker run ... python run.py /app/data/amazon_sales.csv
# or
#   docker run -p 5000:5000 ... python run.py /app/data/amazon_sales.csv --dashboard

CMD ["python", "run.py", "--help"]
