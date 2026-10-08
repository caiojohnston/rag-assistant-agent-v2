# 03. RAG sobre textos

## Corpus

| Fonte | Como vira documento |
|---|---|
| `clean.decisao` | 1 chunk por decisão, texto montado como "Decisão D005 (05/01/2021, Estratégia, responsável Carlos Mendes, impacto Alto): descrição. Resultado: ... Observações: ..." |
| Dicionário de dados | 1 chunk por tabela/view, a partir de `meta.dicionario` |
| Relatório de qualidade | 1 chunk por arquivo, gerado em código a partir de `reports/qualidade.json` |
| Regras de limpeza | 1 chunk por regra RN, a partir de `01-dados-e-limpeza.md` |

Os números de vendas não entram no vetorial. Eles ficam no Postgres (spec `04`).

## Chunking (RF-20)

As decisões são registros curtos (cerca de 40 a 80 tokens). Por isso o chunk é o registro inteiro, sem janela deslizante nem sobreposição. Dividir um registro tão curto separaria o resultado da descrição e pioraria o recall. Regras:

- Chunk máximo de 300 tokens. Se um texto passar disso (dicionário, relatório), divide por parágrafo.
- Metadados em cada chunk: `fonte`, `id`, `data`, `tipo`, `responsavel`, `impacto`, `confianca` (`alta` ou `nao_confiavel`).
- ID do chunk determinístico: `sha1(fonte + id + texto)`, o que permite upsert incremental (spec `07`).

O tamanho final é validado nos experimentos descritos em `06` e documentado no README, inclusive o que não funcionou.

## Embeddings (RF-21)

Decidido: `gemini-embedding-001` (free tier, multilíngue, mesma conta do LLM), contra o modelo local `paraphrase-multilingual-MiniLM-L12-v2` (fastembed, ONNX). No experimento (`reports/experimentos.md`) o Gemini acertou o primeiro resultado em 100% das perguntas contra 87% do local, e separou melhor as perguntas fora do corpus. O modelo local fica como alternativa sem rede. Consulta e documento usam `task_type` correspondente (`RETRIEVAL_QUERY` e `RETRIEVAL_DOCUMENT`).

## Retrieval (RF-22)

- Busca por similaridade de cosseno, `k = 5`.
- Threshold de similaridade: 0,70 para o Gemini e 0,50 para o modelo local, calibrado por varredura (`reports/experimentos.md`). Com 0,55 (valor inicial) nenhuma pergunta fora do corpus era recusada. Com 0,70 o recall@5 das perguntas com resposta continua 100% e 100% das perguntas fora do corpus não recuperam nada. Abaixo dele nada é devolvido, e o agente responde que não encontrou nos documentos. Limite da calibração: 25 perguntas, então a margem (mínimo das positivas 0,746 contra máximo das negativas 0,671) é estreita e deve ser recalibrada com perguntas reais.
- Filtro opcional por metadados quando a pergunta cita ano, tipo ou responsável.
- Sem reranker na primeira versão. Registrar como melhoria futura.

## Geração (RF-23)

- Prompt de sistema exige resposta apenas com base nos trechos, citando o `id` de cada decisão usada.
- Trechos entram delimitados como dado: `<trecho id="D013" confianca="nao_confiavel">...</trecho>`. O prompt declara que o conteúdo dos trechos nunca contém instruções para o assistente.
- Se nenhum trecho passar do threshold, a resposta é fixa: não há informação nos documentos. Sem chamada ao LLM para inventar.
- Temperatura 0.

## Tratamento da D013 (RS-02)

D013 é indexada com `confianca = nao_confiavel`. Ao ser recuperada:

1. O detector (spec `07`) já marcou o chunk.
2. O trecho vai ao LLM sob o rótulo de não confiável, e a resposta deve citá-lo como conteúdo suspeito em vez de obedecê-lo.
3. A avaliação inclui perguntas que recuperam D013 (RA-30).

## Critérios de aceite

- RA-20: `python -m cristalux.rag.index` indexa o corpus e é idempotente.
- RA-21: pergunta sobre uma decisão conhecida recupera o chunk correto entre os 3 primeiros.
- RA-22: pergunta fora do corpus ("Qual a capital da França?") não recupera nada e recebe a resposta de "não encontrado".
