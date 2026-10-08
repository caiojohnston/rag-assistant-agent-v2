"""Retrieval semantico com threshold de similaridade."""
from __future__ import annotations

from dataclasses import dataclass

from cristalux import obs
from cristalux.config import settings
from cristalux.rag.embeddings import THRESHOLD_PADRAO, Embedder, get_embedder
from cristalux.rag.store import colecao


@dataclass
class Trecho:
    id: str
    fonte: str
    texto: str
    score: float
    confianca: str
    metadata: dict


def threshold_do_backend(backend: str) -> float:
    return settings.rag_threshold if settings.rag_threshold is not None else THRESHOLD_PADRAO.get(backend, 0.5)


@obs.observar(name="rag.retrieve", as_type="retriever")
def buscar(consulta: str, k: int | None = None, threshold: float | None = None, filtro: dict | None = None,
           embedder: Embedder | None = None) -> list[Trecho]:
    """Devolve ate k trechos com similaridade (cosseno) acima do threshold, do mais ao menos similar."""
    embedder = embedder or get_embedder()
    k = k or settings.rag_k
    limite = threshold_do_backend(embedder.nome) if threshold is None else threshold
    col = colecao(embedder.nome)
    if col.count() == 0:
        return []
    r = col.query(query_embeddings=[embedder.embed_query(consulta)], n_results=min(k, col.count()),
                  where=filtro or None, include=["documents", "metadatas", "distances"])
    trechos = []
    for cid, doc, meta, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0]):
        score = 1.0 - dist  # distancia cosseno -> similaridade
        if score >= limite:
            trechos.append(Trecho(meta.get("id", cid), meta.get("fonte", ""), doc, round(score, 4),
                                  meta.get("confianca", "alta"), meta))
    obs.atualizar_span(input={"consulta": consulta, "k": k, "threshold": limite},
                       output=[{"id": t.id, "score": t.score} for t in trechos])
    return trechos
