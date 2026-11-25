# AMLens backend + investigation agents.
# Build from the REPOSITORY ROOT (the image needs both backend/ and agents/):
#   docker build -f backend/Dockerfile -t amlens-backend .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    RUN_MIGRATIONS=true
WORKDIR /app
COPY backend/requirements.txt backend-requirements.txt
COPY agents/requirements.txt agents-requirements.txt
RUN pip install --no-cache-dir -r backend-requirements.txt -r agents-requirements.txt
# `import agents` resolves to /app/agents via PYTHONPATH.
COPY agents ./agents
COPY backend/app ./backend/app
COPY backend/alembic ./backend/alembic
COPY backend/alembic.ini ./backend/alembic.ini
RUN useradd --system --uid 1001 app && chown -R app /app
USER app
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).status==200 else 1)"
# Runtime settings come from the environment (DATABASE_URL, TOKEN_SECRET, AML_AGENT_DATABASE_URL,
# AZURE_OPENAI_*, RAG_SERVICE_URL, ...). Set RUN_MIGRATIONS=false when migrations run as a
# separate job (recommended with more than one replica).
CMD ["sh", "-c", "if [ \"$RUN_MIGRATIONS\" = true ]; then alembic upgrade head; fi && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
