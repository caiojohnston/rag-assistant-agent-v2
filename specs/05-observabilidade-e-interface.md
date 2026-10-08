# 05. Observabilidade e interface

## Langfuse (RF-40)

- Cada pergunta gera um trace. Cada passo é uma observação aninhada:
  - `generation`: chamadas ao Gemini (prompt, resposta, tokens, latência);
  - `tool`: chamadas de tool (entrada, saída, duração);
  - `retriever`: busca vetorial (consulta, ids, scores);
  - `span`: validação de SQL (aprovado ou motivo do bloqueio).
- Instrumentação com o decorator `@observe` do SDK Python do Langfuse.
- Metadados do trace: `session_id` da conversa, versão do prompt, modelo, resultado da guarda.
- Scores anexados ao trace nas avaliações offline (spec `06`).

Hospedagem: Langfuse Cloud (plano gratuito) por padrão, pela simplicidade. Para uso 100% local há o caminho self-host via Docker Compose oficial do Langfuse, que exige mais serviços (ClickHouse, Redis, MinIO). A escolha é feita por variáveis de ambiente (`LANGFUSE_HOST`) e não altera o código.

## Interface Streamlit (RF-41)

Uma página, sem decoração:

- Título e uma linha de descrição.
- Barra lateral: modelo em uso, status das conexões (Postgres, Chroma, Langfuse), botão para limpar a conversa e a lista de perguntas de exemplo.
- Área de chat com `st.chat_message` e `st.chat_input`.
- Para cada resposta:
  - texto da resposta;
  - tabela com o resultado quando houver (`st.dataframe`);
  - bloco "Fontes": SQL executado ou ids das decisões usadas;
  - expansor "Raciocínio do agente" (`st.status`, que mostra "pensando" enquanto roda e fecha ao terminar). Ao expandir, lista os passos do trace, na ordem: chamada ao modelo, tool escolhida, SQL gerado, resultado da validação, linhas devolvidas, trechos recuperados com score. Link "Abrir no Langfuse" para o trace.
- Durante a execução, os passos aparecem no `st.status` à medida que acontecem (o agente emite eventos em um gerador).
- Ao final, os passos exibidos são lidos do Langfuse pelo `trace_id` (API do Langfuse). Se a API não responder, usa os eventos locais e avisa que o trace remoto não está disponível.

Estilo: tema padrão do Streamlit, sem emojis, sem ícones decorativos, textos curtos e objetivos.

## Critérios de aceite

- RA-50: uma pergunta de teste mostra o expansor com os passos reais e o link do trace.
- RA-51: com o Langfuse fora do ar, o app continua respondendo.
- RA-52: nenhum emoji em `app/` (verificação por busca no CI local).
