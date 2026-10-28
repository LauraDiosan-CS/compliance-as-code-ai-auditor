# Compliance-as-Code AI Auditor: FastAPI backend.
#   docker build -t ccauditor-api app/backend
#   docker run --rm -p 8000:8000 ccauditor-api
# The container has no logged-in Claude Code CLI, so CCAUDITOR_SERVERLESS=1 makes every audit run in
# deterministic mode (rules only). Unset it and mount a logged-in ~/.claude to enable hybrid mode.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CCAUDITOR_SERVERLESS=1 \
    CCAUDITOR_CORS_ORIGINS=*

# git is used by POST /audit to clone repo_url (shallow clone).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY pyproject.toml ./
COPY ccauditor ./ccauditor
RUN pip install . && useradd --create-home --uid 10001 auditor

USER auditor
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4); sys.exit(0)"
CMD ["uvicorn", "ccauditor.api:app", "--host", "0.0.0.0", "--port", "8000"]
