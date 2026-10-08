"""Limpeza de compradores.csv e vendedores.csv (inclui deduplicacao)."""
from __future__ import annotations

from datetime import date

import pandas as pd

from cristalux.cleaning import parsers as p
from cristalux.cleaning.base import Resultado, canonico_por_fold, completude

DOMINIO_EMPRESA = "cristalux.com.br"

CAMPOS_COMPRADOR = ["razao_social", "cnpj", "cidade", "uf", "segmento", "porte", "contato", "email",
                    "data_cadastro", "limite_credito", "status"]
CAMPOS_VENDEDOR = ["nome", "email", "telefone", "uf", "data_admissao", "meta_mensal", "comissao_pct",
                   "status", "supervisor"]


def _data_ate_hoje(texto):
    """Data valida e nao futura; devolve (data, motivo)."""
    d, motivo, _ = p.parse_data(texto)
    if d and d > date.today():
        return None, "futura"
    return d, motivo


def _escolher_sobrevivente(grupo: list[dict], campos: list[str]) -> dict:
    """RN-22: mais campos preenchidos; no empate, menor id (mais antigo)."""
    return sorted(grupo, key=lambda r: (-completude(r, campos), r["_id"]))[0]


def _fundir(sobrevivente: dict, outros: list[dict], campos: list[str]) -> dict:
    """Preenche campos nulos do sobrevivente com os dos descartados."""
    for campo in campos:
        if sobrevivente.get(campo) in (None, ""):
            for o in outros:
                if o.get(campo) not in (None, ""):
                    sobrevivente[campo] = o[campo]
                    break
    return sobrevivente


def _linha_rejeitada(raw_por_linha: dict, linha_origem: int, motivo: str, sobrevivente) -> dict:
    original = {c: v for c, v in raw_por_linha[linha_origem].items() if c != "linha_origem"}
    return {"linha_origem": linha_origem, "motivo": motivo, "id_sobrevivente": sobrevivente, **original}


def _montar(raw: pd.DataFrame, clean: list[dict], rej: list[dict], chave_id: str, alias: dict) -> Resultado:
    df = pd.DataFrame(clean).drop(columns="_id").sort_values(chave_id).reset_index(drop=True)
    cols_rej = ["linha_origem", "motivo", "id_sobrevivente"] + [c for c in raw.columns if c != "linha_origem"]
    quarantine = pd.DataFrame(rej, columns=cols_rej)
    res = Resultado(df, quarantine, {"linhas_brutas": len(raw), "linhas_limpas": len(df),
                                     "quarentena": len(quarantine), "alias": alias})
    res.conferir_conservacao(len(raw))
    return res


# ------------------------------------------------------------------ compradores

def limpar_compradores(raw: pd.DataFrame) -> Resultado:
    segmentos = canonico_por_fold(raw["segmento"].map(p.limpar))
    portes = canonico_por_fold(raw["porte"].map(p.limpar))
    cidades = canonico_por_fold(raw["cidade"].map(p.limpar))
    raw_por_linha = {x["linha_origem"]: x for x in raw.to_dict("records")}

    linhas, rej = [], []
    for r in raw.to_dict("records"):
        razao = p.limpar(r["razao_social"])
        cnpj = p.so_digitos(r["cnpj"])
        if razao is None and (cnpj is None or set(cnpj) == {"0"}):
            rej.append(_linha_rejeitada(raw_por_linha, r["linha_origem"], "registro_vazio", None))
            continue
        data, motivo_data = _data_ate_hoje(r["data_cadastro"])
        flags = []
        if not p.cnpj_valido(cnpj):
            flags.append("cnpj_invalido")
        if motivo_data:
            flags.append("data_cadastro_invalida")
        email = p.parse_email(r["email"])
        if email is None:
            flags.append("email_ausente")
        cidade = p.limpar(r["cidade"])
        segmento, porte = p.limpar(r["segmento"]), p.limpar(r["porte"])
        linhas.append({
            "_id": r["id_comprador"], "linha_origem": r["linha_origem"],
            "id_comprador": r["id_comprador"], "razao_social": razao, "cnpj": cnpj,
            "cidade": cidades.get(p.fold(cidade), p.titulo(cidade)) if cidade else None,
            "uf": p.parse_uf(r["estado"]),
            "segmento": segmentos.get(p.fold(segmento)) if segmento else None,
            "porte": portes.get(p.fold(porte)) if porte else None,
            "contato": p.limpar(r["contato"]), "email": email, "data_cadastro": data,
            "limite_credito": p.parse_numero(r["limite_credito"]),
            "status": p.parse_status_cadastro(r["status"]), "flags": flags,
        })

    # RN-20: a chave de duplicidade e o CNPJ normalizado.
    grupos: dict[str, list[dict]] = {}
    for l in linhas:
        grupos.setdefault(l["cnpj"] or f"sem-cnpj-{l['_id']}", []).append(l)

    clean, alias = [], {}
    for grupo in grupos.values():
        sob = _escolher_sobrevivente(grupo, CAMPOS_COMPRADOR)
        outros = [g for g in grupo if g is not sob]
        sob = _fundir(dict(sob), outros, CAMPOS_COMPRADOR)
        for o in outros:
            alias[o["id_comprador"]] = sob["id_comprador"]
            rej.append(_linha_rejeitada(raw_por_linha, o["linha_origem"], "duplicata_cnpj", sob["id_comprador"]))
        clean.append(sob)
    return _montar(raw, clean, rej, "id_comprador", alias)


