"""Experimentos que sustentam as decisoes do README: embedding, threshold e chunking (so retrieval, sem gerar texto).

Uso: python -m cristalux.eval.experimentos
Grava reports/experimentos.json e reports/experimentos.md.
"""
from __future__ import annotations

import json
from collections import defaultdict

import numpy as np

from cristalux.config import settings
from cristalux.eval.run import _ler
from cristalux.rag import chunking as ck
from cristalux.rag import corpus
from cristalux.rag.embeddings import GeminiEmbedder, LocalEmbedder

# Perguntas fora do corpus usadas so para calibrar o threshold (nao fazem parte do conjunto A).
NEGATIVAS_EXTRAS = [
    "Qual a receita da pizzaria do centro em 2023?", "Quem ganhou a Copa do Mundo de 2022?",
    "Como faço um bolo de cenoura?", "Qual a cotação do dólar hoje?", "Qual o salário do presidente da empresa?",
    "Qual a previsão do tempo para amanhã?", "Quantos funcionários a empresa tem em Manaus?",
    "Qual o endereço da sede da empresa?",
]
KS = (1, 3, 5)
THRESHOLDS = [0.30, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]


def _normalizar(m: np.ndarray) -> np.ndarray:
    return m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)


def variante_por_registro() -> list[ck.Chunk]:
    return corpus.montar()


def variante_por_ano(base: list[ck.Chunk]) -> list[ck.Chunk]:
    """Uma decisao por ano agrupadas num unico chunk (chunk maior)."""
    por_ano: dict[int, list[ck.Chunk]] = defaultdict(list)
    saida = []
    for c in base:
        if c.fonte == "decisao":
            por_ano[c.metadata["ano"]].append(c)
        else:
            saida.append(c)
    for ano, cs in por_ano.items():
        g = ck.Chunk("decisao", f"ano-{ano}", "\n".join(c.texto for c in cs), {"ids": [c.id for c in cs]})
        saida.append(g)
    return saida


def variante_dividida(base: list[ck.Chunk]) -> list[ck.Chunk]:
    """Cada decisao em dois chunks: cabecalho com descricao e outro com resultado e observacoes (chunk menor)."""
    saida = []
    for c in base:
        if c.fonte != "decisao":
            saida.append(c)
            continue
        corte = c.texto.find("Resultado:")
        saida.append(ck.Chunk("decisao", f"{c.id}#a", c.texto[:corte].strip(), {"ids": [c.id]}))
        saida.append(ck.Chunk("decisao", f"{c.id}#b", f"Decisao {c.id}. " + c.texto[corte:].strip(), {"ids": [c.id]}))
    return saida


def ids_do_chunk(c: ck.Chunk) -> set[str]:
    return set(c.metadata.get("ids", [])) or {c.id.split("#")[0]}


def avaliar(embedder, chunks: list[ck.Chunk], positivas: list[dict], negativas: list[str]) -> dict:
    docs = _normalizar(np.array(embedder.embed_documents([c.texto for c in chunks])))
    ids = [ids_do_chunk(c) for c in chunks]

    def ranking(pergunta):
        q = _normalizar(np.array([embedder.embed_query(pergunta)]))[0]
        sim = docs @ q
        ordem = np.argsort(-sim)
        return [(int(i), float(sim[i])) for i in ordem]

    ranks = [(p, ranking(p["pergunta"])) for p in positivas]
    neg = [ranking(q) for q in negativas]

    hits = {k: 0 for k in KS}
    rr = 0.0
    for p, r in ranks:
        esperado = set(p["ids_esperados"])
        pos = next((n for n, (i, _) in enumerate(r, 1) if ids[i] & esperado), None)
        for k in KS:
            hits[k] += int(pos is not None and pos <= k)
        rr += 1 / pos if pos else 0.0
    n = len(positivas)
    por_threshold = {}
    for t in THRESHOLDS:
        rec = sum(any(ids[i] & set(p["ids_esperados"]) and s >= t for i, s in r[:5]) for p, r in ranks) / n
        media_trechos = np.mean([sum(s >= t for _, s in r[:5]) for _, r in ranks])
        recusa = np.mean([sum(s >= t for _, s in r[:5]) == 0 for r in neg])
        por_threshold[t] = {"recall_at_5": round(rec, 3), "trechos_medios": round(float(media_trechos), 2),
                            "recusa_fora_do_corpus": round(float(recusa), 3)}
    return {"chunks": len(chunks), "hit": {f"@{k}": round(hits[k] / n, 3) for k in KS}, "mrr": round(rr / n, 3),
            "por_threshold": por_threshold,
            "score_positivas": {"min": round(min(r[0][1] for _, r in ranks), 3),
                                "media": round(float(np.mean([r[0][1] for _, r in ranks])), 3)},
            "score_negativas": {"max": round(max(r[0][1] for r in neg), 3),
                                "media": round(float(np.mean([r[0][1] for r in neg])), 3)}}


def main() -> None:
    casos = _ler("conjunto_a.jsonl")
    positivas = [c for c in casos if c["ids_esperados"]]
    negativas = [c["pergunta"] for c in casos if not c["ids_esperados"]] + NEGATIVAS_EXTRAS
    base = variante_por_registro()
    rel: dict = {"positivas": len(positivas), "negativas": len(negativas)}

    embedders = {"gemini-embedding-001": GeminiEmbedder(), "paraphrase-multilingual-MiniLM-L12-v2 (local)": LocalEmbedder()}
    rel["embedding"] = {nome: avaliar(e, base, positivas, negativas) for nome, e in embedders.items()}
    rel["chunking"] = {nome: avaliar(embedders["gemini-embedding-001"], ch, positivas, negativas) for nome, ch in {
        "1 decisao por chunk (adotado)": base, "decisoes agrupadas por ano": variante_por_ano(base),
        "decisao dividida em 2 chunks": variante_dividida(base)}.items()}

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.reports_dir / "experimentos.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Experimentos de retrieval", "", f"{rel['positivas']} perguntas com resposta no corpus e "
          f"{rel['negativas']} fora do corpus (2 do conjunto A e {len(NEGATIVAS_EXTRAS)} extras de calibracao).", ""]
    for secao, titulo in (("embedding", "Embedding (chunk de 1 decisao)"), ("chunking", "Chunking (embedding Gemini)")):
        md += [f"## {titulo}", "", "| Variante | Chunks | hit@1 | hit@3 | hit@5 | MRR | score minimo das positivas | score maximo das negativas |",
               "|---|---|---|---|---|---|---|---|"]
        for nome, r in rel[secao].items():
            md.append(f"| {nome} | {r['chunks']} | {r['hit']['@1']} | {r['hit']['@3']} | {r['hit']['@5']} | {r['mrr']} | "
                      f"{r['score_positivas']['min']} | {r['score_negativas']['max']} |")
        md.append("")
    md += ["## Varredura de threshold", ""]
    for nome, r in rel["embedding"].items():
        md += [f"### {nome}", "", "| Threshold | Recall@5 | Trechos retornados (media) | Recusa fora do corpus |", "|---|---|---|---|"]
        for t, v in r["por_threshold"].items():
            md.append(f"| {t} | {v['recall_at_5']} | {v['trechos_medios']} | {v['recusa_fora_do_corpus']} |")
        md.append("")
    (settings.reports_dir / "experimentos.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
