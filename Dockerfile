FROM python:3.11-slim

ENV APP_ROOT=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install .

# Modelo de embeddings local embutido na imagem: e a reserva se a cota de embeddings do Gemini acabar.
ENV FASTEMBED_CACHE_PATH=/opt/fastembed
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY app ./app
COPY sql ./sql
COPY specs ./specs
COPY notebooks ./notebooks
COPY docker/entrypoint.sh ./docker/entrypoint.sh
RUN sed -i 's/\r$//' docker/entrypoint.sh && chmod +x docker/entrypoint.sh

# Railway injeta PORT; localmente o padrao e 8501.
EXPOSE 8501
CMD ["./docker/entrypoint.sh"]
