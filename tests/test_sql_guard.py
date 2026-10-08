import pytest

from cristalux.agent.sql_guard import LIMITE_LINHAS, validar


def test_select_simples_ganha_limit():
    v = validar("SELECT vendedor, SUM(valor_total) AS f FROM vw_vendas GROUP BY vendedor ORDER BY f DESC")
    assert v.ok and f"LIMIT {LIMITE_LINHAS}" in v.sql


def test_limit_existente_e_mantido_quando_menor():
    v = validar("SELECT * FROM vw_vendas LIMIT 3")
    assert v.ok and "LIMIT 3" in v.sql


def test_limit_grande_e_reduzido():
    v = validar("SELECT * FROM vw_vendas LIMIT 100000")
    assert v.ok and f"LIMIT {LIMITE_LINHAS}" in v.sql


def test_cte_e_schema_permitido():
    v = validar("WITH x AS (SELECT uf, SUM(faturamento) f FROM clean.vw_faturamento_uf_ano GROUP BY uf) SELECT * FROM x")
    assert v.ok


def test_dicionario_de_dados_e_permitido():
    assert validar("SELECT * FROM meta.dicionario").ok


@pytest.mark.parametrize("sql", [
    "DROP TABLE clean.fato_venda",
    "DELETE FROM vw_vendas",
    "UPDATE vw_vendas SET valor_total = 0",
    "INSERT INTO vw_vendas VALUES (1)",
    "TRUNCATE clean.fato_venda",
    "CREATE TABLE x AS SELECT * FROM vw_vendas",
    "SELECT * INTO nova FROM vw_vendas",
    "SELECT * FROM vw_vendas; DROP TABLE clean.fato_venda",
    "SELECT * FROM vw_vendas; SELECT 1",
    "SELECT * FROM clean.fato_venda",
    "SELECT * FROM clean.dim_comprador",
    "SELECT * FROM raw.registros",
    "SELECT * FROM quarantine.registros",
    "SELECT * FROM pg_catalog.pg_user",
    "SELECT * FROM information_schema.tables",
    "SELECT pg_sleep(10)",
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT set_config('a','b',false)",
    "SELECT * FROM vw_vendas FOR UPDATE",
    "COPY clean.fato_venda TO '/tmp/x'",
    "SET ROLE postgres",
    "",
    "isto nao e sql",
])
def test_bloqueios(sql):
    v = validar(sql)
    assert not v.ok and v.motivo


def test_subconsulta_com_tabela_proibida_e_bloqueada():
    assert not validar("SELECT * FROM vw_vendas WHERE id_venda IN (SELECT id_venda FROM clean.fato_venda)").ok
