"""Limpeza de vendas.csv (spec 01, RN-10 a RN-19)."""
from __future__ import annotations

import pandas as pd

from cristalux.cleaning import parsers as p
from cristalux.cleaning.base import Resultado, completude
from cristalux.config import ANO_FIM, ANO_INICIO

LIMITE_DESCONTO = 0.10  # decisao D018: politica de descontos limitada a 10%

# Categoria que o produto deveria ter. A categoria informada na venda nao e confiavel
# (ver notebook 02), entao a analise de categoria usa categoria_produto.
CATEGORIA_DO_PRODUTO = {
    "Parabrisas Dianteiro": "Vidros", "Vidro Lateral": "Vidros", "Vidro Lateral Direito": "Vidros",
    "Vidro Lateral Esquerdo": "Vidros", "Vidro Traseiro": "Vidros",
    "Moldura de Parabrisas": "Acessórios", "Película Protetora": "Acessórios", "Teto Solar": "Acessórios",
    "Sensor de Chuva": "Sensores", "Kit de Reparo": "Reparos",
}

_COLUNAS_RAW = ["id_venda", "data", "id_vendedor", "id_comprador", "produto", "categoria", "quantidade",
                "valor_unitario", "valor_total", "desconto", "status", "regiao", "observacoes"]
_CAMPOS_COMPLETUDE = ["data", "id_vendedor", "id_comprador", "produto", "categoria", "quantidade",
                      "valor_unitario", "valor_total_informado", "desconto", "status", "uf"]


def _id(texto, alias: dict) -> str | None:
    t = p.limpar(texto)
    if t is None:
        return None
    t = t.upper()
    return alias.get(t, t)


def _interpretar(r: dict, alias_vendedor: dict, alias_comprador: dict) -> dict:
    """Converte uma linha crua em campos tipados e lista os motivos de rejeicao e flags."""
    motivos, flags = [], []
    id_venda = p.limpar(r["id_venda"])
    if id_venda is None:
        motivos.append("id_venda_ausente")

    data, motivo_data, ambigua = p.parse_data(r["data"])
    if motivo_data:
        motivos.append(f"data_{motivo_data}")
    elif not (ANO_INICIO <= data.year <= ANO_FIM):
        motivos.append("data_fora_do_periodo")
    if ambigua:
        flags.append("data_ambigua")

    quantidade = p.parse_inteiro(r["quantidade"])
    if quantidade is None:
        motivos.append("quantidade_invalida")
    elif quantidade < 0:
        motivos.append("quantidade_negativa")
    elif quantidade == 0:
        motivos.append("quantidade_invalida")

    valor_unitario = p.parse_numero(r["valor_unitario"])
    if valor_unitario is None or valor_unitario <= 0:
        motivos.append("valor_unitario_invalido")

    desconto, flag_desc = p.parse_desconto(r["desconto"])
    if flag_desc:
        flags.append(flag_desc)
    elif desconto is not None and desconto > LIMITE_DESCONTO:
        flags.append("desconto_acima_limite")

    status = p.parse_status_venda(r["status"])
    if status is None:
        motivos.append("status_ausente")

    uf = p.parse_uf(r["regiao"])
    if uf is None:
        flags.append("uf_ausente")

    produto = p.parse_produto(r["produto"])
    categoria = p.parse_categoria(r["categoria"])
    categoria_produto = CATEGORIA_DO_PRODUTO.get(produto)
    if categoria and categoria_produto and categoria != categoria_produto:
        flags.append("categoria_incoerente")

    valor_total_informado = p.parse_numero(r["valor_total"])
    valor_total = None
    if quantidade and quantidade > 0 and valor_unitario and valor_unitario > 0:
        valor_total = round(quantidade * valor_unitario * (1 - (desconto or 0.0)), 2)
        if valor_total_informado is None or abs(valor_total - valor_total_informado) > 0.01:
            flags.append("valor_total_divergente")

    return {
        "id_venda": id_venda, "data": data, "id_vendedor": _id(r["id_vendedor"], alias_vendedor),
        "id_comprador": _id(r["id_comprador"], alias_comprador), "produto": produto,
        "produto_original": p.limpar(r["produto"]), "categoria": categoria, "categoria_produto": categoria_produto,
        "quantidade": quantidade, "valor_unitario": valor_unitario, "desconto": desconto,
        "valor_total": valor_total, "valor_total_informado": valor_total_informado, "status": status, "uf": uf,
        "observacoes": p.limpar(r["observacoes"]), "flags": flags, "_motivos": motivos,
        "linha_origem": r["linha_origem"],
    }


