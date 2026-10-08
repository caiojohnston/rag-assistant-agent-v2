"""Monta o corpus do RAG a partir do banco, do dicionario, do relatorio de qualidade e das regras."""
from __future__ import annotations

import json

from cristalux.config import ROOT, settings
from cristalux.db.dicionario import VIEWS
from cristalux.rag import chunking as ck


def _decisoes() -> list[dict]:
    from psycopg.rows import dict_row

    from cristalux.db.setup import conectar

    with conectar(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM clean.decisao ORDER BY id_decisao")
        return cur.fetchall()


def montar() -> list[ck.Chunk]:
    chunks = [ck.chunk_decisao(d) for d in _decisoes()]
    chunks += ck.chunks_dicionario(VIEWS)
    rel = settings.reports_dir / "qualidade.json"
    if rel.exists():
        chunks += ck.chunks_qualidade(json.loads(rel.read_text(encoding="utf-8")))
    spec = ROOT / "specs" / "01-dados-e-limpeza.md"
    if spec.exists():
        chunks += ck.chunks_regras(spec.read_text(encoding="utf-8"))
    return chunks
