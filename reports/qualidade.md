# Relatorio de qualidade dos dados

Linhas brutas: 293. Linhas na base limpa: 164. Linhas em quarentena: 129.

## compradores

Brutas: 30. Limpas: 15. Quarentena: 15.

| Problema | Volume | % | Impacto |
|---|---|---|---|
| duplicata_cnpj | 13 | 43.3% | Mesmo cliente com dois cadastros; fragmenta o historico e distorce rankings de compradores. |
| registro_vazio | 2 | 6.7% | Linha sem informacao util; inflaria contagens de registros se mantida. |
| cnpj_invalido | 15 | 100.0% | CNPJ com digitos verificadores invalidos; cadastro pode estar errado. |
| data_cadastro_invalida | 1 | 6.7% | Data de cadastro invalida. |
| email_ausente | 1 | 6.7% | Sem e-mail de contato. |
| grafias_diferentes:estado | 19 |  | O mesmo valor aparece escrito de varias formas; agrupamentos por esse campo ficariam fragmentados (19 grafias para 9 valores reais). |
| grafias_diferentes:segmento | 8 |  | O mesmo valor aparece escrito de varias formas; agrupamentos por esse campo ficariam fragmentados (8 grafias para 5 valores reais). |
| grafias_diferentes:porte | 9 |  | O mesmo valor aparece escrito de varias formas; agrupamentos por esse campo ficariam fragmentados (9 grafias para 4 valores reais). |

## vendedores

Brutas: 20. Limpas: 18. Quarentena: 2.

| Problema | Volume | % | Impacto |
|---|---|---|---|
| registro_vazio | 1 | 5.0% | Linha sem informacao util; inflaria contagens de registros se mantida. |
| duplicata_exata | 1 | 5.0% | Linha repetida; duplicaria faturamento e contagem de vendas. |
| email_dominio_incomum | 3 | 16.7% | Dominio de e-mail diferente do corporativo; provavel erro de digitacao. |
| email_ausente | 1 | 5.6% | Sem e-mail de contato. |
| admissao_invalida | 1 | 5.6% | Data de admissao no futuro ou invalida. |
| grafias_diferentes:regiao | 18 |  | O mesmo valor aparece escrito de varias formas; agrupamentos por esse campo ficariam fragmentados (18 grafias para 8 valores reais). |

## estoque_logistica

Brutas: 30. Limpas: 15. Quarentena: 15.

| Problema | Volume | % | Impacto |
|---|---|---|---|
| duplicata_nome | 13 | 43.3% | Mesmo item/pessoa cadastrado duas vezes; distorce contagens e estoque total. |
| registro_vazio | 2 | 6.7% | Linha sem informacao util; inflaria contagens de registros se mantida. |
| reposicao_invalida | 2 | 13.3% | Data de reposicao invalida ou no futuro. |

## decisoes

Brutas: 23. Limpas: 20. Quarentena: 3.

| Problema | Volume | % | Impacto |
|---|---|---|---|
| registro_vazio | 2 | 8.7% | Linha sem informacao util; inflaria contagens de registros se mantida. |
| duplicata_exata | 1 | 4.3% | Linha repetida; duplicaria faturamento e contagem de vendas. |
| suspeita_injection | 1 | 5.0% | Texto com instrucoes dirigidas a assistentes de IA; um LLM ingenuo pode obedece-lo. |

## vendas

Brutas: 190. Limpas: 96. Quarentena: 94.

| Problema | Volume | % | Impacto |
|---|---|---|---|
| data_vazia | 26 | 13.7% | Venda sem data nao entra em nenhuma serie mensal; sai do faturamento por vendedor. |
| data_inexistente | 19 | 10.0% | Data impossivel (ex: 30/02, mes 22); nao e possivel alocar a venda a um mes. |
| quantidade_negativa | 19 | 10.0% | Quantidade negativa sem relacao com a coluna de status; faturamento ficaria subestimado. |
| duplicata_exata | 12 | 6.3% | Linha repetida; duplicaria faturamento e contagem de vendas. |
| quantidade_invalida | 10 | 5.3% | Quantidade ausente ou zero; impossivel calcular valor. |
| comprador_inexistente | 9 | 4.7% | Comprador sem cadastro valido (registro vazio ou inexistente). |
| data_fora_do_periodo | 8 | 4.2% | Venda fora de 2020-2024; contaminaria a analise do periodo pedido. |
| data_formato_desconhecido | 4 | 2.1% | Data incompleta (ex: 'Jul/2021'); sem dia nao ha como fechar o mes com certeza. |
| valor_unitario_invalido | 3 | 1.6% | Preco ausente ou nao positivo; impossivel calcular valor. |
| status_ausente | 3 | 1.6% | Sem status nao e possivel saber se a venda foi concluida. |
| vendedor_ausente | 3 | 1.6% | Venda sem vendedor nao entra no ranking por vendedor. |
| comprador_ausente | 3 | 1.6% | Venda sem comprador nao entra em analises por cliente. |
| id_venda_ausente | 1 | 0.5% | Venda sem identificador; nao ha como deduplicar. |
| categoria_incoerente | 72 | 75.0% | Categoria da venda diferente da categoria natural do produto; analise por categoria nao e confiavel. |
| valor_total_divergente | 42 | 43.8% | valor_total informado difere de quantidade x preco x desconto; usa-se o recalculado. |
| desconto_indefinido | 26 | 27.1% | Desconto 'Sim' ou vazio sem percentual; margem real incerta. |
| data_ambigua | 4 | 4.2% | Data com hifen que pode ser dd-mm ou mm-dd; risco de cair no mes errado. |
| grafias_diferentes:regiao | 35 |  | O mesmo valor aparece escrito de varias formas; agrupamentos por esse campo ficariam fragmentados (35 grafias para 8 valores reais). |
| grafias_diferentes:status | 14 |  | O mesmo valor aparece escrito de varias formas; agrupamentos por esse campo ficariam fragmentados (14 grafias para 4 valores reais). |
| grafias_diferentes:produto | 27 |  | O mesmo valor aparece escrito de varias formas; agrupamentos por esse campo ficariam fragmentados (27 grafias para 10 valores reais). |
| grafias_diferentes:categoria | 11 |  | O mesmo valor aparece escrito de varias formas; agrupamentos por esse campo ficariam fragmentados (11 grafias para 4 valores reais). |
