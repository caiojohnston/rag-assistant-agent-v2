"""Leitura do relatorio de qualidade: do banco (preferencial, funciona no Railway) ou do arquivo."""
from __future__ import annotations

import json

import psycopg

from cristalux.config import settings


def ler_relatorio() -> dict | None:
    try:
        with psycopg.connect(settings.agent_database_url, connect_timeout=5) as conn:
            linha = conn.execute("SELECT relatorio FROM meta.relatorio_qualidade ORDER BY id DESC LIMIT 1").fetchone()
        if linha:
            return linha[0]
    except psycopg.Error:
        pass
    arquivo = settings.reports_dir / "qualidade.json"
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else None
