"""Atualizacao mensal sem reconstruir (spec 07, RF-50): idempotencia, upsert e novo lote.

Usa um banco descartavel (cristalux_test) e uma copia dos CSV, sem tocar na base principal.
"""
import shutil
from pathlib import Path

import pandas as pd
import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from cristalux.config import settings
from cristalux.pipeline.run import executar

ORIGEM = Path(settings.data_dir)
pytestmark = pytest.mark.db

if not (ORIGEM / "vendas.csv").exists():
    pytest.skip("dados_raw ausente", allow_module_level=True)


def _url(banco: str) -> str:
    return make_conninfo(**{**conninfo_to_dict(settings.database_url), "dbname": banco})


@pytest.fixture()
def banco_de_teste(tmp_path):
    try:
        admin = psycopg.connect(_url("postgres"), autocommit=True)
    except psycopg.Error:
        pytest.skip("Postgres indisponivel")
    admin.execute("DROP DATABASE IF EXISTS cristalux_test WITH (FORCE)")
    admin.execute("CREATE DATABASE cristalux_test")
    for f in ORIGEM.glob("*.csv"):
        shutil.copy(f, tmp_path / f.name)
    yield _url("cristalux_test"), tmp_path
    admin.execute("DROP DATABASE IF EXISTS cristalux_test WITH (FORCE)")
    admin.close()


def contar(url, tabela):
    with psycopg.connect(url) as c:
        return c.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]


def test_reprocessar_nao_duplica_e_novo_lote_faz_upsert(banco_de_teste):
    url, pasta = banco_de_teste
    executar(pasta, url=url, reports_dir=pasta / "rel")
    base = {t: contar(url, t) for t in ("clean.fato_venda", "clean.dim_comprador", "meta.ingest_log")}

    # 1. Mesmos arquivos: o hash ja foi ingerido, nada muda.
    executar(pasta, url=url, reports_dir=pasta / "rel")
    assert {t: contar(url, t) for t in base} == base

    # 2. Lote do mes seguinte: uma venda nova e uma venda antiga corrigida.
    vendas = pd.read_csv(pasta / "vendas.csv", dtype=str, keep_default_na=False)
    with psycopg.connect(url) as c:
        id_corrigido, qtd_antiga = c.execute(
            "SELECT id_venda, quantidade FROM clean.fato_venda ORDER BY id_venda LIMIT 1").fetchone()
    vendas.loc[vendas["id_venda"] == id_corrigido, "quantidade"] = str(qtd_antiga + 100)
    nova = {c: "" for c in vendas.columns} | {
        "id_venda": "VD9001", "data": "10/11/2024", "id_vendedor": "V007", "id_comprador": "C001",
        "produto": "teto solar", "categoria": "Acessorios", "quantidade": "2", "valor_unitario": "1000",
        "valor_total": "2000", "desconto": "0", "status": "concluida", "regiao": "SP"}
    vendas = pd.concat([vendas, pd.DataFrame([nova])], ignore_index=True)
    vendas.to_csv(pasta / "vendas.csv", index=False, encoding="utf-8")
    executar(pasta, url=url, reports_dir=pasta / "rel")

    assert contar(url, "clean.fato_venda") == base["clean.fato_venda"] + 1  # so a venda nova entrou
    with psycopg.connect(url) as c:
        assert c.execute("SELECT quantidade FROM clean.fato_venda WHERE id_venda = %s",
                         (id_corrigido,)).fetchone()[0] == qtd_antiga + 100  # corrigida, nao duplicada
        assert c.execute("SELECT count(*) FROM clean.fato_venda WHERE id_venda = 'VD9001'").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM meta.ingest_log WHERE arquivo = 'vendas'").fetchone()[0] == 2
    assert contar(url, "clean.dim_comprador") == base["clean.dim_comprador"]  # dimensoes intactas
