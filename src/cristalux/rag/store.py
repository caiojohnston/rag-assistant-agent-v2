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


def salvar_no_banco(backend: str) -> int:
    """Grava no Postgres (meta.vetores) os vetores da colecao do Chroma, para sobreviverem a novos deploys."""
    from psycopg.types.json import Jsonb

    from cristalux.db.setup import conectar

    col = colecao(backend)
    dados = col.get(include=["documents", "metadatas", "embeddings"])
    linhas = [(backend, i, d, Jsonb(m), [float(x) for x in v])
              for i, d, m, v in zip(dados["ids"], dados["documents"], dados["metadatas"], dados["embeddings"])]
    with conectar() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM meta.vetores WHERE backend = %s", (backend,))
        cur.executemany("INSERT INTO meta.vetores (backend, chunk_id, documento, metadata, vetor) VALUES (%s, %s, %s, %s, %s)",
                        linhas)
    return len(linhas)


def restaurar_do_banco(backend: str) -> int:
    """Se a colecao do Chroma estiver vazia, recarrega os vetores salvos no Postgres. Devolve quantos restaurou."""
    from cristalux.db.setup import conectar

    col = colecao(backend)
    if col.count() > 0:
        return 0
    try:
        with conectar() as conn, conn.cursor() as cur:
            cur.execute("SELECT chunk_id, documento, metadata, vetor FROM meta.vetores WHERE backend = %s", (backend,))
            linhas = cur.fetchall()
    except Exception:  # tabela ou banco indisponivel: segue sem restaurar
        return 0
    if linhas:
        col.upsert(ids=[l[0] for l in linhas], documents=[l[1] for l in linhas], metadatas=[l[2] for l in linhas],
                   embeddings=[l[3] for l in linhas])
    return len(linhas)


def indexar(chunks: list[Chunk], embedder: Embedder | None = None) -> dict:
    """Embeda so o que e novo ou mudou e remove o que saiu do corpus. Reindexar sem mudanca embeda zero."""
    embedder = embedder or get_embedder()
    nome_inicial = embedder.nome
    col = colecao(nome_inicial)
    desejados = {c.chunk_id: c for c in chunks}
    existentes = set(col.get(include=[])["ids"])

    novos = [c for i, c in desejados.items() if i not in existentes]
    removidos = list(existentes - set(desejados))
    if removidos:
        col.delete(ids=removidos)
    if novos:
        vetores = embedder.embed_documents([c.texto for c in novos])
        if embedder.nome != nome_inicial:  # a cota do primario acabou no meio: refaz na colecao do secundario
            return indexar(chunks, embedder)
        col.upsert(ids=[c.chunk_id for c in novos], embeddings=vetores,
                   documents=[c.texto for c in novos], metadatas=[c.metadata for c in novos])
    return {"backend": embedder.nome, "novos": len(novos), "removidos": len(removidos),
            "mantidos": len(desejados) - len(novos), "total": col.count()}
