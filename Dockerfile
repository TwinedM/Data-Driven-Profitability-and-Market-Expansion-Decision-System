# ── Layer 1: Base image ───────────────────────────────────────
# We start FROM an official Python image, not from scratch.
# "3.11-slim" = Python 3.11, but stripped of extras we don't need.
# "slim" cuts image size from ~900MB to ~130MB.
FROM python:3.11-slim

# ── Layer 2: Working directory ────────────────────────────────
# All subsequent commands run from /app inside the contain
er.
# This is like doing "mkdir /app && cd /app".
WORKDIR /app

# ── Layer 3: Install dependencies FIRST (before copying code) ─
# WHY THIS ORDER MATTERS:
# Docker caches each layer. If you copy your code first,
# then every code change forces a full pip install (~2 min).
# By copying requirements.txt first, pip install is cached
# and only re-runs if requirements.txt actually changes.
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Layer 4: Copy application code ───────────────────────────
# Now copy everything else. Code changes only rebuild THIS layer.
COPY app/ ./app/

COPY "Amazon Sale Report.csv" ./

# ── Layer 5: Create output directory ─────────────────────────
# The container needs this folder to save generated reports.
RUN mkdir -p /app/outputs

# ── Environment variables ─────────────────────────────────────
# PORT is read by Flask/FastAPI to know which port to listen on.
# Render sets this automatically — we just need to read it.
ENV PORT=5000

# ── Expose the port ───────────────────────────────────────────
# EXPOSE documents which port the app uses.
# It does NOT publish the port — that happens at "docker run".
EXPOSE 5000

# ── Layer 6: Start command ────────────────────────────────────
# CMD is what runs when the container starts.
# Use JSON array form ["cmd", "arg"] — not shell string form.
# 0.0.0.0 means "listen on all network interfaces inside container"
# Without this, the app listens only on localhost INSIDE the container
# and is unreachable from outside.
CMD ["python", "app/dashboard.py"]


