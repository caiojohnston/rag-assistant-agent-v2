"""Limpeza de decisoes.csv."""
from __future__ import annotations

import pandas as pd

from cristalux.cleaning import parsers as p
from cristalux.cleaning.base import Resultado, canonico_por_fold
from cristalux.security.injection import detectar

COLUNAS = ["id_decisao", "data", "tipo", "descricao", "responsavel", "impacto", "resultado", "observacoes"]


def limpar_decisoes(raw: pd.DataFrame) -> Resultado:
    tipos = canonico_por_fold(raw["tipo"].map(p.limpar))
    vistos: set[tuple] = set()
    ok, rej = [], []
    for r in raw.to_dict("records"):
        v = {c: p.limpar(r[c]) for c in COLUNAS}
        base = {"linha_origem": r["linha_origem"], "id_sobrevivente": None, **{c: r[c] for c in COLUNAS}}
        if not v["descricao"] and not v["tipo"]:
            rej.append({**base, "motivo": "registro_vazio"})
            continue
        chave = tuple(v[c] for c in COLUNAS)
        if chave in vistos:
            rej.append({**base, "motivo": "duplicata_exata", "id_sobrevivente": v["id_decisao"]})
            continue
        vistos.add(chave)
        data, motivo, _ = p.parse_data(v["data"])
        padroes = detectar(" ".join(filter(None, [v["descricao"], v["resultado"], v["observacoes"]])))
        ok.append({
            "id_decisao": v["id_decisao"], "data": data,
            "tipo": tipos.get(p.fold(v["tipo"]), v["tipo"]),
            "descricao": v["descricao"], "responsavel": v["responsavel"], "impacto": v["impacto"],
            "resultado": v["resultado"], "observacoes": v["observacoes"],
            "suspeita_injection": bool(padroes), "padroes_injection": padroes,
            "flags": ["data_invalida"] if motivo else [],
            "linha_origem": r["linha_origem"],
        })
    clean = pd.DataFrame(ok)
    quarantine = pd.DataFrame(rej, columns=["linha_origem", "motivo", "id_sobrevivente"] + COLUNAS)
    res = Resultado(clean, quarantine, {
        "linhas_brutas": len(raw), "linhas_limpas": len(clean), "quarentena": len(quarantine),
        "suspeita_injection": int(clean["suspeita_injection"].sum()) if len(clean) else 0,
    })
    res.conferir_conservacao(len(raw))
    return res
