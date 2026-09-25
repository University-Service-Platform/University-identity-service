FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8001 \
    DATABASE_URL=sqlite:////data/identity.db

WORKDIR /app

# Dependencies first for better layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY scripts ./scripts
COPY app ./app

# Run as an unprivileged user; /data holds the SQLite database (mount a volume there)
RUN useradd --create-home --uid 10001 identity \
    && mkdir -p /data \
    && chown identity:identity /data
USER identity

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=3)"

CMD ["python", "scripts/start.py"]
