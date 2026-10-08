"""Conjunto B: perguntas sobre os dados tabulares com gabarito calculado em pandas.

O gabarito NAO passa pelo Postgres nem pelas views: parte dos CSV limpos em memoria e calcula com pandas.
Assim o teste compara dois caminhos independentes (pandas contra SQL gerado pelo LLM).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from cristalux.config import settings
from cristalux.pipeline.run import limpar_tudo


@dataclass
class Caso:
    id: str
    pergunta: str
    tipo: str
    gabarito: Callable[[dict], dict]  # recebe os DataFrames limpos
    observacao: str = ""


def _base(res: dict) -> dict:
    v = res["vendas"].clean.copy()
    v["ano"] = v["data"].map(lambda d: d.year)
    v["ano_mes"] = v["data"].map(lambda d: d.strftime("%Y-%m"))
    nomes_v = res["vendedores"].clean.set_index("id_vendedor")["nome"]
    nomes_c = res["compradores"].clean.set_index("id_comprador")["razao_social"]
    v["vendedor"] = v["id_vendedor"].map(nomes_v)
    v["comprador"] = v["id_comprador"].map(nomes_c)
    return {"todas": v, "c": v[v["status"] == "concluida"], "estoque": res["estoque_logistica"].clean,
            "vendedores": res["vendedores"].clean}


def _linhas(df: pd.DataFrame) -> list[list]:
    return [[(round(x, 2) if isinstance(x, float) else x) for x in r] for r in df.itertuples(index=False)]


def _escalar(valor) -> dict:
    return {"tipo": "escalar", "linhas": [[round(float(valor), 2)]]}


def _tabela(df: pd.DataFrame, ordenada: bool = False) -> dict:
    return {"tipo": "tabela", "ordenada": ordenada, "linhas": _linhas(df)}


def g01(b):
    return _escalar(b["c"][b["c"]["ano"] == 2022]["valor_total"].sum())


def _topn(serie: pd.Series, n: int) -> dict:
    """Top N ordenado. Se houver empate no valor do ultimo lugar, qualquer entidade empatada e aceita nessa posicao."""
    ordenada = serie.sort_values(ascending=False)
    corte = ordenada.iloc[n - 1]
    empatadas = ordenada[ordenada == corte]
    linhas = []
    for nome, valor in ordenada.head(n).items():
        if valor == corte and len(empatadas) > 1:
            linhas.append({"ou": [[k, round(float(v), 2)] for k, v in empatadas.items()]})
        else:
            linhas.append([nome, round(float(valor), 2)])
    return {"tipo": "tabela", "ordenada": True, "linhas": linhas}


def g02(b):
    return _topn(b["c"].groupby("comprador")["valor_total"].sum(), 3)


def g03(b):
    return _topn(b["c"].groupby("comprador")["quantidade"].sum(), 3)


def g04(b):
    t = b["c"].groupby(["uf", "ano"])["valor_total"].sum().unstack(fill_value=0)
    queda = t[(t.get(2022, 0) > 0) & (t.get(2023, 0) < t.get(2022, 0))]
    return {"tipo": "conjunto", "linhas": [[uf] for uf in queda.index]}


def g05(b):
    t = b["todas"][b["todas"]["status"] == "cancelada"].groupby("ano").size().reset_index()
    return _tabela(t)


def g06(b):
    return _topn(b["c"].groupby("vendedor")["valor_total"].sum(), 1)


def g07(b):
    t = b["c"].groupby("categoria_produto")["valor_total"].sum().reset_index()
    return _tabela(t)


def g08(b):
    return _escalar(((b["c"]["ano"] == 2021)).sum())


def g09(b):
    e = b["estoque"]
    return {"tipo": "conjunto", "linhas": [[n] for n in e[e["estoque_atual"] < e["estoque_minimo"]]["nome_produto"]]}


def g10(b):
    # Confere os valores mensais; o rotulo do mes ("2022-02" ou "fevereiro") fica livre.
    t = b["c"][b["c"]["ano"] == 2022].groupby("ano_mes")["valor_total"].sum().reset_index()[["valor_total"]]
    return _tabela(t)


def g11(b):
    return {"tipo": "vazio"}


def g12(b):
    return _topn(b["c"].groupby("uf")["valor_total"].sum(), 1)


def g13(b):
    return _escalar((b["vendedores"]["status"] == "ativo").sum())


def g14(b):
    return _escalar(b["c"]["valor_total"].mean())


CASOS = [
    Caso("B01", "Qual foi o faturamento total de 2022?", "agregacao", g01),
    Caso("B02", "Quem são os 3 maiores compradores por faturamento?", "top_n", g02),
    Caso("B03", "Quem são os top 3 compradores por volume de unidades?", "top_n", g03),
    Caso("B04", "Quais regiões tiveram queda de vendas em 2023 em relação a 2022?", "queda_ano_a_ano", g04,
         "UF com venda em 2022 e nenhuma em 2023 conta como queda (faturamento zero)."),
    Caso("B05", "Quantas vendas foram canceladas em cada ano?", "filtro_status", g05),
    Caso("B06", "Qual vendedor teve o maior faturamento entre 2020 e 2024?", "top_n", g06),
    Caso("B07", "Qual o faturamento por categoria de produto?", "agregacao", g07),
    Caso("B08", "Quantas vendas concluídas houve em 2021?", "contagem", g08),
    Caso("B09", "Quais produtos estão abaixo do estoque mínimo?", "estoque", g09),
    Caso("B10", "Qual foi o faturamento de cada mês de 2022?", "serie_mensal", g10),
    Caso("B11", "Qual foi o faturamento de 2019?", "sem_dado", g11, "Fora do período da base: sem linhas ou zero."),
    Caso("B12", "Qual UF teve o maior faturamento no total?", "top_n", g12),
    Caso("B13", "Quantos vendedores estão ativos?", "contagem", g13),
    Caso("B14", "Qual o ticket médio das vendas concluídas?", "agregacao", g14),
]


def carregar_base() -> dict:
    _, res = limpar_tudo(Path(settings.data_dir))
    return _base(res)
