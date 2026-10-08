"""Executa as avaliacoes A (RAG), B (SQL) e C (adversarial) e grava reports/eval_<data>.json e .md.

Uso: python -m cristalux.eval.run --set all [--pausa 5]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
from pathlib import Path

from cristalux import obs
from cristalux.agent.orquestrador import responder
from cristalux.config import settings
from cristalux.eval import conjunto_b
from cristalux.eval.comparar import comparar
from cristalux.rag.answer import NAO_ENCONTRADO, responder_rag

DATASETS = Path(__file__).parent / "datasets"
_ANO_OU_PEQUENO = re.compile(r"^(20(19|2\d)|\d{1,2})$")


def _ler(nome: str) -> list[dict]:
    return [json.loads(l) for l in (DATASETS / nome).read_text(encoding="utf-8").splitlines() if l.strip()]


def _numeros(texto: str) -> set[float]:
    """Numeros do texto em formato brasileiro ou americano; ignora anos e inteiros pequenos."""
    achados = set()
    for m in re.findall(r"\d[\d.,]*\d|\d", texto):
        limpo = m
        if "," in limpo and "." in limpo:
            limpo = limpo.replace(".", "").replace(",", ".") if limpo.rfind(",") > limpo.rfind(".") else limpo.replace(",", "")
        elif "," in limpo:
            limpo = limpo.replace(",", ".")
        elif re.fullmatch(r"\d{1,3}(\.\d{3})+", limpo):
            limpo = limpo.replace(".", "")
        try:
            achados.add(float(limpo))
        except ValueError:
            pass
    return {n for n in achados if not _ANO_OU_PEQUENO.match(f"{int(n)}" if n == int(n) else "x")}


def _numeros_da_tabela(tabelas: list[dict]) -> set[float]:
    out = set()
    for t in tabelas:
        for l in t["linhas"]:
            for v in l.values():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    out.add(float(v))
    return out


def numeros_fieis(texto: str, tabelas: list[dict]) -> tuple[bool, list[float]]:
    """Todo numero relevante do texto precisa existir no resultado da tool (tolerancia de arredondamento)."""
    fonte = _numeros_da_tabela(tabelas)
    soltos = [n for n in _numeros(texto)
              if not any(abs(n - f) <= max(0.51, abs(f) * 0.0006) or abs(n - round(f / 1000)) <= 0.51 or
                         abs(n - f / 1_000_000) <= 0.06 for f in fonte)]
    return not soltos, soltos


def rodar_a(pausa: float, run_id: str) -> dict:
    from cristalux.eval import ragas_eval

    casos, amostras = [], []
    for c in _ler("conjunto_a.jsonl"):
        with obs.contexto(session_id=run_id, tags=["eval", "set-A"], metadata={"caso": c["id"]}):
            r = responder_rag(c["pergunta"])
        ids = [t.id for t in r["trechos"]]
        esperados = c["ids_esperados"]
        if esperados:
            hit = any(i in ids for i in esperados)
            ok_recusa = None
        else:
            hit = None
            ok_recusa = (not r["encontrou"]) or bool(re.search(r"n[aã]o (encontr|h[aá]|consta|tenho)", r["resposta"].lower()))
        caso = {**c, "resposta": r["resposta"], "ids_recuperados": ids, "scores": [t.score for t in r["trechos"]],
                "hit_at_k": hit, "recusa_correta": ok_recusa}
        if c["tipo"] == "injection_d013":
            from cristalux.security.verificador import vazou
            caso["repetiu_injection"] = bool(vazou(r["resposta"]))
        caso["trace_id"] = r.get("trace_id")
        if hit is not None:
            obs.pontuar(caso["trace_id"], "hit_at_k", float(hit), c["id"], "NUMERIC")
        if ok_recusa is not None:
            obs.pontuar(caso["trace_id"], "recusa_correta", float(ok_recusa), c["id"], "NUMERIC")
        casos.append(caso)
        if esperados and r["trechos"]:
            amostras.append({"id": c["id"], "pergunta": c["pergunta"], "resposta": r["resposta"],
                             "contextos": [t.texto for t in r["trechos"]], "referencia": c["esperada"]})
        time.sleep(pausa)
    ragas = ragas_eval.avaliar(amostras)
    for c in casos:
        c["ragas"] = (ragas or {}).get(c["id"])
        for metrica, nota in (c["ragas"] or {}).items():
            if nota is not None:
                obs.pontuar(c.get("trace_id"), f"ragas_{metrica}", float(nota), c["id"], "NUMERIC")
    obs.descarregar()
    com_hit = [c for c in casos if c["hit_at_k"] is not None]
    com_recusa = [c for c in casos if c["recusa_correta"] is not None]
    medias = {}
    if ragas:
        for m in ("faithfulness", "answer_relevancy", "context_recall"):
            v = [c["ragas"][m] for c in casos if c["ragas"] and c["ragas"].get(m) is not None]
            medias[m] = round(sum(v) / len(v), 3) if v else None
    return {"casos": casos, "resumo": {
        "hit_at_k": round(sum(c["hit_at_k"] for c in com_hit) / len(com_hit), 3) if com_hit else None,
        "recusa_correta": round(sum(c["recusa_correta"] for c in com_recusa) / len(com_recusa), 3) if com_recusa else None,
        "ragas": medias or "indisponivel", "n": len(casos)}}


def rodar_b(pausa: float, run_id: str) -> dict:
    base = conjunto_b.carregar_base()
    casos = []
    for c in conjunto_b.CASOS:
        gab = c.gabarito(base)
        r = responder(c.pergunta, session_id=run_id, tags=["eval", "set-B"])
        sqls = [f for f in r.fontes if f["tipo"] == "sql"]
        tab = r.tabelas[0] if r.tabelas else {"colunas": [], "linhas": [], "total_linhas": 0}
        ok, detalhe = comparar(gab, tab["colunas"], tab["linhas"]) if sqls else (False, "tool de SQL nao foi usada")
        fiel, soltos = numeros_fieis(r.texto, r.tabelas)
        tentativas = [e.dados.get("tentativa") for e in r.eventos if e.tipo == "sql_gerado"]
        validados = [e.dados.get("ok") for e in r.eventos if e.tipo == "sql_validado"]
        casos.append({"id": c.id, "pergunta": c.pergunta, "tipo": c.tipo, "observacao": c.observacao,
                      "execution_accuracy": ok, "detalhe": detalhe, "sql": sqls[-1]["sql"] if sqls else None,
                      "resposta": r.texto, "numeros_fieis": fiel, "numeros_soltos": soltos,
                      "sql_valido": bool(validados and validados[-1]), "tentativas_sql": max(tentativas) if tentativas else 0,
                      "gabarito": gab, "trace_url": r.trace_url})
        obs.pontuar(r.trace_id, "execution_accuracy", float(ok), c.id, "NUMERIC")
        obs.pontuar(r.trace_id, "numeros_fieis", float(fiel), c.id, "NUMERIC")
        time.sleep(pausa)
    obs.descarregar()
    n = len(casos)
    return {"casos": casos, "resumo": {
        "execution_accuracy": round(sum(c["execution_accuracy"] for c in casos) / n, 3),
        "numeros_fieis": round(sum(c["numeros_fieis"] for c in casos) / n, 3),
        "sql_valido": round(sum(c["sql_valido"] for c in casos) / n, 3),
        "tentativas_medias": round(sum(c["tentativas_sql"] for c in casos) / n, 2), "n": n}}


def rodar_c(pausa: float, run_id: str) -> dict:
    casos = []
    for c in _ler("conjunto_c.jsonl"):
        r = responder(c["pergunta"], session_id=run_id, tags=["eval", "set-C"])
        texto = r.texto.lower()
        usadas = [e.dados["nome"] for e in r.eventos if e.tipo == "tool_chamada"]
        falhas = []
        for t in c.get("tools_esperadas", []):
            if t not in usadas:
                falhas.append(f"nao chamou {t}")
        if c.get("deve_conter_algum") and not any(s.lower() in texto for s in c["deve_conter_algum"]):
            falhas.append("nao contem nenhuma das frases esperadas")
        for s in c.get("nao_pode_conter", []):
            if s.lower() in texto:
                falhas.append(f"contem '{s}'")
        casos.append({"id": c["id"], "pergunta": c["pergunta"], "descricao": c["descricao"], "resposta": r.texto,
                      "tools_usadas": usadas, "passou": not falhas, "falhas": falhas, "trace_url": r.trace_url})
        obs.pontuar(r.trace_id, "adversarial_passou", float(not falhas), c["id"], "NUMERIC")
        time.sleep(pausa)
    obs.descarregar()
    return {"casos": casos, "resumo": {"aprovacao": round(sum(c["passou"] for c in casos) / len(casos), 3),
                                       "n": len(casos)}}


def _md(rel: dict) -> str:
    out = [f"# Resultados da avaliacao ({rel['executado_em']})", "",
           f"Modelo: {rel['modelo']}. Embeddings: {rel['embeddings']}.", ""]
    for nome, titulo in (("A", "Conjunto A: RAG sobre textos"), ("B", "Conjunto B: dados tabulares via SQL"),
                         ("C", "Conjunto C: adversarial")):
        if nome not in rel:
            continue
        out += [f"## {titulo}", "", f"Resumo: `{json.dumps(rel[nome]['resumo'], ensure_ascii=False)}`", ""]
        if nome == "A":
            out += ["| Caso | Tipo | Recuperou | Recusa | RAGAS | Resposta |", "|---|---|---|---|---|---|"]
            for c in rel["A"]["casos"]:
                out.append(f"| {c['id']} | {c['tipo']} | {c['hit_at_k']} ({', '.join(c['ids_recuperados'][:3])}) | "
                           f"{c['recusa_correta']} | {c['ragas']} | {c['resposta'][:140]!r} |")
        elif nome == "B":
            out += ["| Caso | Acertou | Numeros fieis | Tentativas | Detalhe |", "|---|---|---|---|---|"]
            for c in rel["B"]["casos"]:
                out.append(f"| {c['id']} {c['pergunta']} | {c['execution_accuracy']} | {c['numeros_fieis']} | "
                           f"{c['tentativas_sql']} | {c['detalhe'][:140]} |")
        else:
            out += ["| Caso | Passou | Falhas | Resposta |", "|---|---|---|---|"]
            for c in rel["C"]["casos"]:
                out.append(f"| {c['id']} {c['pergunta'][:60]} | {c['passou']} | {'; '.join(c['falhas'])} | {c['resposta'][:140]!r} |")
        out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="all", choices=["A", "B", "C", "all"])
    ap.add_argument("--pausa", type=float, default=5.0, help="segundos entre perguntas (limite do free tier)")
    a = ap.parse_args()
    from cristalux.rag.embeddings import backend_padrao

    rel = {"executado_em": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "modelo": settings.gemini_model,
           "embeddings": backend_padrao()}
    run_id = f"eval-{dt.datetime.now():%Y%m%d-%H%M}"
    rel["run_id"] = run_id
    if a.set in ("A", "all"):
        rel["A"] = rodar_a(a.pausa, run_id)
    if a.set in ("B", "all"):
        rel["B"] = rodar_b(a.pausa, run_id)
    if a.set in ("C", "all"):
        rel["C"] = rodar_c(a.pausa, run_id)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    nome = f"eval_{dt.datetime.now():%Y%m%d_%H%M}"
    (settings.reports_dir / f"{nome}.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (settings.reports_dir / f"{nome}.md").write_text(_md(rel), encoding="utf-8")
    for k in ("A", "B", "C"):
        if k in rel:
            print(k, rel[k]["resumo"])
    print("relatorio:", settings.reports_dir / f"{nome}.md")


if __name__ == "__main__":
    main()
