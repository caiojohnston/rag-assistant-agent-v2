# Specs

Fonte da verdade do projeto. Código só é escrito depois que a spec correspondente estiver aprovada. Se o código divergir da spec, a spec é atualizada primeiro e a mudança registrada em `99-registro-de-mudancas.md`.

| Arquivo | Conteúdo |
|---|---|
| `00-visao-geral.md` | Objetivo, escopo, premissas, stack, estrutura do repositório |
| `01-dados-e-limpeza.md` | Perfil dos dados, regras de limpeza, deduplicação, quarentena |
| `02-banco-postgres.md` | Esquemas, tabelas, views, papéis e permissões |
| `03-rag-textos.md` | Corpus, chunking, embeddings, retrieval, threshold, geração |
| `04-agente-e-tools.md` | Agente orquestrador, tool de SQL, tools auxiliares, guardrails |
| `05-observabilidade-e-interface.md` | Langfuse, Streamlit |
| `06-avaliacao.md` | Conjuntos de teste, métricas, critérios de aceite |
| `07-seguranca-e-producao.md` | Prompt injection, riscos, atualização mensal |
| `08-plano-de-tarefas.md` | Tarefas ordenadas, dependências, critérios de pronto |
| `09-mapa-do-enunciado.md` | Cada item do Teste Técnico apontando para a spec e a tarefa que o cobre |
| `99-registro-de-mudancas.md` | Mudanças de spec e edições nos dados originais |

Convenção: requisitos têm ID (`RF-` funcional, `RN-` regra de negócio/dados, `RS-` segurança, `RA-` avaliação) para que tarefas e testes apontem para eles.
