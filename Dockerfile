FROM python:3.11-slim

ENV APP_ROOT=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install .

COPY app ./app
COPY sql ./sql
COPY specs ./specs
COPY notebooks ./notebooks
COPY docker/entrypoint.sh ./docker/entrypoint.sh
RUN sed -i 's/\r$//' docker/entrypoint.sh && chmod +x docker/entrypoint.sh

# Railway injeta PORT; localmente o padrao e 8501.
EXPOSE 8501
CMD ["./docker/entrypoint.sh"]
