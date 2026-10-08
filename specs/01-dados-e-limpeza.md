# 01. Dados e limpeza

Notebooks em `notebooks/`, um por etapa. A lógica testável fica em `src/cristalux/cleaning/` e os notebooks apenas chamam as funções, mostram antes e depois e comentam as decisões.

## Perfil inicial (levantado na leitura dos arquivos)

| Arquivo | Linhas | Principais problemas |
|---|---|---|
| `vendas.csv` | 190 | linhas duplicadas, `id_venda` repetido, datas em vários formatos e algumas inválidas ou vazias, quantidade negativa, status e região com muitas grafias, `desconto` misturado, moeda em texto |
| `compradores.csv` | 30 | pares duplicados por CNPJ, linha vazia (C011), capitalização e acentos inconsistentes, estado por extenso e sigla, limite de crédito em formatos diferentes |
| `vendedores.csv` | 20 | duplicata exata (V001), pares duplicados, registro vazio (V018), admissão futura (V019), e-mail com domínio errado, telefone em formatos diferentes |
| `decisoes.csv` | 23 | duplicata (D001), linhas vazias ou `N/A` (D021, D022), D013 com prompt injection |
| `estoque_logistica.csv` | 30 | pares duplicados em caixa diferente, estoque negativo, fornecedor vazio, moeda em texto |

O notebook `01_eda_qualidade` mede cada problema com contagem e percentual e é a fonte do relatório de qualidade (RN-01).

## Regras de negócio e dados

- RN-01: relatório de qualidade por arquivo com tipo de problema, volume afetado e impacto potencial. Gerado por código, salvo em `reports/qualidade.json` e `reports/qualidade.md`.
- RN-02: valores originais são preservados na camada `raw`. A camada `clean` guarda apenas valores normalizados e válidos. Linhas rejeitadas vão para `quarantine` com o motivo.
- RN-03: nenhuma linha é descartada em silêncio. Toda exclusão tem motivo registrado.

### Vendas (`vendas.csv`)

Objetivo: calcular faturamento mensal por vendedor de 2020 a 2024.

| Regra | Decisão |
|---|---|
| RN-10 Datas | Parse dos formatos observados (`dd/mm/aaaa`, `aaaa-mm-dd`, `aaaa/mm/dd`, `dd-mm-aa`, `dd.mm.aa`, etc.). Formato ambíguo `dd/mm` versus `mm/dd` resolvido por `dd/mm`, a convenção brasileira, e validado: `11/22/2022` é inválido e vai para quarentena. Data inexistente (`30/02`, `31/11`, `00/12`), vazia, formato incompleto (`Jul/2021`) ou fora de 2020-2024 vai para quarentena. Não se inventa data. |
| RN-11 Duplicatas | Linha totalmente igual: mantém uma. `id_venda` repetido com conteúdo diferente: mantém a linha mais completa (menos nulos) e, no empate, a de data mais recente; as outras vão para quarentena com motivo `id_duplicado`. |
| RN-12 Status | Normaliza caixa e acento e agrupa em `concluida` (concluída, concluido, fechado, fechada), `cancelada`, `devolvida`, `pendente` (pendente, em aberto). |
| RN-13 Faturamento | Só `concluida` entra no faturamento. Cancelada, devolvida, pendente e em aberto ficam fora e são reportadas à parte. |
| RN-14 Quantidade negativa | Tratada como erro de lançamento, vai para quarentena. Não é assumida como devolução, porque a devolução já tem status próprio. |
| RN-15 Valores | Converte `R$ 1.424,08` e `1424.08` para número. `valor_total` é recalculado como `quantidade * valor_unitario * (1 - desconto)` e comparado com o informado. Divergência acima de 1 centavo é sinalizada em coluna `valor_total_divergente`, e o valor usado no faturamento é o recalculado. |
| RN-16 Desconto | Normaliza para fração: `5%`, `5` e `0.05` viram 0,05. `nenhum`, `não`, `0`, `0%` viram 0. `Sim` sem valor e vazio viram nulo, tratado como 0 no cálculo e contado como `desconto_indefinido`. Descontos acima de 10% são sinalizados, pois a decisão D018 fixou o limite em 10%. |
| RN-17 Região | Mapa único de variantes para a UF e o nome oficial (`S.Paulo`, `sp - capital`, `São Paulo` viram `SP`). Cidades (`Salvador`, `Florianópolis`) são mapeadas para a UF. |
| RN-18 Categoria | Normaliza caixa e acento. Divergência entre produto e categoria é sinalizada, mas a categoria informada é mantida, pois não há tabela de produto confiável nos dados de vendas. |
| RN-19 Integridade referencial | `id_vendedor` e `id_comprador` ausentes ou inexistentes nas dimensões limpas vão para quarentena com o motivo correspondente. |

### Compradores e vendedores

| Regra | Decisão |
|---|---|
| RN-20 Chave de duplicidade compradores | CNPJ normalizado (só dígitos). Linha sem dados úteis (C011) é descartada para quarentena. |
| RN-21 Chave de duplicidade vendedores | Nome normalizado (sem acento, caixa baixa) mais telefone normalizado ou e-mail. V001 é duplicata exata. |
| RN-22 Registro sobrevivente | Mantém o registro com mais campos preenchidos; no empate, o de menor id (mais antigo, já referenciado em vendas); no empate de ids, o de formato mais próximo do padrão. Campos nulos do sobrevivente são preenchidos com os do descartado. |
| RN-23 Mapa de ids | Cada id descartado é mapeado para o id sobrevivente (`dim_*_alias`), de modo que vendas apontando para o id descartado sejam reatribuídas ao sobrevivente. |
| RN-24 Normalização | UF por sigla, porte e segmento em formato canônico, status em `ativo`/`inativo`, comissão e meta em número, telefone só com dígitos e formatado na saída. |
| RN-25 Admissão futura | Data de admissão depois de 2026-10-08 (V019: 2030) é inválida. O campo fica nulo e o registro é sinalizado. Os demais campos permanecem. |
| RN-26 E-mail | Domínio fora de `cristalux.com.br` em vendedor é sinalizado, não corrigido, pois não há como saber o correto. |

Observação: os CNPJs de C027 e C028 diferem do de C001. A chave é o CNPJ, portanto não são duplicatas de C001.

### Estoque e decisões

- RN-30 Estoque: pares duplicados por nome normalizado; sobrevive o registro mais completo e de formato padrão. Estoque negativo é inválido, vai para quarentena. Fornecedor vazio fica nulo e é sinalizado.
- RN-31 Decisões: remove duplicata (D001), linhas vazias e `N/A` vão para quarentena. D013 é mantida como está e recebe `suspeita_injection = true` pelo detector da spec `07`.

## Saídas

- Tabelas `clean.*` no Postgres (ver `02`).
- `quarantine.*` com `motivo`, `arquivo_origem`, `linha_origem`.
- `reports/qualidade.json` e `.md`.
- Tabela de edições feitas nos dados (o enunciado exige documentar toda edição e o motivo), em `99-registro-de-mudancas.md` e no README.

## Critérios de aceite

- RA-01: soma de linhas limpas + quarentena + duplicatas removidas = linhas brutas, para cada arquivo (conservação).
- RA-02: nenhuma data fora de 2020-2024 em `clean.vendas`.
- RA-03: nenhum `id_vendedor` ou `id_comprador` órfão em `clean.vendas`.
- RA-04: faturamento mensal por vendedor calculável por uma única query sobre a view `vw_faturamento_mensal_vendedor`.
- RA-05: testes unitários das funções de parse (data, moeda, desconto, status, região) com os casos reais do arquivo.
