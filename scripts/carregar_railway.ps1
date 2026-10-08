<#
Carrega os CSV limpos no Postgres do Railway (rodar na sua maquina, onde estao os dados).

Uso:
  .\scripts\carregar_railway.ps1 -DatabaseUrl "<DATABASE_PUBLIC_URL do servico Postgres>" -AgentPassword "<mesma senha do AGENT_DB_PASSWORD do app>"

O script cria os schemas, o papel somente leitura, limpa os arquivos de dados_raw/ e grava tudo no banco remoto.
Depois reinicie o servico do app para que ele reindexe os textos no Chroma.
#>
param(
  [Parameter(Mandatory = $true)][string]$DatabaseUrl,
  [Parameter(Mandatory = $true)][string]$AgentPassword
)

$ErrorActionPreference = "Stop"
$env:DATABASE_URL = $DatabaseUrl
$env:AGENT_DB_PASSWORD = $AgentPassword
Remove-Item Env:AGENT_DATABASE_URL -ErrorAction SilentlyContinue

if (-not (Test-Path "dados_raw\vendas.csv")) { throw "Rode da raiz do projeto, onde existe a pasta dados_raw/." }

& .\.venv\Scripts\python.exe -m cristalux.pipeline.run
if ($LASTEXITCODE -ne 0) { throw "Falha na carga" }
Write-Host "Carga concluida. Reinicie o servico do app no Railway."
