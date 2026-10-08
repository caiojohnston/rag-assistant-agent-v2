# 04. Agente e tools

## Agente orquestrador (RF-30)

Gemini com function calling. Recebe a pergunta, decide quais tools chamar (zero, uma ou várias), compõe a resposta final em português com as fontes. Limite de 6 chamadas de tool por pergunta. Temperatura 0.

Sem framework de agentes. O laço de function calling é escrito diretamente com o SDK `google-genai`: é curto, fácil de explicar na apresentação e de instrumentar no Langfuse. LangChain, LlamaIndex e ferramentas prontas de text-to-SQL (Vanna, Wren, agente SQL do LangChain) foram consideradas e descartadas por esconderem o prompt e o fluxo de validação, que são justamente o que precisa ser explicado e testado. Essa justificativa vai ao README.

## Tools

### `consultar_dados(pergunta: str)` (RF-31)

Tool de SQL, implementada como um subagente com prompt próprio. Passos:

1. Monta o contexto: DDL das views permitidas, comentários de coluna, 3 exemplos de linhas e uma lista curta de pares pergunta/SQL (few-shot) para perguntas típicas (top N, queda ano a ano, faturamento por período).
2. O Gemini devolve JSON com `sql` e `justificativa`.
3. Validação estática (RS-03), com `sqlglot`:
   - exatamente uma instrução;
   - somente `SELECT` (ou `WITH ... SELECT`);
   - só tabelas e views da lista permitida;
   - sem funções perigosas (`pg_sleep`, `pg_read_file`, `dblink`, `copy`, etc.);
   - `LIMIT` obrigatório, máximo 200, adicionado automaticamente se faltar.
4. Execução com o papel `cristalux_agent_ro` (spec `02`).
5. Em erro de sintaxe ou de execução, devolve o erro ao modelo para uma nova tentativa, no máximo 2.
6. Retorno para o orquestrador: `{sql, colunas, linhas, total_linhas, truncado, tentativas}`.

O orquestrador nunca vê credenciais nem escreve SQL por conta própria; só passa a pergunta em linguagem natural.

Premissas fixas embutidas no contexto do subagente (para evitar ambiguidade):
- "Faturamento" e "vendas" usam `vw_vendas` (somente `concluida`), a menos que a pergunta fale de cancelamentos, devoluções ou pendências.
- "Últimos 5 anos" é 2020-2024.
- "Queda" compara faturamento ano contra ano por UF.
- Toda resposta numérica informa o período e o filtro de status usados.

### `buscar_documentos(consulta: str, filtros?: dict)` (RF-32)

Retrieval da spec `03`. Retorna trechos com `id`, `texto`, `score`, `confianca`.

### `relatorio_qualidade(arquivo?: str)` (RF-33)

Devolve as métricas de `reports/qualidade.json` e a contagem atual de `quarantine.*`. Calculado em código. Responde "os dados estão limpos?" com números (spec `07`).

### `data_atual()` (RF-34)

Retorna a data de hoje. Necessária porque "últimos 5 anos" e "mês atual" dependem dela. Mostra o uso de tool simples no bônus.

### Tool de cálculo (opcional, RF-35)

`calcular(expressao)` para aritmética simples sobre números já retornados (variação percentual, ticket médio), usando `ast` seguro, sem `eval`. Só entra se os testes mostrarem erro aritmético do modelo.

## Política de resposta (RF-36)

- Número só aparece se vier de resultado de tool. Proibido calcular de cabeça.
- Sempre mostrar o período e o critério de status quando houver número de vendas.
- Se a tool não devolver linhas, dizer que não há dados para o filtro, sem completar com suposição.
- Se a pergunta pedir algo fora do escopo (dados externos, opinião), recusar e dizer o que o sistema cobre.
- Pergunta sobre qualidade dos dados: sempre chamar `relatorio_qualidade` antes de responder, e nunca derivar a resposta de texto de documento.

## Critérios de aceite

- RA-40: cada pergunta do conjunto de SQL (spec `06`) retorna o SQL e o resultado.
- RA-41: tentativas de `DROP`, `UPDATE`, segundo comando ou tabela fora da lista são bloqueadas pelo validador, com teste unitário para cada caso (RS-03).
- RA-42: com a tool de SQL indisponível, o agente informa a falha e não responde de memória.
