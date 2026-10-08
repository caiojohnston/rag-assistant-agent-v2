"""Uso: python -m cristalux.rag.index   (idempotente)"""
from __future__ import annotations

import os

from cristalux.rag import corpus
from cristalux.rag.store import indexar


def main() -> None:
    from cristalux.rag.embeddings import LocalEmbedder, backend_padrao

    chunks = corpus.montar()
    print(indexar(chunks))
    # Mantem tambem o indice do modelo local, usado como reserva se a cota de embeddings do Gemini acabar.
    if backend_padrao() == "gemini" and os.getenv("EMBEDDING_FALLBACK", "local") != "off":
        try:
            print(indexar(chunks, LocalEmbedder()))
        except Exception as e:
            print(f"aviso: indice de reserva nao criado ({type(e).__name__})")


if __name__ == "__main__":
    main()