def limpar_vendas(raw: pd.DataFrame, vendedores_validos: set[str], compradores_validos: set[str],
                  alias_vendedor: dict | None = None, alias_comprador: dict | None = None) -> Resultado:
    alias_vendedor, alias_comprador = alias_vendedor or {}, alias_comprador or {}
    raw_por_linha = {x["linha_origem"]: x for x in raw.to_dict("records")}

    def rejeitada(linha_origem, motivo, sobrevivente=None):
        original = {c: v for c, v in raw_por_linha[linha_origem].items() if c != "linha_origem"}
        return {"linha_origem": linha_origem, "motivo": motivo, "id_sobrevivente": sobrevivente, **original}

    # RN-11: linha identica em todos os campos (apos tirar espacos) e duplicata exata.
    vistos: dict[tuple, int] = {}
    rej, candidatas = [], []
    for r in raw.to_dict("records"):
        chave = tuple((r[c] or "").strip() for c in _COLUNAS_RAW)
        if chave in vistos:
            rej.append(rejeitada(r["linha_origem"], "duplicata_exata", r["id_venda"]))
            continue
        vistos[chave] = r["linha_origem"]
        candidatas.append(_interpretar(r, alias_vendedor, alias_comprador))

    # RN-19: integridade referencial.
    for c in candidatas:
        if c["id_vendedor"] is None:
            c["_motivos"].append("vendedor_ausente")
        elif c["id_vendedor"] not in vendedores_validos:
            c["_motivos"].append("vendedor_inexistente")
        if c["id_comprador"] is None:
            c["_motivos"].append("comprador_ausente")
        elif c["id_comprador"] not in compradores_validos:
            c["_motivos"].append("comprador_inexistente")

    # RN-11: mesmo id_venda com conteudo diferente. Fica o registro valido, mais completo e mais recente.
    por_id: dict[str, list[dict]] = {}
    sem_id = []
    for c in candidatas:
        (por_id.setdefault(c["id_venda"], []) if c["id_venda"] else sem_id).append(c)

    def prioridade(c):
        return (bool(c["_motivos"]), -completude(c, _CAMPOS_COMPLETUDE),
                -(c["data"].toordinal() if c["data"] else 0), c["linha_origem"])

    sobreviventes = list(sem_id)
    for id_venda, grupo in por_id.items():
        grupo.sort(key=prioridade)
        sobreviventes.append(grupo[0])
        for o in grupo[1:]:
            rej.append(rejeitada(o["linha_origem"], "id_duplicado", id_venda))

    ok = []
    for c in sobreviventes:
        if c["_motivos"]:
            rej.append(rejeitada(c["linha_origem"], ";".join(c["_motivos"])))
        else:
            ok.append({k: v for k, v in c.items() if k != "_motivos"})

    cols = ["id_venda", "data", "id_vendedor", "id_comprador", "produto", "produto_original", "categoria",
            "categoria_produto", "quantidade", "valor_unitario", "desconto", "valor_total",
            "valor_total_informado", "status", "uf", "observacoes", "flags", "linha_origem"]
    clean = pd.DataFrame(ok, columns=cols).sort_values("id_venda").reset_index(drop=True)
    cols_rej = ["linha_origem", "motivo", "id_sobrevivente"] + [c for c in raw.columns if c != "linha_origem"]
    quarantine = pd.DataFrame(rej, columns=cols_rej).sort_values("linha_origem").reset_index(drop=True)
    res = Resultado(clean, quarantine, {"linhas_brutas": len(raw), "linhas_limpas": len(clean),
                                        "quarentena": len(quarantine)})
    res.conferir_conservacao(len(raw))
    return res
