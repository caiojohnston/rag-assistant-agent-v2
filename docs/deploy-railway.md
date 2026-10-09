# Deploy no Railway

Dois serviços: um Postgres e o app (esta imagem Docker). Os CSV ficam fora do repositório e do container; eles são carregados no banco a partir da sua máquina.

Ordem importa: primeiro o banco e a carga dos dados, depois o app. O app indexa os textos (decisões, dicionário e relatório de qualidade) no Chroma ao subir, e para isso as decisões já precisam estar no banco.

## 1. Criar o projeto e o Postgres

1. Em railway.com, crie um projeto vazio.
2. `+ New` > `Database` > `Add PostgreSQL`. O serviço se chama `Postgres`.
3. No serviço Postgres, aba `Variables`, copie o valor de `DATABASE_PUBLIC_URL` (endereço acessível de fora, usado só para a carga). Se a variável não existir, habilite o `TCP Proxy` na aba `Settings` > `Networking`.

## 2. Carregar os dados

Na raiz do projeto, na sua máquina, com a pasta `dados_raw/` preenchida e o ambiente virtual criado (`.venv`):

```powershell
.\scripts\carregar_railway.ps1 -DatabaseUrl "<DATABASE_PUBLIC_URL>" -AgentPassword "<senha-do-papel-somente-leitura>"
```

O script cria os esquemas, as views e o papel somente leitura `cristalux_agent_ro`, limpa os CSV e grava tudo no banco do Railway. Guarde a senha que você escolheu: o app precisa da mesma no passo 4 (`AGENT_DB_PASSWORD`). Gere uma senha aleatória, por exemplo com `[guid]::NewGuid().ToString("N")`.

Saída esperada: cinco linhas `X limpas, Y em quarentena` (compradores 15/15, vendedores 18/2, estoque 15/15, decisões 20/3, vendas 96/94).

### Alternativa sem expor o banco (foi a usada no deploy real)

Em vez da URL pública, abra um túnel criptografado com o Railway CLI (login feito com `railway login`):

```powershell
railway link -p <id-do-projeto> -e production -s Postgres
railway connect Postgres --tunnel-only -P 15432     # deixa o túnel aberto; mostra usuário e senha do banco
```

Em outro terminal, na raiz do projeto, aponte a carga para o túnel:

```powershell
$env:DATABASE_URL = "postgresql://postgres:<senha-mostrada-pelo-tunel>@127.0.0.1:15432/railway"
$env:AGENT_DB_PASSWORD = "<senha-do-papel-somente-leitura>"
.\.venv\Scripts\python.exe -m cristalux.pipeline.run
```

O banco não precisa de acesso público, e a senha do papel somente leitura é a mesma que vai na variável `AGENT_DB_PASSWORD` do app.

## 3. Criar o serviço do app

1. `+ New` > `GitHub Repo` > escolha `rag-assistant-agent-v2` (repositório privado: autorize o app do Railway no GitHub quando pedir).
2. O Railway lê o `railway.json` e usa o `Dockerfile`. Não precisa configurar build nem comando de start.

## 4. Variáveis do serviço do app

Aba `Variables` do serviço do app:

| Variável | Valor |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (referência ao serviço Postgres, rede privada) |
| `AGENT_DB_PASSWORD` | a mesma senha usada no script do passo 2 |
| `GEMINI_API_KEY` | sua chave |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |
| `GEMINI_THINKING_LEVEL` | `low` |
| `LANGFUSE_PUBLIC_KEY` | chave pública do projeto Langfuse |
| `LANGFUSE_SECRET_KEY` | chave secreta do projeto Langfuse |
| `LANGFUSE_BASE_URL` | `https://us.cloud.langfuse.com` (a região do seu projeto) |
| `LANGFUSE_TRACING_ENVIRONMENT` | `production` |
| `APP_PASSWORD` | senha de acesso ao app (obrigatória, ver aviso abaixo) |

Não precisa definir `PORT`: o Railway injeta. Também não precisa de `AGENT_DATABASE_URL`: o app monta a conexão do papel somente leitura a partir da `DATABASE_URL` e da `AGENT_DB_PASSWORD`.

Opcional, para o índice do Chroma sobreviver a novos deploys: crie um `Volume` montado em `/data` e defina `CHROMA_PATH=/data/chroma`. Sem volume o índice é refeito a cada subida (são cerca de 60 trechos, poucos segundos).

Aviso: o link do Railway é público. `APP_PASSWORD` coloca uma tela de senha na frente do app. Sem ela, qualquer pessoa com o link consome sua cota do Gemini e vê dados da empresa.

## 5. Publicar e abrir

1. Aba `Settings` > `Networking` > `Generate Domain`. Esse é o link do app.
2. Aba `Deployments`: acompanhe os logs. Sequência esperada:
   - `banco configurado`
   - `{'backend': 'gemini', 'novos': 59, ...}` (indexação do RAG)
   - `You can now view your Streamlit app in your browser.`
3. Abra o link, digite a senha, e confira a barra lateral: Postgres `ok (96 vendas)`, Chroma `ok (59 trechos...)`, Gemini `chave configurada`, Langfuse `ativo`.

## Se algo falhar

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Barra lateral: Postgres `indisponível` | `AGENT_DB_PASSWORD` diferente da usada na carga, ou carga não feita | Rodar de novo o script do passo 2 com a mesma senha do app |
| Chroma com 0 ou poucos trechos | App subiu antes da carga dos dados | Fazer a carga e reiniciar o serviço (`Deployments` > `Restart`) |
| Erro `429` ou `RESOURCE_EXHAUSTED` na resposta | Cota diária do Gemini no plano gratuito | Esperar o reset, trocar `GEMINI_MODEL` ou habilitar faturamento na chave |
| Healthcheck falha no deploy | Indexação lenta no boot | Aumentar `healthcheckTimeout` no `railway.json` |
| Sem traces no Langfuse | Região errada em `LANGFUSE_BASE_URL` | Usar a URL da região do projeto (US: `https://us.cloud.langfuse.com`) |

## Atualizar os dados depois

Novos CSV em `dados_raw/` e o mesmo script do passo 2. A carga é idempotente: arquivos já ingeridos (mesmo hash) são ignorados, vendas existentes são atualizadas e as novas inseridas. Reinicie o app para reindexar o texto, se as decisões mudaram.
