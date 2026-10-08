# Experimentos de retrieval

15 perguntas com resposta no corpus e 10 fora do corpus (2 do conjunto A e 8 extras de calibracao).

## Embedding (chunk de 1 decisao)

| Variante | Chunks | hit@1 | hit@3 | hit@5 | MRR | score minimo das positivas | score maximo das negativas |
|---|---|---|---|---|---|---|---|
| gemini-embedding-001 | 59 | 1.0 | 1.0 | 1.0 | 1.0 | 0.746 | 0.671 |
| paraphrase-multilingual-MiniLM-L12-v2 (local) | 59 | 0.867 | 1.0 | 1.0 | 0.933 | 0.554 | 0.473 |

## Chunking (embedding Gemini)

| Variante | Chunks | hit@1 | hit@3 | hit@5 | MRR | score minimo das positivas | score maximo das negativas |
|---|---|---|---|---|---|---|---|
| 1 decisao por chunk (adotado) | 59 | 1.0 | 1.0 | 1.0 | 1.0 | 0.746 | 0.671 |
| decisoes agrupadas por ano | 44 | 0.667 | 0.867 | 0.867 | 0.767 | 0.628 | 0.671 |
| decisao dividida em 2 chunks | 79 | 1.0 | 1.0 | 1.0 | 1.0 | 0.729 | 0.671 |

## Varredura de threshold

### gemini-embedding-001

| Threshold | Recall@5 | Trechos retornados (media) | Recusa fora do corpus |
|---|---|---|---|
| 0.3 | 1.0 | 5.0 | 0.0 |
| 0.4 | 1.0 | 5.0 | 0.0 |
| 0.45 | 1.0 | 5.0 | 0.0 |
| 0.5 | 1.0 | 5.0 | 0.0 |
| 0.55 | 1.0 | 5.0 | 0.0 |
| 0.6 | 1.0 | 5.0 | 0.1 |
| 0.65 | 1.0 | 3.2 | 0.7 |
| 0.7 | 1.0 | 1.6 | 1.0 |
| 0.75 | 0.867 | 0.87 | 1.0 |
| 0.8 | 0.0 | 0.0 | 1.0 |

### paraphrase-multilingual-MiniLM-L12-v2 (local)

| Threshold | Recall@5 | Trechos retornados (media) | Recusa fora do corpus |
|---|---|---|---|
| 0.3 | 1.0 | 5.0 | 0.2 |
| 0.4 | 1.0 | 4.53 | 0.7 |
| 0.45 | 1.0 | 3.67 | 0.9 |
| 0.5 | 1.0 | 2.73 | 1.0 |
| 0.55 | 0.933 | 1.8 | 1.0 |
| 0.6 | 0.667 | 0.8 | 1.0 |
| 0.65 | 0.6 | 0.67 | 1.0 |
| 0.7 | 0.333 | 0.33 | 1.0 |
| 0.75 | 0.2 | 0.2 | 1.0 |
| 0.8 | 0.2 | 0.2 | 1.0 |
