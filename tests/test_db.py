"""Testes que exigem o Postgres do docker compose e os CSV em dados_raw (ficam fora do git)."""
import psycopg
import pytest

from cristalux.config import settings
from cristalux.db.setup import conectar

pytestmark = pytest.mark.db


def _disponivel() -> bool:
    try:
        with conectar() as c, c.cursor() as cur:
            cur.execute("SELECT 1 FROM clean.fato_venda LIMIT 1")
        return True
    except Exception:
        return False


if not _disponivel():
    pytest.skip("Postgres com dados carregados indisponivel", allow_module_level=True)


def contagens():
    with conectar() as c, c.cursor() as cur:
        out = {}
        for t in ("clean.fato_venda", "clean.dim_comprador", "clean.dim_vendedor", "clean.estoque", "clean.decisao",
                  "quarantine.registros", "meta.ingest_log"):
            cur.execute(f"SELECT count(*) FROM {t}")
            out[t] = cur.fetchone()[0]
        return out


def test_carga_repetida_nao_altera_contagens():
    from cristalux.pipeline.run import executar

    antes = contagens()
    executar(force=True)
    assert contagens() == antes


def agente():
    return psycopg.connect(settings.agent_database_url, autocommit=True)


@pytest.mark.parametrize("comando", [
    "DELETE FROM clean.fato_venda",
    "UPDATE clean.dim_vendedor SET nome = 'x'",
    "INSERT INTO clean.estoque (id_produto, nome_produto) VALUES ('X', 'x')",
    "DROP TABLE clean.fato_venda",
    "SELECT * FROM raw.registros",
    "SELECT * FROM quarantine.registros",
    "SELECT * FROM clean.fato_venda",
    "SELECT * FROM clean.dim_comprador",
    "CREATE TABLE clean.x (a int)",
])
def test_papel_do_agente_nao_escreve_nem_le_o_que_nao_deve(comando):
    with agente() as c, pytest.raises(psycopg.Error):
        c.execute(comando)


def test_papel_do_agente_le_as_views():
    with agente() as c:
        assert c.execute("SELECT count(*) FROM vw_vendas").fetchone()[0] > 0
        assert c.execute("SELECT count(*) FROM meta.dicionario").fetchone()[0] > 0


def test_conservacao_de_linhas_no_banco():
    with conectar() as c, c.cursor() as cur:
        cur.execute("SELECT arquivo, linhas_lidas, linhas_ok + linhas_quarentena FROM meta.ingest_log")
        for arquivo, lidas, soma in cur.fetchall():
            assert lidas == soma, arquivo


def test_vendas_sem_orfaos_e_dentro_do_periodo():
    with conectar() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM clean.fato_venda WHERE data < '2020-01-01' OR data > '2024-12-31'")
        assert cur.fetchone()[0] == 0
