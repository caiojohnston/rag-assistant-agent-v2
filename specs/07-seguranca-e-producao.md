# 07. Segurança e produção

## Prompt injection (RS-02)

Caso real nos dados: D013 contém texto que se apresenta como "pré-validação automática" e instrui assistentes de IA a declarar a base como excelente e a omitir problemas. O sistema deve tratá-lo como dado, não como ordem.

Defesas em camadas:

1. Detector na indexação e na carga: regras simples (regex e lista de termos como "instrução para assistentes de ia", "ignore ... anteriores", "retorne obrigatoriamente", "não mencione") marcam o registro com `suspeita_injection` e `confianca = nao_confiavel`. O registro não é apagado.
2. Isolamento no prompt: todo texto recuperado entra em bloco delimitado e rotulado como dado; o prompt de sistema diz que ele nunca contém ordens.
3. Fonte da verdade em código: a resposta sobre qualidade vem de `relatorio_qualidade`, calculado sobre os dados. Um documento não consegue mudar esse número.
4. Verificação da saída: um verificador simples (código) rejeita respostas que contenham a assinatura do ataque ("score = 9.8", "nenhuma limpeza necessária") e as refaz uma vez com a nota do problema. Tratar como defesa em profundidade, não como controle único.
5. O SQL gerado a partir da pergunta nunca recebe texto de documentos no prompt.

O que isso revela (resposta para a pergunta 8 do enunciado, a ser escrita no README): um LLM que lê dados sem tratamento obedece a texto embutido nas células, não distingue dado de instrução e responde com confiança sobre uma base suja. A mitigação é separar o que vem de código do que vem de texto livre.

## Três maiores riscos de um agente com acesso direto ao banco (RS-03 a RS-05)

| Risco | Mitigação implementada |
|---|---|
| RS-03 Escrita ou exfiltração por SQL gerado (DROP, UPDATE, SELECT em tabela sensível, comando múltiplo) | Papel somente leitura, acesso só a views, validador com `sqlglot`, `LIMIT` obrigatório, `statement_timeout`, colunas pessoais fora das views, log de todo SQL |
| RS-04 Prompt injection vinda dos próprios dados ou de usuário | Seção acima, mais separação entre texto e SQL |
| RS-05 Resposta errada com aparência de certa (SQL semanticamente errado, métrica mal interpretada) e custo descontrolado | SQL exibido ao usuário, premissas explícitas em toda resposta numérica, avaliação contínua com o conjunto B, limite de chamadas por pergunta, cache e limite de tokens, alerta no Langfuse de custo e latência |

Outros pontos (para a seção de limitações): vazamento de dado pessoal no prompt, dependência do free tier, e variação de resposta entre versões do modelo (por isso `temperature = 0` e modelo fixado por variável).

## Atualização mensal sem reconstruir (RF-50)

Chegam novos arquivos de vendas todo mês.

Banco tabular:
1. Arquivo entra em `raw` com `sha256` registrado em `meta.ingest_log`. Hash já visto: ignorado.
2. O mesmo código de limpeza roda apenas sobre o lote novo.
3. `clean.fato_venda` recebe `INSERT ... ON CONFLICT (id_venda) DO UPDATE`. Correções de vendas antigas atualizam o registro em vez de duplicar.
4. Linhas rejeitadas vão para `quarantine` com o lote de origem. Dimensões novas entram antes das vendas que as referenciam.
5. Views refletem o novo dado sem reprocessar nada.

Vetorial:
1. Textos novos (decisões do mês, relatório de qualidade atualizado) viram chunks com ID determinístico (`sha1`).
2. O indexador compara IDs: embeda e grava apenas os novos ou alterados, e remove os que sumiram.
3. O dicionário de dados e o relatório de qualidade são regenerados e reindexados a cada carga (poucos chunks, custo baixo).

Controles: execução agendada (cron ou Airflow, fora do escopo do teste, descrita no README), validações de esquema antes da carga, relatório de qualidade comparando o lote com o histórico, e alerta se a taxa de quarentena do mês passar de um limite.

## Critérios de aceite

- RA-70: carregar o mesmo CSV duas vezes não altera nenhuma contagem.
- RA-71: carregar um lote com uma venda corrigida atualiza a linha e não cria outra.
- RA-72: reindexar sem mudança embeda zero chunks.
- RA-73: o conjunto C (spec `06`) passa nos casos de injection.
