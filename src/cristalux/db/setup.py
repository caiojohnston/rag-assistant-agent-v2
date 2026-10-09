"""Cria esquemas, tabelas, views, papel somente leitura e dicionario. Idempotente.

Uso: python -m cristalux.db.setup
"""
from __future__ import annotations

import psycopg
from psycopg import sql

from cristalux.config import settings
from cristalux.db.dicionario import VIEWS

PAPEL_AGENTE = "cristalux_agent_ro"


def conectar(url: str | None = None, **kw) -> psycopg.Connection:
    return psycopg.connect(url or settings.database_url, **kw)


def _criar_papel(cur) -> None:
    senha = sql.Literal(settings.agent_db_password)
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (PAPEL_AGENTE,))
    verbo = "ALTER" if cur.fetchone() else "CREATE"
    cur.execute(sql.SQL(f"{verbo} ROLE {PAPEL_AGENTE} LOGIN PASSWORD {{}}").format(senha))
    cur.execute(sql.SQL(f"ALTER ROLE {PAPEL_AGENTE} SET default_transaction_read_only = on"))
    cur.execute(sql.SQL(f"ALTER ROLE {PAPEL_AGENTE} SET statement_timeout = '5s'"))
    cur.execute(sql.SQL(f"ALTER ROLE {PAPEL_AGENTE} SET idle_in_transaction_session_timeout = '10s'"))
    cur.execute(sql.SQL(f"ALTER ROLE {PAPEL_AGENTE} SET search_path = clean"))


def _conceder(cur) -> None:
    """O agente le somente as views e o dicionario. Nao acessa raw, quarantine nem tabelas base."""
    cur.execute("SELECT current_database()")
    banco = cur.fetchone()[0]
    cur.execute(sql.SQL(f"REVOKE ALL ON SCHEMA public, raw, quarantine FROM {PAPEL_AGENTE}"))
    cur.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA clean, meta, raw, quarantine FROM {}").format(
        sql.Identifier(PAPEL_AGENTE)))
    cur.execute(sql.SQL(f"GRANT CONNECT ON DATABASE {{}} TO {PAPEL_AGENTE}").format(sql.Identifier(banco)))
    cur.execute(sql.SQL(f"GRANT USAGE ON SCHEMA clean, meta TO {PAPEL_AGENTE}"))
    for view in VIEWS:
        cur.execute(sql.SQL(f"GRANT SELECT ON clean.{{}} TO {PAPEL_AGENTE}").format(sql.Identifier(view)))
    cur.execute(sql.SQL(f"GRANT SELECT ON meta.dicionario, meta.relatorio_qualidade TO {PAPEL_AGENTE}"))


def _dicionario(cur) -> None:
    cur.execute("DELETE FROM meta.dicionario")
    for view, info in VIEWS.items():
        cur.execute("INSERT INTO meta.dicionario (objeto, coluna, tipo, descricao) VALUES (%s, '', 'view', %s)",
                    (view, info["descricao"]))
        cur.execute(sql.SQL("COMMENT ON VIEW clean.{} IS {}").format(sql.Identifier(view), sql.Literal(info["descricao"])))
        for col, desc in info["colunas"].items():
            cur.execute("INSERT INTO meta.dicionario (objeto, coluna, tipo, descricao) VALUES (%s, %s, 'coluna', %s)",
                        (view, col, desc))
            cur.execute(sql.SQL("COMMENT ON COLUMN clean.{}.{} IS {}").format(
                sql.Identifier(view), sql.Identifier(col), sql.Literal(desc)))


def setup(url: str | None = None) -> None:
    with conectar(url, autocommit=True) as conn, conn.cursor() as cur:
        # Serializa boots simultaneos (deploy novo enquanto o antigo reinicia): evita chaves duplicadas no dicionario.
        cur.execute("SELECT pg_advisory_lock(746102)")
        for arquivo in ("01_schemas.sql", "02_views.sql"):
            cur.execute((settings.sql_dir / arquivo).read_text(encoding="utf-8"))
        _criar_papel(cur)
        _dicionario(cur)
        _conceder(cur)


if __name__ == "__main__":
    setup()
    print("banco configurado")
