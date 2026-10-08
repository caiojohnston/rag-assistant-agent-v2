"""Limpeza de estoque_logistica.csv."""
from __future__ import annotations

import re
from datetime import date

import pandas as pd

from cristalux.cleaning import parsers as p
from cristalux.cleaning.base import Resultado, canonico_por_fold, completude

CAMPOS = ["nome_produto", "categoria", "estoque_atual", "estoque_minimo", "ultima_reposicao",
          "lead_time_dias", "fornecedor", "custo_unitario", "localizacao_deposito", "status"]

_ABREV = {"dir": "direito", "esq": "esquerdo", "lat": "lateral", "diant": "dianteiro", "tras": "traseiro"}
_STOP = {"de", "da", "do", "e"}


def chave_produto(nome: str) -> str:
    """Nome sem acento, abreviacoes expandidas, sem preposicoes e com palavras em ordem alfabetica."""
    tokens = re.findall(r"[a-z0-9]+", p.fold(nome))
    tokens = [_ABREV.get(t, t) for t in tokens if t not in _STOP]
    return " ".join(sorted(tokens))


def _local(texto):
    t = p.limpar(texto)
    if t is None:
        return None
    partes = re.split(r"[-\s]+", t.strip())
    return "-".join([partes[0].capitalize()] + [x.upper() for x in partes[1:]])


def _status(texto):
    f = p.fold(p.limpar(texto))
    return f.replace(" ", "_") if f else None


def _invalido(l: dict) -> bool:
    """Estoque ausente ou negativo invalida o registro."""
    return l["estoque_atual"] is None or l["estoque_atual"] < 0


def limpar_estoque(raw: pd.DataFrame) -> Resultado:
    categorias = canonico_por_fold(raw["categoria"].map(p.limpar))
    raw_por_linha = {x["linha_origem"]: x for x in raw.to_dict("records")}

    def rejeitada(linha_origem, motivo, sobrevivente):
        original = {c: v for c, v in raw_por_linha[linha_origem].items() if c != "linha_origem"}
        return {"linha_origem": linha_origem, "motivo": motivo, "id_sobrevivente": sobrevivente, **original}

    linhas, rej = [], []
    for r in raw.to_dict("records"):
        nome = p.limpar(r["nome_produto"])
        if nome is None:
            rej.append(rejeitada(r["linha_origem"], "registro_vazio", None))
            continue
        flags = []
        reposicao, motivo = p.parse_data(r["ultima_reposicao"])[:2]
        if reposicao and reposicao > date.today():
            reposicao, motivo = None, "futura"
        if motivo:
            flags.append("reposicao_invalida")
        fornecedor = p.titulo(r["fornecedor"])
        if fornecedor is None:
            flags.append("fornecedor_ausente")
        linhas.append({
            "_id": r["id_produto"], "linha_origem": r["linha_origem"], "id_produto": r["id_produto"],
            "nome_produto": p.titulo(nome) if (nome.islower() or nome.isupper()) else nome,
            "categoria": categorias.get(p.fold(r["categoria"])),
            "estoque_atual": p.parse_inteiro(r["estoque_atual"]),
            "estoque_minimo": p.parse_inteiro(r["estoque_minimo"]), "ultima_reposicao": reposicao,
            "lead_time_dias": p.parse_inteiro(r["lead_time_dias"]), "fornecedor": fornecedor,
            "custo_unitario": p.parse_numero(r["custo_unitario"]),
            "localizacao_deposito": _local(r["localizacao_deposito"]),
            "status": _status(r["status"]), "flags": flags,
        })

    grupos: dict[str, list[dict]] = {}
    for l in linhas:
        grupos.setdefault(chave_produto(l["nome_produto"]), []).append(l)

    clean = []
    for g in grupos.values():
        g.sort(key=lambda l: (_invalido(l), -completude(l, CAMPOS), l["_id"]))
        sob, outros = dict(g[0]), g[1:]
        for o in outros:
            rej.append(rejeitada(o["linha_origem"], "duplicata_nome", sob["id_produto"]))
        if _invalido(sob):
            rej.append(rejeitada(sob["linha_origem"], "estoque_negativo", None))
            continue
        for campo in ("fornecedor", "localizacao_deposito", "ultima_reposicao"):
            if sob[campo] is None:
                for o in outros:
                    if o[campo] is not None:
                        sob[campo] = o[campo]
                        sob["flags"] = [f for f in sob["flags"] if f not in ("fornecedor_ausente", "reposicao_invalida")]
                        break
        clean.append(sob)

    df = pd.DataFrame(clean).drop(columns="_id").sort_values("id_produto").reset_index(drop=True)
    cols_rej = ["linha_origem", "motivo", "id_sobrevivente"] + [c for c in raw.columns if c != "linha_origem"]
    quarantine = pd.DataFrame(rej, columns=cols_rej)
    res = Resultado(df, quarantine, {"linhas_brutas": len(raw), "linhas_limpas": len(df),
                                     "quarentena": len(quarantine)})
    res.conferir_conservacao(len(raw))
    return res
