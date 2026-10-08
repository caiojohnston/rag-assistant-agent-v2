"""Relatorio de qualidade (RN-01): tipo de problema, volume afetado e impacto por arquivo.

Os numeros vem do codigo, nunca de texto livre. O relatorio alimenta a tool
`relatorio_qualidade` do agente e a resposta para "os dados estao limpos?".
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from cristalux.cleaning import parsers as p
from cristalux.cleaning.base import Resultado

IMPACTO = {
    "registro_vazio": "Linha sem informação útil; inflaria contagens de registros se mantida.",
    "duplicata_exata": "Linha repetida; duplicaria faturamento e contagem de vendas.",
    "duplicata_cnpj": "Mesmo cliente com dois cadastros; fragmenta o histórico e distorce rankings de compradores.",
    "duplicata_nome": "Mesmo item ou pessoa cadastrado duas vezes; distorce contagens e estoque total.",
    "id_duplicado": "Mesmo id de venda com conteúdos diferentes; só um registro pode ser o verdadeiro.",
    "data_vazia": "Venda sem data não entra em nenhuma série mensal; sai do faturamento por vendedor.",
    "data_inexistente": "Data impossível (ex: 30/02, mês 22); não é possível alocar a venda a um mês.",
    "data_formato_desconhecido": "Data incompleta (ex: 'Jul/2021'); sem dia não há como fechar o mês com certeza.",
    "data_fora_do_periodo": "Venda fora de 2020-2024; contaminaria a análise do período pedido.",
    "quantidade_negativa": "Quantidade negativa sem relação com a coluna de status; faturamento ficaria subestimado.",
    "quantidade_invalida": "Quantidade ausente ou zero; impossível calcular valor.",
    "valor_unitario_invalido": "Preço ausente ou não positivo; impossível calcular valor.",
    "status_ausente": "Sem status não é possível saber se a venda foi concluída.",
    "vendedor_ausente": "Venda sem vendedor não entra no ranking por vendedor.",
    "vendedor_inexistente": "Vendedor sem cadastro; desempenho não pode ser atribuído.",
    "comprador_ausente": "Venda sem comprador não entra em análises por cliente.",
    "comprador_inexistente": "Comprador sem cadastro válido (registro vazio ou inexistente).",
    "id_venda_ausente": "Venda sem identificador; não há como deduplicar.",
    "estoque_negativo": "Estoque negativo é fisicamente impossível; indica erro de lançamento.",
    "data_ambigua": "Data com hífen que pode ser dd-mm ou mm-dd; risco de cair no mês errado.",
    "desconto_indefinido": "Desconto 'Sim' ou vazio sem percentual; margem real incerta.",
    "desconto_acima_limite": "Desconto acima de 10%, o limite da decisão D018.",
    "valor_total_divergente": "valor_total informado difere de quantidade x preço unitário; usa-se o recalculado.",
    "categoria_incoerente": "Categoria da venda diferente da categoria natural do produto; análise por categoria não é confiável.",
    "venda_antes_da_admissao": "Venda anterior à data de admissão do vendedor; o cadastro ou a data da venda está errado.",
    "uf_ausente": "Venda sem região; fica fora de análises regionais.",
    "cnpj_invalido": "CNPJ com dígitos verificadores inválidos; cadastro pode estar errado.",
    "email_ausente": "Sem e-mail de contato.",
    "email_dominio_incomum": "Domínio de e-mail diferente do corporativo; provável erro de digitação.",
    "admissao_invalida": "Data de admissão no futuro ou inválida.",
    "data_cadastro_invalida": "Data de cadastro inválida.",
    "reposicao_invalida": "Data de reposição inválida ou no futuro.",
    "fornecedor_ausente": "Fornecedor desconhecido; atrapalha a reposição.",
    "data_invalida": "Data da decisão inválida.",
    "suspeita_injection": "Texto com instruções dirigidas a assistentes de IA; um LLM ingênuo pode obedecê-lo.",
}

_FORMATOS_DATA = [
    ("aaaa-mm-dd", r"^\d{4}-\d{1,2}-\d{1,2}$"), ("aaaa/mm/dd", r"^\d{4}/\d{1,2}/\d{1,2}$"),
    ("dd/mm/aaaa", r"^\d{1,2}/\d{1,2}/\d{4}$"), ("dd-mm-aaaa", r"^\d{1,2}-\d{1,2}-\d{4}$"),
    ("dd.mm.aaaa", r"^\d{1,2}\.\d{1,2}\.\d{4}$"), ("dd-mm-aa", r"^\d{1,2}-\d{1,2}-\d{2}$"),
    ("dd.mm.aa", r"^\d{1,2}\.\d{1,2}\.\d{2}$"), ("mmm/aaaa", r"^[A-Za-z]{3}/\d{4}$"),
]


def formatos_de_data(serie: pd.Series) -> dict[str, int]:
    """Quantas linhas usam cada formato de data."""
    contagem: dict[str, int] = {}
    for v in serie:
        t = p.limpar(v)
        nome = "vazio" if t is None else next((n for n, rx in _FORMATOS_DATA if re.match(rx, t)), "outro")
        contagem[nome] = contagem.get(nome, 0) + 1
    return contagem


def _variantes(serie: pd.Series, normalizada: pd.Series) -> tuple[int, int]:
    return serie.map(p.limpar).dropna().nunique(), normalizada.dropna().nunique()


def _entrada(tipo: str, volume: int, total: int, detalhe: str = "") -> dict:
    return {"tipo": tipo, "volume": int(volume), "percentual": round(100 * volume / total, 1) if total else 0.0,
            "impacto": IMPACTO.get(tipo, detalhe or "Ver detalhe."), "detalhe": detalhe}


def perfil_arquivo(nome: str, raw: pd.DataFrame, res: Resultado, extras: dict | None = None) -> dict:
    total = len(raw)
    problemas = []
    quarentena = res.quarantine["motivo"].str.split(";").explode().value_counts() if len(res.quarantine) else {}
    for motivo, n in dict(quarentena).items():
        problemas.append(_entrada(motivo, n, total))
    if len(res.clean) and "flags" in res.clean:
        for flag, n in res.clean["flags"].explode().dropna().value_counts().items():
            problemas.append(_entrada(flag, n, len(res.clean), "sobre as linhas que permaneceram na base limpa"))
    if "suspeita_injection" in res.clean and res.clean["suspeita_injection"].any():
        problemas.append(_entrada("suspeita_injection", int(res.clean["suspeita_injection"].sum()), len(res.clean),
                                  "id(s): " + ", ".join(res.clean.loc[res.clean["suspeita_injection"], "id_decisao"])))
    for coluna, serie in (extras or {}).get("variantes", {}).items():
        brutas, normalizadas = serie
        if brutas > normalizadas:
            problemas.append({"tipo": f"grafias_diferentes:{coluna}", "volume": brutas, "percentual": None,
                              "impacto": "O mesmo valor aparece escrito de várias formas; agrupamentos por esse campo "
                                         f"ficariam fragmentados ({brutas} grafias para {normalizadas} valores reais).",
                              "detalhe": f"{brutas} grafias brutas, {normalizadas} normalizadas"})
    perfil = {"arquivo": nome, "linhas_brutas": total, "linhas_limpas": len(res.clean),
              "linhas_quarentena": len(res.quarantine), "problemas": problemas}
    if "formatos_data" in (extras or {}):
        perfil["formatos_data"] = extras["formatos_data"]
    return perfil


def gerar_relatorio(perfis: list[dict]) -> dict:
    return {"arquivos": perfis, "resumo": {
        "total_linhas_brutas": sum(x["linhas_brutas"] for x in perfis),
        "total_linhas_limpas": sum(x["linhas_limpas"] for x in perfis),
        "total_quarentena": sum(x["linhas_quarentena"] for x in perfis),
    }}


def para_markdown(rel: dict) -> str:
    out = ["# Relatório de qualidade dos dados", ""]
    r = rel["resumo"]
    out.append(f"Linhas brutas: {r['total_linhas_brutas']}. Linhas na base limpa: {r['total_linhas_limpas']}. "
               f"Linhas em quarentena: {r['total_quarentena']}.")
    for a in rel["arquivos"]:
        out += ["", f"## {a['arquivo']}", "",
                f"Brutas: {a['linhas_brutas']}. Limpas: {a['linhas_limpas']}. Quarentena: {a['linhas_quarentena']}.", "",
                "| Problema | Volume | % | Impacto |", "|---|---|---|---|"]
        for pr in a["problemas"]:
            pct = "" if pr["percentual"] is None else f"{pr['percentual']}%"
            out.append(f"| {pr['tipo']} | {pr['volume']} | {pct} | {pr['impacto']} |")
    return "\n".join(out) + "\n"


def salvar(rel: dict, pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "qualidade.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta / "qualidade.md").write_text(para_markdown(rel), encoding="utf-8")
