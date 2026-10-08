FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install .

COPY app ./app
COPY sql ./sql
COPY notebooks ./notebooks

# Railway injeta PORT; localmente o padrao e 8501.
CMD ["sh", "-c", "streamlit run app/streamlit_app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
