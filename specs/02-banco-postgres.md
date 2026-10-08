# 02. Banco PostgreSQL

Um container Postgres 16 no `docker-compose.yml`.

## Esquemas

| Esquema | Conteúdo | Quem acessa |
|---|---|---|
| `raw` | CSV carregado como texto, sem alteração, com `linha_origem` | só o pipeline |
| `clean` | tabelas tipadas, normalizadas e deduplicadas | pipeline (escrita), agente (leitura) |
| `quarantine` | linhas rejeitadas com motivo | pipeline, relatório de qualidade |
| `meta` | `ingest_log`, dicionário de dados | pipeline, agente (leitura do dicionário) |

## Tabelas em `clean`

- `dim_vendedor(id_vendedor pk, nome, email, telefone, uf, data_admissao, meta_mensal numeric, comissao_pct numeric, status, supervisor, flags)`
- `dim_comprador(id_comprador pk, razao_social, cnpj unique, cidade, uf, segmento, porte, contato, email, data_cadastro, limite_credito numeric, status)`
- `dim_vendedor_alias` e `dim_comprador_alias(id_descartado pk, id_sobrevivente fk)`
- `fato_venda(id_venda pk, data date, id_vendedor fk, id_comprador fk, produto, categoria, quantidade int, valor_unitario numeric(12,2), desconto numeric(5,4), valor_total numeric(14,2), valor_total_informado numeric(14,2), status, uf, observacoes, flags text[])`
- `estoque(id_produto pk, nome_produto, categoria, estoque_atual, estoque_minimo, ultima_reposicao date, lead_time_dias, fornecedor, custo_unitario numeric(12,2), localizacao_deposito, status)`
- `decisao(id_decisao pk, data date, tipo, descricao, responsavel, impacto, resultado, observacoes, suspeita_injection bool)`

## Views para o agente

O agente de SQL só enxerga views, para esconder a complexidade e reduzir erro:

- `vw_vendas`: venda com nomes de vendedor e comprador, UF, ano, mês, apenas `status = 'concluida'`.
- `vw_vendas_todas`: inclui todos os status, para perguntas sobre cancelamentos.
- `vw_faturamento_mensal_vendedor(ano_mes, id_vendedor, nome, faturamento, qtd_vendas, ticket_medio)`.
- `vw_faturamento_uf_ano(uf, ano, faturamento)`.
- `vw_compradores`, `vw_vendedores`, `vw_estoque`.

Cada view e coluna tem `COMMENT ON` em português. Esses comentários alimentam o prompt do agente de SQL (RF-10).

## Papéis e permissões (RS-01)

- `cristalux_pipeline`: dono dos esquemas, usado só nos notebooks e na carga.
- `cristalux_agent_ro`: `CONNECT`, `USAGE` apenas em `clean` e `meta`, `SELECT` apenas nas views e em `meta.dicionario`. Sem acesso a `raw`, `quarantine` nem às tabelas base. `default_transaction_read_only = on`, `statement_timeout = 5s`, `idle_in_transaction_session_timeout = 10s`.
- Colunas com dado pessoal (`email`, `telefone`, `contato`, `cnpj`) ficam fora das views do agente, exceto onde a pergunta de negócio exigir (decisão registrada em `99`).

## Carga

1. Lê os CSV e grava em `raw.*` com `linha_origem`.
2. Aplica as funções de `cleaning/` e grava `clean.*` e `quarantine.*`.
3. Registra em `meta.ingest_log(arquivo, sha256, linhas_lidas, linhas_ok, linhas_quarentena, executado_em)`.

A carga é idempotente: mesmo arquivo com mesmo hash não é reprocessado, e a escrita em `clean` usa `INSERT ... ON CONFLICT (pk) DO UPDATE` (RF-11, base da spec `07`).

## Critérios de aceite

- RA-10: `docker compose up` sobe o Postgres e um script cria esquemas, papéis e views.
- RA-11: conexão com `cristalux_agent_ro` falha em `INSERT`, `UPDATE`, `DELETE`, `DROP` e em `SELECT` de `raw.*`.
- RA-12: toda view tem comentário.
