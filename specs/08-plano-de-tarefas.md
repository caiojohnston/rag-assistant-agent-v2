# 08. Plano de tarefas

Cada tarefa lista dependência, requisitos cobertos e o que precisa estar verdadeiro para ser dada como pronta. Commits pequenos, um por tarefa.

| ID | Tarefa | Depende | Cobre | Pronto quando |
|---|---|---|---|---|
| T01 | Esqueleto: `pyproject.toml`, `.env.example`, `docker-compose.yml` (Postgres), `.gitignore`, `git init` | none | RF-00, RF-01 | `docker compose up` sobe o Postgres; `pip install -e .` funciona |
| T02 | Funções de parse e normalização (data, moeda, desconto, status, UF, telefone, texto) com testes | T01 | RN-10 a RN-18, RA-05 | testes passam com os casos reais dos CSV |
| T03 | Notebook `01_eda_qualidade` e gerador de `reports/qualidade.*` | T02 | RN-01 | relatório com tipo, volume e impacto por arquivo |
| T04 | Notebook `02_limpeza_vendas` (quarentena, deduplicação, status, faturamento mensal por vendedor) | T02 | RN-10 a RN-19, RA-01 a RA-04 | conservação de linhas confere |
| T05 | Notebook `03_dedup_compradores_vendedores` com mapa de alias | T02 | RN-20 a RN-26 | duplicatas resolvidas e critério documentado |
| T06 | Notebook `04_limpeza_estoque_decisoes` | T02 | RN-30, RN-31 | D013 marcada, vazias em quarentena |
| T07 | DDL, esquemas, papéis, views com comentários e carga idempotente | T04, T05, T06 | spec 02, RA-10 a RA-12 | testes de permissão passam; carga repetida não muda contagens |
| T08 | Notebook `05_analise_melhor_vendedor` e métrica justificada | T07 | pergunta 4 | resultado reproduzível por query |
| T09 | Indexação RAG: documentos, chunking, embeddings, Chroma, detector de injection | T07 | spec 03, RA-20 a RA-22, RS-02 | índice idempotente |
| T10 | Validador de SQL com `sqlglot` e testes de bloqueio | T07 | RS-03, RA-41 | todos os casos de ataque bloqueados |
| T11 | Agente de SQL (`consultar_dados`) | T10 | RF-31, RA-40 | perguntas de exemplo devolvem SQL e resultado |
| T12 | Tools restantes e agente orquestrador | T09, T11 | RF-30 a RF-36 | pergunta mista usa as tools certas |
| T13 | Instrumentação Langfuse | T12 | RF-40 | trace aninhado completo por pergunta |
| T14 | Interface Streamlit com expansor de raciocínio | T13 | RF-41, RA-50 a RA-52 | demonstração ponta a ponta |
| T15 | Conjuntos de avaliação A, B e C e executor | T12 | spec 06 | relatório gerado, falhas incluídas |
| T16 | Experimentos de decisão (embedding, threshold, chunking, few-shot) | T15 | RA-63 | números no relatório |
| T17 | Teste da atualização incremental (lote de exemplo) | T09, T07 | RF-50, RA-70 a RA-72 | os três testes passam |
| T18 | README em português com decisões, evals, limitações e respostas às perguntas | todas | enunciado | revisão contra `09` sem itens abertos |
| T19 | Roteiro da apresentação de 20 minutos | T18 | apresentação | roteiro com demo e plano B sem rede |

Ordem sugerida: T01 a T08 (dados), T09 a T14 (sistema), T15 a T17 (qualidade), T18 e T19 (entrega).

## Riscos do plano

- Limite do free tier do Gemini pode atrasar a avaliação. Mitigação: cache de respostas, pausa entre chamadas, execução em lotes.
- Docker precisa estar em execução (hoje o daemon do Docker Desktop está parado nesta máquina).
- RAGAS com Gemini pode exigir ajuste de wrappers. Mitigação: reservar tempo em T15 e manter as métricas próprias sem LLM como base.
