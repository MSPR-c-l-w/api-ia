# ──────────────────────────────────────────────
# Stage 1 — dependency builder
# ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

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
# Stage 2 — production image
# ──────────────────────────────────────────────
FROM python:3.12-slim AS production

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION="dev"

LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.title="HealthAI Coach API" \
      org.opencontainers.image.description="Microservice Flask pour les recommandations nutrition et sport IA" \
      org.opencontainers.image.source="https://github.com/MSPR-c-l-w/api-ia" \
      org.opencontainers.image.licenses="MIT"

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home --shell /sbin/nologin appuser

# Copy only the installed virtualenv — no build tools in production image
COPY --from=builder /opt/venv /opt/venv

# Copy application code with correct ownership
COPY --chown=appuser:appgroup app/ ./app/
COPY --chown=appuser:appgroup run.py .

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c \
        "import urllib.request, os; \
         urllib.request.urlopen( \
             'http://localhost:' + os.environ.get('PORT','8000') + '/health' \
         )" || exit 1

CMD ["sh", "-c", "hypercorn app.main:asgi_app --bind 0.0.0.0:${PORT:-8000}"]
