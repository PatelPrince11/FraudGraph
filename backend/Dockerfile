# API image. Build context is backend/, so only files in backend/ can be copied in.
FROM python:3.13-slim

# No .pyc files, logs straight to `docker logs` without buffering, no pip cache in the image.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# XGBoost's Linux build needs the OpenMP runtime, which the slim image leaves out.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requirements BEFORE code: Docker caches each step, so editing a .py file
# reuses the (slow) install layer instead of reinstalling every package.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Don't run as root: if the app is ever compromised, the attacker isn't root in the container.
RUN useradd --create-home --uid 1000 appuser
USER appuser

# The model isn't baked in: it's mounted at runtime (see docker-compose.yml),
# so retraining doesn't require rebuilding the image.
ENV MODEL_DIR=/models
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

# 2 worker processes, each with its own Python interpreter, so one slow request
# (a big graph) can't stall everyone else's. Measured: this does NOT change
# single-user latency (the 3 requests per click only add ~12ms to /risk either way);
# it matters once several people use the dashboard at once.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
