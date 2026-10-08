# 00. Visão geral

## Objetivo

Permitir que um analista de negócio faça perguntas em português sobre a base interna da Cristalux (vendas, compradores, vendedores, estoque e decisões) e receba respostas verificáveis, com a fonte de cada afirmação visível.

## Entregáveis do teste

1. Pipeline RAG sobre os textos da base.
2. Consulta em linguagem natural sobre os dados tabulares, via tool de SQL sobre PostgreSQL.
3. Limpeza e relatório de qualidade dos 5 arquivos, em notebooks.
4. Avaliação com métricas e casos de falha.
5. README em português com decisões, limitações e respostas às perguntas do enunciado.
6. Bônus: agente com tools (coberto pelo agente orquestrador).

## Escopo

Dentro:
- Os 5 CSVs em `dados_raw/` (os mesmos que o enunciado chama de xlsx/PDF).
- Período de vendas analisado: 2020 a 2024.
- Uso local com Docker Compose.

Fora:
- Autenticação de usuários, multi-tenant, deploy em nuvem.
- Fine-tuning de modelos.

## Premissas e decisões já tomadas

| Tema | Decisão |
|---|---|
| Linguagem | Python 3.11 |
| LLM | Gemini, free tier: `gemini-3.1-flash-lite`, configurável por `GEMINI_MODEL`. O `gemini-3.5-flash` tem cota gratuita de 20 requisições por dia, inviável para desenvolvimento e avaliação; o `gemini-2.5-flash` não está mais disponível para contas novas |
| Banco tabular | PostgreSQL em Docker |
| Banco vetorial | ChromaDB, persistente em disco |
| Avaliação | RAGAS para o RAG, comparação de resultado contra gabarito para o SQL |
| Tracing | Langfuse |
| Interface | Streamlit, sem enfeites |
| Limpeza | Notebooks `.ipynb`, com a lógica reutilizável em módulos Python |
| Linha D013 | Mantida no corpus de propósito, para demonstrar a defesa contra prompt injection |
| Containers | Tudo containerizado com Docker (Postgres, app Streamlit, job de carga). Destino de deploy: Railway, com um serviço por container |
| Idioma | Código em inglês onde convencional, documentação e interface em português |
| Estilo | Sem emojis, texto simples, sem linguagem de marketing |

Confirmado: "DStack" era Docker. Deploy posterior no Railway.

## Arquitetura

```
CSV bruto -> notebooks de limpeza -> PostgreSQL (raw, clean, quarantine)
                                          |
                                          v
Pergunta -> Streamlit -> Agente (Gemini, function calling)
                           |-- tool consultar_dados   -> agente de SQL -> validador -> Postgres (papel somente leitura)
                           |-- tool buscar_documentos -> ChromaDB (decisões, dicionário, relatório de qualidade)
                           |-- tool relatorio_qualidade -> métricas calculadas em código
                           |-- tool data_atual
                           v
                  Resposta com fontes + trace no Langfuse
```

Princípio central: números vêm sempre do banco ou de código determinístico, nunca do texto livre de um documento.

## Estrutura do repositório

```
cristalux/
  dados_raw/              CSVs originais, fora do git (apenas anonimizados, ver 99)
  specs/
  notebooks/              01_eda ... 05_analise
  src/cristalux/
    config.py
    cleaning/             funções de limpeza (datas, moeda, status, região, dedup)
    db/                   conexão, carga, DDL
    rag/                  chunking, indexação, retrieval
    agent/                orquestrador, agente de SQL, tools, guardrails
    eval/                 datasets e execução das avaliações
  app/streamlit_app.py
  sql/                    DDL, views, papéis
  tests/
  docker-compose.yml
  pyproject.toml
  .env.example
  README.md
```

## Requisitos transversais

- RF-00: tudo roda com `docker compose up` mais um comando de setup documentado.
- RF-04: o app lê toda configuração de variáveis de ambiente, inclusive `DATABASE_URL` e `PORT`, para rodar no Railway sem alteração de código. A imagem do app é uma só (`Dockerfile`); o job de carga e o app usam a mesma imagem com comandos diferentes. O Chroma persiste em volume (`/data/chroma`).
- RF-01: nenhum segredo no repositório, apenas `.env.example`.
- RF-02: o dado bruto só recebeu a anonimização do nome da empresa (ver `99`). Toda outra edição vive em código e é registrada.
- RF-03: toda resposta mostra de onde veio (SQL executado ou trechos recuperados).
