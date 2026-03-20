# ── Stage 1: build dependencies ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgl1 libglib2.0-0 libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: production image ──────────────────────────────────────────────────
FROM python:3.11-slim AS production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system govca \
    && adduser  --system --ingroup govca govca

COPY --from=builder /install /usr/local
COPY --chown=govca:govca . .

RUN mkdir -p /app/uploads && chown govca:govca /app/uploads

USER govca
EXPOSE 5000

ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["gunicorn", "wsgi:app", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]


# ── Stage 3: test runner ───────────────────────────────────────────────────────
FROM production AS test

USER root
RUN pip install --no-cache-dir pytest pytest-cov pytest-flask faker
USER govca

ENV FLASK_ENV=testing
CMD ["pytest", "tests/", "-v", "--tb=short", "--cov=app", "--cov-report=term-missing"]
