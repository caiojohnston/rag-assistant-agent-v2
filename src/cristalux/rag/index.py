"""Uso: python -m cristalux.rag.index   (idempotente)"""
from __future__ import annotations

from cristalux.rag import corpus
from cristalux.rag.store import indexar


def main() -> None:
    print(indexar(corpus.montar()))


if __name__ == "__main__":
    main()
