"""Subagente que transforma a pergunta em SQL, valida, executa e se corrige (spec 04, tool consultar_dados)."""
from __future__ import annotations

import datetime as dt
import decimal
import json

import psycopg
from psycopg.rows import dict_row

from cristalux import obs
from cristalux.agent.sql_guard import validar
from cristalux.config import settings
from cristalux.db.dicionario import AMOSTRAS_PERGUNTA_SQL, descricao_texto
from cristalux.llm import gerar_texto

MAX_TENTATIVAS = 3  # 1 geracao + ate 2 correcoes
MAX_LINHAS_PARA_O_MODELO = 50

SYSTEM = """Voce converte perguntas em portugues em UMA consulta SQL para PostgreSQL.

Regras:
- Responda somente com JSON: {"sql": "...", "premissas": "..."}.
- Apenas SELECT. Use somente as views listadas abaixo, sem prefixo de esquema.
- Nunca use tabelas que nao estejam na lista. Nunca escreva SQL que altere dados.
- "Faturamento", "vendas" e "receita" usam vw_vendas (somente vendas concluidas). Use vw_vendas_todas apenas quando a
  pergunta falar de cancelamentos, devolucoes, pendencias ou de todos os status.
- "Faturamento" e a coluna valor_total. Use valor_liquido apenas se a pergunta pedir valor depois do desconto.
- "Ultimos 5 anos" significa 2020 a 2024. Os dados de venda cobrem apenas 2020 a 2024.
- "Queda" e comparacao de faturamento ano contra ano. "Regiao" e a coluna uf.
- "Volume" significa a soma de quantidade. "Melhor"/"top" sem criterio claro significa maior faturamento.
- Em premissas escreva em uma frase curta os criterios que voce assumiu (status, periodo, metrica).
- Sempre devolva colunas com nomes legiveis (alias) e ordene o resultado de forma util."""


def _contexto() -> str:
    exemplos = "\n".join(f"Pergunta: {p}\nSQL: {s}" for p, s in AMOSTRAS_PERGUNTA_SQL)
    return f"VIEWS DISPONIVEIS:\n{descricao_texto()}\n\nEXEMPLOS:\n{exemplos}\n"


def _json_seguro(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return v


def executar_sql(sql: str) -> tuple[list[str], list[dict]]:
    """Executa com o papel somente leitura. Levanta psycopg.Error em falha."""
    with psycopg.connect(settings.agent_database_url, autocommit=True, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            linhas = cur.fetchall()
            colunas = [c.name for c in cur.description] if cur.description else []
    return colunas, [{k: _json_seguro(v) for k, v in l.items()} for l in linhas]


def extrair_json(texto: str) -> dict:
    """JSON da resposta do modelo. Tolera cerca de codigo e texto em volta, comuns em modelos de reserva."""
    t = (texto or "").strip()
    for candidato in (t, t.strip("`").removeprefix("json").strip()):
        try:
            valor = json.loads(candidato)
            return valor if isinstance(valor, dict) else {"sql": "", "premissas": ""}
        except json.JSONDecodeError:
            pass
    ini, fim = t.find("{"), t.rfind("}")
    if 0 <= ini < fim:
        try:
            return json.loads(t[ini:fim + 1])
        except json.JSONDecodeError:
            pass
    return {"sql": "", "premissas": ""}


def _pedir_sql(pergunta: str, erro_anterior: str | None, sql_anterior: str | None) -> dict:
    prompt = f"{_contexto()}\nPERGUNTA: {pergunta}\n"
    if erro_anterior:
        prompt += (f"\nSua tentativa anterior falhou.\nSQL anterior: {sql_anterior}\nErro: {erro_anterior}\n"
                   "Corrija e devolva o JSON novamente.")
    bruto = gerar_texto(prompt, system=SYSTEM, json_mode=True,
                       nome="generate-sql" if not erro_anterior else "fix-sql")
    return extrair_json(bruto)


@obs.observar(name="generate-and-run-sql", as_type="agent")
def consultar(pergunta: str, emitir=lambda *a, **k: None) -> dict:
    """Devolve {sql, premissas, colunas, linhas, total_linhas, truncado, tentativas, erro}."""
    obs.atualizar(input=pergunta)
    erro, sql_anterior, premissas = None, None, ""
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        resposta = _pedir_sql(pergunta, erro, sql_anterior)
        sql, premissas = resposta.get("sql", ""), resposta.get("premissas", "")
        emitir("sql_gerado", "SQL gerado", {"sql": sql, "premissas": premissas, "tentativa": tentativa})
        with obs.observacao("validate-sql", "guardrail", input=sql, metadata={"tentativa": tentativa}) as span:
            v = validar(sql)
            span.update(output={"ok": v.ok, "motivo": v.motivo, "sql_normalizado": v.sql},
                        level="DEFAULT" if v.ok else "WARNING", status_message=v.motivo or None)
        emitir("sql_validado", "Validacao do SQL", {"ok": v.ok, "motivo": v.motivo, "sql": v.sql})
        if not v.ok:
            erro, sql_anterior = f"validacao: {v.motivo}", sql
            continue
        try:
            with obs.observacao("execute-sql", "tool", input=v.sql, metadata={"papel": "somente leitura"}) as span:
                colunas, linhas = executar_sql(v.sql)
                span.update(output={"colunas": colunas, "total_linhas": len(linhas),
                                    "linhas": linhas[:MAX_LINHAS_PARA_O_MODELO]})
        except psycopg.Error as e:
            erro, sql_anterior = f"execucao: {str(e).splitlines()[0][:200]}", v.sql
            emitir("sql_erro", "Erro na execucao", {"erro": erro})
            continue
        truncado = len(linhas) > MAX_LINHAS_PARA_O_MODELO
        emitir("sql_resultado", "Linhas devolvidas", {"total": len(linhas), "colunas": colunas})
        resultado = {"sql": v.sql, "premissas": premissas, "colunas": colunas,
                     "linhas": linhas[:MAX_LINHAS_PARA_O_MODELO], "total_linhas": len(linhas),
                     "truncado": truncado, "tentativas": tentativa, "erro": None}
        obs.atualizar(output=resultado, metadata={"tentativas": tentativa})
        return resultado
    resultado = {"sql": sql_anterior or "", "premissas": premissas, "colunas": [], "linhas": [], "total_linhas": 0,
                 "truncado": False, "tentativas": MAX_TENTATIVAS, "erro": erro}
    obs.atualizar(output=resultado, level="ERROR", status_message=erro)
    return resultado
