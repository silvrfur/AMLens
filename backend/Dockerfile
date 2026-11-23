FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
# NOTE: app.services.agent_bridge imports the `agents` package (member3-agents);
# it must be added to this image (or PYTHONPATH) before the container can start.
EXPOSE 8000
# Apply database migrations, then serve. DATABASE_URL must be set at runtime.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
