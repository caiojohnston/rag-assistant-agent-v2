"""Dicionário de dados das views expostas ao agente.

Fonte única para COMMENT ON, para meta.dicionario, para o prompt do agente de SQL
e para os chunks de documentação do RAG.
"""
from __future__ import annotations

VIEWS: dict[str, dict] = {
    "vw_vendas": {
        "descricao": "Vendas concluídas (status concluida) de 2020 a 2024. Use para faturamento, ranking e volumes.",
        "colunas": {
            "id_venda": "Identificador da venda", "data": "Data da venda", "ano": "Ano da venda",
            "mes": "Mês da venda (1 a 12)", "ano_mes": "Ano e mês no formato AAAA-MM",
            "id_vendedor": "Id do vendedor", "vendedor": "Nome do vendedor",
            "id_comprador": "Id do comprador", "comprador": "Razão social do comprador",
            "produto": "Produto vendido (nome canônico)",
            "categoria": "Categoria do produto (Vidros, Acessórios, Sensores, Reparos)",
            "quantidade": "Unidades vendidas", "valor_unitario": "Preço unitário em reais",
            "desconto": "Desconto como fração (0.05 = 5 por cento); 0 quando desconhecido",
            "valor_total": "Valor da venda em reais, quantidade x preço unitário, como a origem reporta (faturamento)",
            "valor_liquido": "Valor da venda depois do desconto, quando o desconto é conhecido",
            "status": "Sempre concluida nesta view", "uf": "UF da venda (sigla de 2 letras)",
        },
    },
    "vw_vendas_todas": {
        "descricao": "Todas as vendas válidas, em qualquer status (concluida, cancelada, devolvida, pendente). "
                     "Use para perguntas sobre cancelamentos, devoluções e pendências.",
        "colunas": {},  # mesmas colunas de vw_vendas
    },
    "vw_faturamento_mensal_vendedor": {
        "descricao": "Faturamento mensal por vendedor, só vendas concluídas.",
        "colunas": {
            "ano_mes": "Mês no formato AAAA-MM", "id_vendedor": "Id do vendedor", "vendedor": "Nome do vendedor",
            "faturamento": "Soma de valor_total no mês", "faturamento_liquido": "Soma de valor_liquido no mês (após desconto)",
            "qtd_vendas": "Quantidade de vendas no mês",
            "ticket_medio": "Faturamento dividido por qtd_vendas",
        },
    },
    "vw_faturamento_uf_ano": {
        "descricao": "Faturamento anual por UF, só vendas concluídas.",
        "colunas": {"uf": "UF (sigla)", "ano": "Ano", "faturamento": "Soma de valor_total",
                    "qtd_vendas": "Quantidade de vendas"},
    },
    "vw_compradores": {
        "descricao": "Compradores (clientes) sem duplicatas. Não inclui dados de contato.",
        "colunas": {
            "id_comprador": "Id do comprador", "razao_social": "Razão social", "cidade": "Cidade", "uf": "UF",
            "segmento": "Segmento (Oficinas, Vidraçarias, Distribuidoras, Revendas, Reparos)",
            "porte": "Porte (Micro, Pequeno, Médio, Grande)", "limite_credito": "Limite de crédito em reais",
            "status": "ativo ou inativo", "data_cadastro": "Data de cadastro",
        },
    },
    "vw_vendedores": {
        "descricao": "Vendedores sem duplicatas. Não inclui e-mail nem telefone.",
        "colunas": {
            "id_vendedor": "Id do vendedor", "nome": "Nome", "uf": "UF de atuação", "data_admissao": "Data de admissão",
            "meta_mensal": "Meta mensal em reais", "comissao_pct": "Comissão em percentual (3.5 = 3,5 por cento)",
            "status": "ativo ou inativo", "supervisor": "Nome do supervisor",
        },
    },
    "vw_estoque": {
        "descricao": "Estoque e logística por produto, sem duplicatas e sem estoque negativo.",
        "colunas": {
            "id_produto": "Id do produto", "nome_produto": "Nome", "categoria": "Categoria",
            "estoque_atual": "Unidades em estoque", "estoque_minimo": "Estoque mínimo desejado",
            "abaixo_do_minimo": "Verdadeiro se estoque_atual é menor que estoque_minimo",
            "ultima_reposicao": "Data da última reposição", "lead_time_dias": "Prazo de reposição em dias",
            "fornecedor": "Fornecedor", "custo_unitario": "Custo unitário em reais",
            "localizacao_deposito": "Depósito e posição", "status": "Situação do item",
        },
    },
}
VIEWS["vw_vendas_todas"]["colunas"] = {**VIEWS["vw_vendas"]["colunas"],
                                       "status": "concluida, cancelada, devolvida ou pendente"}

AMOSTRAS_PERGUNTA_SQL = [
    ("Quais os 5 vendedores que mais venderam em unidades?",
     "SELECT vendedor, SUM(quantidade) AS unidades FROM vw_vendas GROUP BY vendedor ORDER BY unidades DESC LIMIT 5"),
    ("Quais UFs tiveram queda de faturamento de 2021 para 2022? (UF sem venda no segundo ano conta como faturamento zero)",
     "SELECT b.uf, b.faturamento AS fat_2021, COALESCE(a.faturamento, 0) AS fat_2022 FROM vw_faturamento_uf_ano b "
     "LEFT JOIN vw_faturamento_uf_ano a ON a.uf = b.uf AND a.ano = 2022 "
     "WHERE b.ano = 2021 AND COALESCE(a.faturamento, 0) < b.faturamento ORDER BY b.uf"),
    ("Quantas devoluções houve por UF?",
     "SELECT uf, COUNT(*) AS devolucoes FROM vw_vendas_todas WHERE status = 'devolvida' GROUP BY uf ORDER BY devolucoes DESC"),
]


def descricao_texto() -> str:
    """Dicionário em texto corrido, para o prompt do agente de SQL."""
    linhas = []
    for view, info in VIEWS.items():
        linhas.append(f"{view}: {info['descricao']}")
        for col, desc in info["colunas"].items():
            linhas.append(f"  - {col}: {desc}")
    return "\n".join(linhas)
