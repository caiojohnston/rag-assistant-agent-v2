"""Dicionario de dados das views expostas ao agente.

Fonte unica para COMMENT ON, para meta.dicionario, para o prompt do agente de SQL
e para os chunks de documentacao do RAG.
"""
from __future__ import annotations

VIEWS: dict[str, dict] = {
    "vw_vendas": {
        "descricao": "Vendas concluidas (status concluida) de 2020 a 2024. Use para faturamento, ranking e volumes.",
        "colunas": {
            "id_venda": "Identificador da venda", "data": "Data da venda", "ano": "Ano da venda",
            "mes": "Mes da venda (1 a 12)", "ano_mes": "Ano e mes no formato AAAA-MM",
            "id_vendedor": "Id do vendedor", "vendedor": "Nome do vendedor",
            "id_comprador": "Id do comprador", "comprador": "Razao social do comprador",
            "produto": "Produto vendido (nome canonico)",
            "categoria": "Categoria do produto (Vidros, Acessorios, Sensores, Reparos)",
            "quantidade": "Unidades vendidas", "valor_unitario": "Preco unitario em reais",
            "desconto": "Desconto como fracao (0.05 = 5 por cento); 0 quando desconhecido",
            "valor_total": "Valor liquido da venda em reais (quantidade x preco x (1 - desconto))",
            "status": "Sempre concluida nesta view", "uf": "UF da venda (sigla de 2 letras)",
        },
    },
    "vw_vendas_todas": {
        "descricao": "Todas as vendas validas, em qualquer status (concluida, cancelada, devolvida, pendente). "
                     "Use para perguntas sobre cancelamentos, devolucoes e pendencias.",
        "colunas": {},  # mesmas colunas de vw_vendas
    },
    "vw_faturamento_mensal_vendedor": {
        "descricao": "Faturamento mensal por vendedor, so vendas concluidas.",
        "colunas": {
            "ano_mes": "Mes no formato AAAA-MM", "id_vendedor": "Id do vendedor", "vendedor": "Nome do vendedor",
            "faturamento": "Soma de valor_total no mes", "qtd_vendas": "Quantidade de vendas no mes",
            "ticket_medio": "Faturamento dividido por qtd_vendas",
        },
    },
    "vw_faturamento_uf_ano": {
        "descricao": "Faturamento anual por UF, so vendas concluidas.",
        "colunas": {"uf": "UF (sigla)", "ano": "Ano", "faturamento": "Soma de valor_total",
                    "qtd_vendas": "Quantidade de vendas"},
    },
    "vw_compradores": {
        "descricao": "Compradores (clientes) sem duplicatas. Nao inclui dados de contato.",
        "colunas": {
            "id_comprador": "Id do comprador", "razao_social": "Razao social", "cidade": "Cidade", "uf": "UF",
            "segmento": "Segmento (Oficinas, Vidracarias, Distribuidoras, Revendas, Reparos)",
            "porte": "Porte (Micro, Pequeno, Medio, Grande)", "limite_credito": "Limite de credito em reais",
            "status": "ativo ou inativo", "data_cadastro": "Data de cadastro",
        },
    },
    "vw_vendedores": {
        "descricao": "Vendedores sem duplicatas. Nao inclui e-mail nem telefone.",
        "colunas": {
            "id_vendedor": "Id do vendedor", "nome": "Nome", "uf": "UF de atuacao", "data_admissao": "Data de admissao",
            "meta_mensal": "Meta mensal em reais", "comissao_pct": "Comissao em percentual (3.5 = 3,5 por cento)",
            "status": "ativo ou inativo", "supervisor": "Nome do supervisor",
        },
    },
    "vw_estoque": {
        "descricao": "Estoque e logistica por produto, sem duplicatas e sem estoque negativo.",
        "colunas": {
            "id_produto": "Id do produto", "nome_produto": "Nome", "categoria": "Categoria",
            "estoque_atual": "Unidades em estoque", "estoque_minimo": "Estoque minimo desejado",
            "abaixo_do_minimo": "Verdadeiro se estoque_atual e menor que estoque_minimo",
            "ultima_reposicao": "Data da ultima reposicao", "lead_time_dias": "Prazo de reposicao em dias",
            "fornecedor": "Fornecedor", "custo_unitario": "Custo unitario em reais",
            "localizacao_deposito": "Deposito e posicao", "status": "Situacao do item",
        },
    },
}
VIEWS["vw_vendas_todas"]["colunas"] = {**VIEWS["vw_vendas"]["colunas"],
                                       "status": "concluida, cancelada, devolvida ou pendente"}

AMOSTRAS_PERGUNTA_SQL = [
    ("Quais os 3 maiores compradores por faturamento?",
     "SELECT comprador, SUM(valor_total) AS faturamento FROM vw_vendas GROUP BY comprador ORDER BY faturamento DESC LIMIT 3"),
    ("Quais UFs tiveram queda de faturamento em 2023 em relacao a 2022?",
     "SELECT a.uf, b.faturamento AS fat_2022, a.faturamento AS fat_2023 FROM vw_faturamento_uf_ano a "
     "JOIN vw_faturamento_uf_ano b ON a.uf = b.uf AND b.ano = 2022 WHERE a.ano = 2023 AND a.faturamento < b.faturamento"),
    ("Quantas vendas foram canceladas por ano?",
     "SELECT ano, COUNT(*) AS cancelamentos FROM vw_vendas_todas WHERE status = 'cancelada' GROUP BY ano ORDER BY ano"),
]


def descricao_texto() -> str:
    """Dicionario em texto corrido, para o prompt do agente de SQL."""
    linhas = []
    for view, info in VIEWS.items():
        linhas.append(f"{view}: {info['descricao']}")
        for col, desc in info["colunas"].items():
            linhas.append(f"  - {col}: {desc}")
    return "\n".join(linhas)
