#!/bin/sh
set -e
# Cria/atualiza schemas, views e papel somente leitura (idempotente).
python -m cristalux.db.setup
# Reindexa o corpus de texto (idempotente; so embeda o que mudou). Falha nao derruba o app.
python -m cristalux.rag.index || echo "aviso: indexacao do RAG falhou, o app sobe sem busca atualizada"
exec streamlit run app/streamlit_app.py --server.port="${PORT:-8501}" --server.address=0.0.0.0 --server.headless=true
