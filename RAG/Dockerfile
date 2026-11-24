# AMLens RAG service. Build from this folder:  docker build -t amlens-rag RAG
# Default: Azure AI Search backend only (small image, no torch).
# For the local FAISS backend:  --build-arg RAG_REQUIREMENTS=requirements.txt
FROM python:3.12-slim
ARG RAG_REQUIREMENTS=requirements-azure.txt
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RAG_BACKEND=azure
WORKDIR /app
COPY requirements.txt requirements-azure.txt ./
RUN pip install --no-cache-dir -r ${RAG_REQUIREMENTS}
COPY app ./app
# The FAISS index (4.5 MB) is only read when RAG_BACKEND=faiss.
COPY indexes ./indexes
RUN useradd --system --uid 1001 app && chown -R app /app
USER app
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=4).status==200 else 1)"
# Settings (AZURE_SEARCH_*, AZURE_OPENAI_*, RAG_CORS_ORIGINS) come from the environment.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
