# 99. Registro de mudanças

## Mudanças de spec

| Data | Spec | Mudança | Motivo |
|---|---|---|---|
| 2026-10-08 | todas | Criação inicial | Início do projeto |

## Edições nos dados originais

O enunciado exige documentar toda edição feita nos arquivos. Os CSVs em `dados_raw/` só tiveram o nome da empresa substituído por um nome fictício. Todas as demais edições acontecem em código, na camada `clean`. Esta tabela é preenchida durante as tarefas T04 a T06 e copiada para o README.

| Arquivo | Edição | Linhas afetadas | Motivo |
|---|---|---|---|
| `compradores.csv`, `vendedores.csv` | Nome real da empresa trocado por `Cristalux` (razão social e domínio de e-mail; a variante com erro de digitação virou `cristalu.com.br`) | 2 linhas em compradores, 19 em vendedores | Anonimização; nenhum nome real da empresa pode aparecer no repositório |
| (demais, a preencher nas tarefas T04 a T06) | | | |

## Decisões abertas

- Langfuse Cloud ou self-host (padrão: Cloud).
- Embedding final entre Gemini e multilingual-e5 (definido por experimento).
- Se colunas de contato (e-mail, telefone) aparecem ou não nas views do agente (padrão: não).
