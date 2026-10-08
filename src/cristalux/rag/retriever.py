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


def _alerta(trechos: list) -> dict:
    """Destaca no Langfuse as buscas que trouxeram texto marcado como nao confiavel (possivel prompt injection)."""
    suspeitos = [t.id for t in trechos if t.confianca == "nao_confiavel"]
    if not suspeitos:
        return {}
    return {"level": "WARNING", "status_message": f"trecho nao confiavel recuperado: {', '.join(suspeitos)}"}


@obs.observar(name="retrieve-documents", as_type="retriever")
def buscar(consulta: str, k: int | None = None, threshold: float | None = None, filtro: dict | None = None,
           embedder: Embedder | None = None) -> list[Trecho]:
    """Devolve ate k trechos com similaridade (cosseno) acima do threshold, do mais ao menos similar."""
    embedder = embedder or get_embedder()
    k = k or settings.rag_k
    vetor = embedder.embed_query(consulta)  # pode trocar de backend se a cota do Gemini acabou
    backend = embedder.nome
    limite = threshold_do_backend(backend) if threshold is None else threshold
    obs.atualizar(input=consulta, metadata={"k": k, "threshold": limite, "filtro": filtro, "embeddings": backend})
    col = colecao(backend)
    if col.count() == 0:
        obs.atualizar(output=[])
        return []
    r = col.query(query_embeddings=[vetor], n_results=min(k, col.count()),
                  where=filtro or None, include=["documents", "metadatas", "distances"])
    trechos = []
    for cid, doc, meta, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0]):
        score = 1.0 - dist  # distancia cosseno -> similaridade
        if score >= limite:
            trechos.append(Trecho(meta.get("id", cid), meta.get("fonte", ""), doc, round(score, 4),
                                  meta.get("confianca", "alta"), meta))
    # Saida com o texto recuperado: e o contexto que o modelo viu ao decidir.
    obs.atualizar(output=[{"id": t.id, "fonte": t.fonte, "score": t.score, "confianca": t.confianca,
                           "texto": t.texto[:400]} for t in trechos],
                  metadata={"k": k, "threshold": limite, "filtro": filtro, "embeddings": backend,
                            "recuperados": len(trechos), "descartados_pelo_threshold": min(k, col.count()) - len(trechos)},
                  **_alerta(trechos))
    return trechos
