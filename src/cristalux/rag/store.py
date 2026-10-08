"""Colecao do ChromaDB e indexacao incremental."""
from __future__ import annotations

import chromadb

from cristalux.config import settings
from cristalux.rag.chunking import Chunk
from cristalux.rag.embeddings import Embedder, get_embedder


def colecao(backend: str):
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    cliente = chromadb.PersistentClient(path=str(settings.chroma_path))
    return cliente.get_or_create_collection(name=f"cristalux_{backend}", metadata={"hnsw:space": "cosine"})


def indexar(chunks: list[Chunk], embedder: Embedder | None = None) -> dict:
    """Embeda so o que e novo ou mudou e remove o que saiu do corpus. Reindexar sem mudanca embeda zero."""
    embedder = embedder or get_embedder()
    col = colecao(embedder.nome)
    desejados = {c.chunk_id: c for c in chunks}
    existentes = set(col.get(include=[])["ids"])

    novos = [c for i, c in desejados.items() if i not in existentes]
    removidos = list(existentes - set(desejados))
    if removidos:
        col.delete(ids=removidos)
    if novos:
        vetores = embedder.embed_documents([c.texto for c in novos])
        col.upsert(ids=[c.chunk_id for c in novos], embeddings=vetores,
                   documents=[c.texto for c in novos], metadatas=[c.metadata for c in novos])
    return {"backend": embedder.nome, "novos": len(novos), "removidos": len(removidos),
            "mantidos": len(desejados) - len(novos), "total": col.count()}
