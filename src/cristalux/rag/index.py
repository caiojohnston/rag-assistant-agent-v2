"""Uso: python -m cristalux.rag.index   (idempotente)"""
from __future__ import annotations

import os

from cristalux.rag import corpus
from cristalux.rag.store import indexar, restaurar_do_banco, salvar_no_banco


def main() -> None:
    from cristalux.rag.embeddings import LocalEmbedder, backend_padrao

    chunks = corpus.montar()
    backends = ["gemini", "local"] if backend_padrao() == "gemini" else ["local"]
    for b in backends:  # restaura do Postgres o que um deploy anterior ja tinha embedado
        print(f"restaurados do banco ({b}):", restaurar_do_banco(b))
    print(indexar(chunks))
    # Mantem tambem o indice do modelo local, usado como reserva se a cota de embeddings do Gemini acabar.
    if backend_padrao() == "gemini" and os.getenv("EMBEDDING_FALLBACK", "local") != "off":
        try:
            print(indexar(chunks, LocalEmbedder()))
        except Exception as e:
            print(f"aviso: indice de reserva nao criado ({type(e).__name__})")
    for b in backends:  # guarda no Postgres para o proximo deploy
        try:
            print(f"salvos no banco ({b}):", salvar_no_banco(b))
        except Exception as e:
            print(f"aviso: vetores nao salvos no banco ({type(e).__name__})")


if __name__ == "__main__":
    main()
