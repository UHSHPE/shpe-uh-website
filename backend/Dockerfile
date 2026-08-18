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
# NOTE: --proxy-headers is deliberately NOT set, and neither is
#   --forwarded-allow-ips. Forwarded headers are handled in the app instead:
#   services/forwarded_proto.py takes the scheme (so redirects emit https://
#   rather than an http:// one browsers block as mixed content) and
#   services/rate_limit.py takes the client IP. Both read the RIGHTMOST entry;
#   uvicorn's middleware reads the leftmost, which the client supplies and can
#   spoof. --proxy-headers was previously set here with a comment claiming it
#   fixed the scheme -- it did not, because --forwarded-allow-ips defaults to
#   127.0.0.1 and the platform proxy is never that, so the headers were
#   ignored and the comment hid a live bug. Both need TRUST_PROXY_IP_HEADERS=1.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-server-header"]
