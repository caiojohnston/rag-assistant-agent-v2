-- Views que o agente enxerga. Recriadas a cada setup.
DROP VIEW IF EXISTS clean.vw_faturamento_uf_ano, clean.vw_faturamento_mensal_vendedor,
    clean.vw_vendas, clean.vw_vendas_todas, clean.vw_compradores, clean.vw_vendedores, clean.vw_estoque CASCADE;

CREATE VIEW clean.vw_vendas_todas AS
SELECT v.id_venda, v.data,
       EXTRACT(YEAR FROM v.data)::int  AS ano,
       EXTRACT(MONTH FROM v.data)::int AS mes,
       to_char(v.data, 'YYYY-MM')      AS ano_mes,
       v.id_vendedor, vd.nome AS vendedor,
       v.id_comprador, c.razao_social AS comprador,
       v.produto, v.categoria_produto AS categoria, v.quantidade, v.valor_unitario,
       COALESCE(v.desconto, 0) AS desconto, v.valor_total, v.valor_liquido, v.status, v.uf
FROM clean.fato_venda v
JOIN clean.dim_vendedor vd ON vd.id_vendedor = v.id_vendedor
JOIN clean.dim_comprador c ON c.id_comprador = v.id_comprador;

CREATE VIEW clean.vw_vendas AS
SELECT * FROM clean.vw_vendas_todas WHERE status = 'concluida';

CREATE VIEW clean.vw_faturamento_mensal_vendedor AS
SELECT ano_mes, id_vendedor, vendedor,
       SUM(valor_total)::numeric(14,2)          AS faturamento,
       SUM(valor_liquido)::numeric(14,2)        AS faturamento_liquido,
       COUNT(*)                                 AS qtd_vendas,
       (SUM(valor_total) / COUNT(*))::numeric(14,2) AS ticket_medio
FROM clean.vw_vendas
GROUP BY ano_mes, id_vendedor, vendedor;

CREATE VIEW clean.vw_faturamento_uf_ano AS
SELECT uf, ano, SUM(valor_total)::numeric(14,2) AS faturamento, COUNT(*) AS qtd_vendas
FROM clean.vw_vendas
WHERE uf IS NOT NULL
GROUP BY uf, ano;

CREATE VIEW clean.vw_compradores AS
SELECT id_comprador, razao_social, cidade, uf, segmento, porte, limite_credito, status, data_cadastro
FROM clean.dim_comprador;

CREATE VIEW clean.vw_vendedores AS
SELECT id_vendedor, nome, uf, data_admissao, meta_mensal, comissao_pct, status, supervisor
FROM clean.dim_vendedor;

CREATE VIEW clean.vw_estoque AS
SELECT id_produto, nome_produto, categoria, estoque_atual, estoque_minimo,
       (estoque_atual < estoque_minimo) AS abaixo_do_minimo,
       ultima_reposicao, lead_time_dias, fornecedor, custo_unitario, localizacao_deposito, status
FROM clean.estoque;
