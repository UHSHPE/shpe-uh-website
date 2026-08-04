# Pinned to match CI (.github/workflows/ci.yml), not the local 3.11 venv.
# python:3.12-slim is multi-arch, so this same file rebuilds on an ARM host
# (e.g. an Oracle Ampere VM) — rebuild there, never copy the x86 image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so editing app code doesn't reinstall every wheel.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Every writable path hangs off DATA_DIR (see config.py). Mount the
# persistent volume here; on another host, point DATA_DIR somewhere else.
ENV DATA_DIR=/data \
    PORT=8000

EXPOSE 8000

# --workers 1 is a correctness requirement, not tuning. Two independent
#   reasons: the slowapi rate limiter keeps its counters in process memory,
#   so N workers makes every limit N times looser; and SQLite is a single
#   file on a single-attach volume.
# --proxy-headers makes the app honour X-Forwarded-Proto, so FastAPI's
#   trailing-slash redirects emit https:// rather than a http:// redirect
#   that browsers block as mixed content.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --no-server-header"]