# ------------------------------------------------------------------ vendedores

def limpar_vendedores(raw: pd.DataFrame) -> Resultado:
    raw_por_linha = {x["linha_origem"]: x for x in raw.to_dict("records")}
    linhas, rej = [], []
    for r in raw.to_dict("records"):
        nome = p.limpar(r["nome"])
        if nome is None:
            rej.append(_linha_rejeitada(raw_por_linha, r["linha_origem"], "registro_vazio", None))
            continue
        flags = []
        email = p.parse_email(r["email"])
        if email is None:
            flags.append("email_ausente")
        elif not email.endswith("@" + DOMINIO_EMPRESA):
            flags.append("email_dominio_incomum")
        admissao, motivo = _data_ate_hoje(r["data_admissao"])
        if motivo:
            flags.append("admissao_invalida")
        linhas.append({
            "_id": r["id_vendedor"], "linha_origem": r["linha_origem"], "id_vendedor": r["id_vendedor"],
            "nome": nome, "email": email, "telefone": p.parse_telefone(r["telefone"]),
            "uf": p.parse_uf(r["regiao"]), "data_admissao": admissao,
            "meta_mensal": p.parse_numero(r["meta_mensal"]), "comissao_pct": p.parse_numero(r["comissao_pct"]),
            "status": p.parse_status_cadastro(r["status"]), "supervisor": p.limpar(r["supervisor"]),
            "flags": flags,
        })

    # RN-21: mesmo nome normalizado com e-mail ou telefone igual.
    grupos: list[list[dict]] = []
    for l in linhas:
        for g in grupos:
            ref = g[0]
            mesmo_nome = p.fold(ref["nome"]) == p.fold(l["nome"])
            mesmo_contato = (ref["email"] and ref["email"] == l["email"]) or (
                ref["telefone"] and ref["telefone"] == l["telefone"])
            if mesmo_nome and mesmo_contato:
                g.append(l)
                break
        else:
            grupos.append([l])

    clean, alias = [], {}
    for g in grupos:
        sob = _escolher_sobrevivente(g, CAMPOS_VENDEDOR)
        outros = [x for x in g if x is not sob]
        sob = _fundir(dict(sob), outros, CAMPOS_VENDEDOR)
        for o in outros:
            mesmo_id = o["id_vendedor"] == sob["id_vendedor"]
            if not mesmo_id:
                alias[o["id_vendedor"]] = sob["id_vendedor"]
            rej.append(_linha_rejeitada(raw_por_linha, o["linha_origem"],
                                        "duplicata_exata" if mesmo_id else "duplicata_nome", sob["id_vendedor"]))
        clean.append(sob)
    return _montar(raw, clean, rej, "id_vendedor", alias)
