# 99. Registro de mudanças

## Mudanças de spec

| Data | Spec | Mudança | Motivo |
|---|---|---|---|
| 2026-10-08 | todas | Criação inicial | Início do projeto |
| 2026-10-08 | 01, 02 | RN-15: `valor_total` passa a ser quantidade x preço (como a origem reporta) e entra `valor_liquido` com desconto. | O total informado ignora o desconto em 30 das 34 vendas com desconto; aplicá-lo mudaria o faturamento sem base na origem |
| 2026-10-08 | 06 | Gabarito do conjunto B: top N aceita qualquer entidade empatada no último lugar (B03) e a série mensal confere os valores, com rótulo do mês livre (B10). RAGAS: answer relevancy com 1 candidato. | Na primeira execução (`eval_20261008_1509`), B03 falhou por empate de 43 unidades entre dois compradores e B10 por exigir o rótulo "2022-02" quando o SQL devolveu mês 2 com os valores certos; o `gemini-3.1-flash-lite` não aceita múltiplos candidatos, o que zerou a answer relevancy do RAGAS. Os resultados originais ficam publicados em `reports/` ao lado dos corrigidos |
| 2026-10-08 | 05 | Instrumentação do Langfuse revisada com a skill oficial e auditada em traces reais; modelo padrão passa a `gemini-3.5-flash`, com `GEMINI_THINKING_LEVEL=low`. | Auditoria mostrou nomes genéricos e saída ruidosa na integração automática; latência de 30 a 100 s por pergunta com raciocínio alto |
| 2026-10-08 | 02, 07 | Camada raw vira uma tabela `raw.registros` (jsonb) e a quarentena `quarantine.registros`, em vez de uma tabela por arquivo. Relatório de qualidade passa a ser gravado em `meta.relatorio_qualidade`. | Simplifica a carga e permite o app ler o relatório no Railway, onde não há disco compartilhado com o job de carga |
| 2026-10-08 | 04 | Few-shot do agente de SQL trocado por exemplos que não repetem as perguntas do conjunto B. | Evitar contaminação da avaliação |
| 2026-10-08 | 01 | Vendedores: só V001 é duplicata, vizinhos são pessoas diferentes. Estoque: regra de duplicata por nome normalizado. Datas ambíguas com hífen sinalizadas. CNPJ inválido sinalizado. Produto canônico. | Leitura completa dos arquivos antes de codar; a spec inicial supunha pares de vendedores duplicados |

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
