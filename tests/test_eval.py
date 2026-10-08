from pathlib import Path

import pytest

from cristalux.config import settings
from cristalux.eval.comparar import comparar
from cristalux.eval.run import numeros_fieis


def test_escalar_ignora_nome_da_coluna_e_arredonda():
    g = {"tipo": "escalar", "linhas": [[203405.17]]}
    assert comparar(g, ["x"], [{"faturamento": 203405.1700001}])[0]
    assert not comparar(g, ["x"], [{"faturamento": 203405.9}])[0]


def test_conjunto_ignora_ordem_e_colunas_extras():
    g = {"tipo": "conjunto", "linhas": [["MG"], ["RJ"]]}
    assert comparar(g, [], [{"uf": "RJ", "fat": 1}, {"uf": "MG", "fat": 2}])[0]
    assert not comparar(g, [], [{"uf": "RJ"}])[0]
    assert not comparar(g, [], [{"uf": "RJ"}, {"uf": "SP"}])[0]


def test_tabela_ordenada_exige_ordem():
    g = {"tipo": "tabela", "ordenada": True, "linhas": [["A", 10.0], ["B", 5.0]]}
    assert comparar(g, [], [{"c": "A", "v": 10}, {"c": "B", "v": 5}])[0]
    assert not comparar(g, [], [{"c": "B", "v": 5}, {"c": "A", "v": 10}])[0]


def test_acentos_e_caixa_nao_importam():
    g = {"tipo": "conjunto", "linhas": [["Vidro Traseiro Sedan"]]}
    assert comparar(g, [], [{"n": "vidro traseiro sedan"}])[0]
    assert comparar({"tipo": "conjunto", "linhas": [["Película"]]}, [], [{"n": "pelicula"}])[0]


def test_vazio_aceita_sem_linhas_ou_zero():
    assert comparar({"tipo": "vazio"}, [], [])[0]
    assert comparar({"tipo": "vazio"}, [], [{"soma": None}])[0]
    assert not comparar({"tipo": "vazio"}, [], [{"soma": 10}])[0]


def test_numeros_fieis():
    tabela = [{"colunas": ["f"], "linhas": [{"f": 203405.17}], "total_linhas": 1}]
    assert numeros_fieis("O faturamento de 2022 foi R$ 203.405,17.", tabela)[0]
    assert numeros_fieis("Foram 203 mil em 2022.", tabela)[0]
    ok, soltos = numeros_fieis("O faturamento foi de R$ 999.999,00.", tabela)
    assert not ok and 999999.0 in soltos


@pytest.mark.skipif(not (Path(settings.data_dir) / "vendas.csv").exists(), reason="dados_raw ausente")
def test_gabarito_do_conjunto_b_calcula():
    from cristalux.eval import conjunto_b

    base = conjunto_b.carregar_base()
    saidas = {c.id: c.gabarito(base) for c in conjunto_b.CASOS}
    assert saidas["B04"]["linhas"] == [["MG"], ["RJ"], ["RS"]]
    assert saidas["B11"]["tipo"] == "vazio"
    assert len(saidas["B02"]["linhas"]) == 3


def test_empate_no_corte_do_top_n_aceita_qualquer_empatado():
    g = {"tipo": "tabela", "ordenada": True, "linhas": [["A", 59.0], {"ou": [["B", 43.0], ["C", 43.0]]}]}
    assert comparar(g, [], [{"n": "A", "v": 59}, {"n": "C", "v": 43}])[0]
    assert comparar(g, [], [{"n": "A", "v": 59}, {"n": "B", "v": 43}])[0]
    assert not comparar(g, [], [{"n": "A", "v": 59}, {"n": "D", "v": 40}])[0]


def test_topn_marca_empate_no_ultimo_lugar():
    import pandas as pd

    from cristalux.eval.conjunto_b import _topn

    g = _topn(pd.Series({"A": 59, "B": 43, "C": 43, "D": 10}), 3)
    assert g["linhas"][0] == ["A", 59.0] and "ou" in g["linhas"][2]
    sem_empate = _topn(pd.Series({"A": 59, "B": 43, "C": 40}), 3)
    assert all(isinstance(l, list) for l in sem_empate["linhas"])
