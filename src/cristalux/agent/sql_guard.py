"""Validador estatico do SQL gerado pelo LLM (spec 04, RS-03).

Defesa em camadas: este validador e a primeira. A segunda e o papel somente leitura do Postgres,
que nega escrita e acesso a tabelas base mesmo que algo passe por aqui.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from cristalux.db.dicionario import VIEWS

LIMITE_LINHAS = 200
TABELAS_PERMITIDAS = set(VIEWS) | {"dicionario"}
ESQUEMAS_PERMITIDOS = {"", "clean", "meta"}
FUNCOES_PROIBIDAS_PREFIXOS = ("pg_", "lo_", "dblink", "set_config", "current_setting", "txid_", "query_to_xml")

_PROIBIDOS = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command, exp.Merge,
              exp.TruncateTable, exp.Set, exp.Into, exp.Lock, exp.Copy, exp.Use)


@dataclass
class Validacao:
    ok: bool
    sql: str = ""
    motivo: str = ""


def validar(sql: str, limite: int = LIMITE_LINHAS) -> Validacao:
    """Aceita um unico SELECT sobre as views permitidas. Devolve o SQL normalizado com LIMIT."""
    if not sql or not sql.strip():
        return Validacao(False, motivo="sql vazio")
    try:
        instrucoes = [i for i in sqlglot.parse(sql, read="postgres") if i is not None]
    except sqlglot.errors.ParseError as e:
        return Validacao(False, motivo=f"erro de sintaxe: {str(e)[:200]}")
    if len(instrucoes) != 1:
        return Validacao(False, motivo="e permitida exatamente uma instrucao")
    arvore = instrucoes[0]
    if not isinstance(arvore, (exp.Select, exp.Union, exp.Subquery)):
        return Validacao(False, motivo=f"somente SELECT e permitido (recebido {type(arvore).__name__})")
    proibido = arvore.find(*_PROIBIDOS)
    if proibido is not None:
        return Validacao(False, motivo=f"comando nao permitido: {type(proibido).__name__}")

    ctes = {c.alias_or_name.lower() for c in arvore.find_all(exp.CTE)}
    for t in arvore.find_all(exp.Table):
        nome = t.name.lower()
        esquema = (t.db or "").lower()
        if nome in ctes and not esquema:
            continue
        if esquema not in ESQUEMAS_PERMITIDOS or nome not in TABELAS_PERMITIDAS:
            return Validacao(False, motivo=f"tabela nao permitida: {(esquema + '.' if esquema else '') + nome}")

    for f in arvore.find_all(exp.Func):
        nome = (f.sql_name() if not isinstance(f, exp.Anonymous) else f.name).lower()
        if nome.startswith(FUNCOES_PROIBIDAS_PREFIXOS):
            return Validacao(False, motivo=f"funcao nao permitida: {nome}")

    # LIMIT obrigatorio e limitado.
    existente = arvore.args.get("limit")
    if existente is None:
        arvore = arvore.limit(limite)
    else:
        try:
            if int(existente.expression.name) > limite:
                arvore = arvore.limit(limite)
        except (ValueError, AttributeError):
            arvore = arvore.limit(limite)
    return Validacao(True, sql=arvore.sql(dialect="postgres"))
