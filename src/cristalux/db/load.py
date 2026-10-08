"""Gravacao idempotente das camadas raw, clean e quarantine."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.types.json import Jsonb

from cristalux.cleaning.base import Resultado


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _py(v):
    """Converte NaN/NaT/numpy para tipos que o psycopg aceita."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if v is pd.NaT:
        return None
    if hasattr(v, "item") and not isinstance(v, (list, str, date)):
        v = v.item()
        if isinstance(v, float) and math.isnan(v):
            return None
    if isinstance(v, (list, tuple)):
        return list(v)
    return v


def upsert(conn: psycopg.Connection, tabela: str, df: pd.DataFrame, colunas: list[str], pk: str) -> None:
    """INSERT ... ON CONFLICT (pk) DO UPDATE. Reprocessar o mesmo lote nao duplica nada."""
    if df.empty:
        return
    atualiza = ", ".join(f"{c} = EXCLUDED.{c}" for c in colunas if c != pk)
    cmd = (f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({', '.join(['%s'] * len(colunas))}) "
           f"ON CONFLICT ({pk}) DO UPDATE SET {atualiza}")
    linhas = [tuple(_py(r[c]) for c in colunas) for r in df.to_dict("records")]
    with conn.cursor() as cur:
        cur.executemany(cmd, linhas)


def ja_ingerido(conn, arquivo: str, digest: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM meta.ingest_log WHERE arquivo = %s AND sha256 = %s", (arquivo, digest))
        return cur.fetchone() is not None


def gravar_raw_e_quarentena(conn, arquivo: str, digest: str, raw: pd.DataFrame, res: Resultado) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM quarantine.registros WHERE arquivo = %s", (arquivo,))
        cur.executemany(
            "INSERT INTO raw.registros (arquivo, linha_origem, lote_sha256, dados) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            [(arquivo, int(r["linha_origem"]), digest,
              Jsonb({k: v for k, v in r.items() if k != "linha_origem"})) for r in raw.to_dict("records")])
        cur.executemany(
            "INSERT INTO quarantine.registros (arquivo, linha_origem, lote_sha256, motivo, id_sobrevivente, dados) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            [(arquivo, int(r["linha_origem"]), digest, r["motivo"], _py(r["id_sobrevivente"]),
              Jsonb({k: _py(v) for k, v in r.items() if k not in ("linha_origem", "motivo", "id_sobrevivente")}))
             for r in res.quarantine.to_dict("records")])


def registrar_ingestao(conn, arquivo: str, digest: str, res: Resultado) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO meta.ingest_log (arquivo, sha256, linhas_lidas, linhas_ok, linhas_quarentena) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (arquivo, sha256) DO NOTHING",
            (arquivo, digest, res.stats["linhas_brutas"], res.stats["linhas_limpas"], res.stats["quarentena"]))


def gravar_alias(conn, tabela: str, alias: dict) -> None:
    if not alias:
        return
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO {tabela} (id_descartado, id_sobrevivente) VALUES (%s, %s) "
            "ON CONFLICT (id_descartado) DO UPDATE SET id_sobrevivente = EXCLUDED.id_sobrevivente",
            list(alias.items()))


def ids_existentes(conn, tabela: str, coluna: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(f"SELECT {coluna} FROM {tabela}")
        return {r[0] for r in cur.fetchall()}


def aliases(conn, tabela: str) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(f"SELECT id_descartado, id_sobrevivente FROM {tabela}")
        return dict(cur.fetchall())


COLUNAS = {
    "clean.dim_vendedor": ["id_vendedor", "nome", "email", "telefone", "uf", "data_admissao", "meta_mensal",
                           "comissao_pct", "status", "supervisor", "flags"],
    "clean.dim_comprador": ["id_comprador", "razao_social", "cnpj", "cidade", "uf", "segmento", "porte", "contato",
                            "email", "data_cadastro", "limite_credito", "status", "flags"],
    "clean.fato_venda": ["id_venda", "data", "id_vendedor", "id_comprador", "produto", "produto_original",
                         "categoria", "categoria_produto", "quantidade", "valor_unitario", "desconto", "valor_total",
                         "valor_total_informado", "status", "uf", "observacoes", "flags", "linha_origem"],
    "clean.estoque": ["id_produto", "nome_produto", "categoria", "estoque_atual", "estoque_minimo",
                      "ultima_reposicao", "lead_time_dias", "fornecedor", "custo_unitario", "localizacao_deposito",
                      "status", "flags"],
    "clean.decisao": ["id_decisao", "data", "tipo", "descricao", "responsavel", "impacto", "resultado",
                      "observacoes", "suspeita_injection", "padroes_injection", "flags"],
}
PKS = {"clean.dim_vendedor": "id_vendedor", "clean.dim_comprador": "id_comprador", "clean.fato_venda": "id_venda",
       "clean.estoque": "id_produto", "clean.decisao": "id_decisao"}


def gravar_clean(conn, tabela: str, df: pd.DataFrame) -> None:
    upsert(conn, tabela, df, COLUNAS[tabela], PKS[tabela])


__all__ = ["sha256", "upsert", "gravar_clean", "json"]
