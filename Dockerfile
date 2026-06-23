# ──────────────────────────────────────────────
# Stage 1 — Python dependency builder
# ──────────────────────────────────────────────
FROM python:3.14-slim-bookworm AS builder

ENV VIRTUAL_ENV=/opt/venv \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt


# ──────────────────────────────────────────────
# Stage 2 — Production image with embedded MongoDB 7
# ──────────────────────────────────────────────
FROM python:3.14-slim-bookworm AS production

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION="dev"

LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.title="HealthAI Coach API" \
      org.opencontainers.image.description="Microservice Flask — nutrition & sport IA avec MongoDB intégré" \
      org.opencontainers.image.source="https://github.com/MSPR-c-l-w/api-ia" \
      org.opencontainers.image.licenses="MIT"

# ── Upgrade base packages first to patch any known CVEs ────────────────────
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ── Install MongoDB 7 (server only — lean install) ─────────────────────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends gnupg curl ca-certificates && \
    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
        gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor && \
    echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \
        https://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main" \
        > /etc/apt/sources.list.d/mongodb-org-7.0.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends mongodb-org-server && \
    # Remove install-only tools to slim the image
    apt-get purge -y gnupg curl && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    # Default URI points to the embedded MongoDB instance
    MONGODB_URI=mongodb://localhost:27017/healthai_coach

WORKDIR /app

# Non-root user + MongoDB data directory (created before USER switch)
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home --shell /sbin/nologin appuser && \
    mkdir -p /data/db && \
    chown -R appuser:appgroup /data/db

# Python virtualenv from builder stage
COPY --from=builder /opt/venv /opt/venv

# Application code
COPY --chown=appuser:appgroup app/ ./app/
COPY --chown=appuser:appgroup run.py .
COPY --chown=appuser:appgroup docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

USER appuser

# Named volume so MongoDB data survives container restarts
VOLUME /data/db

EXPOSE 8000

# start-period is longer to account for MongoDB first-run initialisation
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c \
        "import urllib.request, os; \
         urllib.request.urlopen( \
             'http://localhost:' + os.environ.get('PORT','8000') + '/health' \
         )" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
