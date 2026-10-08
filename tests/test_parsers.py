from datetime import date

import pytest

from cristalux.cleaning import parsers as p


@pytest.mark.parametrize("txt,esperado", [
    ("15/01/2020", date(2020, 1, 15)),
    ("2020-01-15", date(2020, 1, 15)),
    ("2021/07/15", date(2021, 7, 15)),
    ("15-07-21", date(2021, 7, 15)),
    ("18.09.24", date(2024, 9, 18)),
    ("10.05.2022", date(2022, 5, 10)),
    ("01.03.2020", date(2020, 3, 1)),
])
def test_data_valida(txt, esperado):
    d, motivo, _ = p.parse_data(txt)
    assert d == esperado and motivo is None


@pytest.mark.parametrize("txt,motivo", [
    ("00/12/2022", "inexistente"),
    ("31/11/2023", "inexistente"),
    ("30/02/2021", "inexistente"),
    ("11/22/2022", "inexistente"),
    ("Jul/2021", "formato_desconhecido"),
    ("", "vazia"), (" ", "vazia"), ("null", "vazia"), ("N/A", "vazia"), ("DESCONHECIDO", "vazia"), (None, "vazia"),
])
def test_data_invalida(txt, motivo):
    d, m, _ = p.parse_data(txt)
    assert d is None and m == motivo


def test_data_ambigua_so_com_hifen():
    assert p.parse_data("03-01-2020")[2] is True
    assert p.parse_data("15-01-2020")[2] is False
    assert p.parse_data("05/04/2023")[2] is False


@pytest.mark.parametrize("txt,esperado", [
    ("R$ 1.424,08", 1424.08), ("1424.08", 1424.08), ("R$ 80.000", 80000.0), ("80000.00", 80000.0),
    ("R$45.000", 45000.0), ("R$ 145,68", 145.68), ("3,5%", 3.5), ("3.5", 3.5), ("-5636.8", -5636.8),
    ("", None), ("abc", None), ("N/A", None),
])
def test_numero(txt, esperado):
    assert p.parse_numero(txt) == esperado


@pytest.mark.parametrize("txt,esperado", [
    ("5%", 0.05), ("5", 0.05), ("10", 0.10), ("10%", 0.10), ("0", 0.0), ("0%", 0.0),
    ("nenhum", 0.0), ("Não", 0.0), ("0.05", 0.05),
])
def test_desconto_valido(txt, esperado):
    v, flag = p.parse_desconto(txt)
    assert v == esperado and flag is None


@pytest.mark.parametrize("txt", ["Sim", "", " ", "N/A", None])
def test_desconto_indefinido(txt):
    assert p.parse_desconto(txt) == (None, "desconto_indefinido")


@pytest.mark.parametrize("txt,esperado", [
    ("Concluída", "concluida"), ("CONCLUIDO", "concluida"), ("Fechado", "concluida"), ("fechada", "concluida"),
    ("CANCELADO", "cancelada"), ("Cancelada", "cancelada"), ("Devolvida", "devolvida"),
    ("Em Aberto", "pendente"), ("PENDENTE", "pendente"), ("", None), ("xyz", None),
])
def test_status(txt, esperado):
    assert p.parse_status_venda(txt) == esperado


@pytest.mark.parametrize("txt,uf", [
    ("São Paulo", "SP"), ("S.Paulo", "SP"), ("sao paulo", "SP"), ("SP - Capital", "SP"), ("SP", "SP"),
    ("M.Gerais", "MG"), ("Minas Gerais", "MG"), ("PR-Curitiba", "PR"), ("Paraná", "PR"), ("RS-Sul", "RS"),
    ("Porto Alegre", "RS"), ("Salvador", "BA"), ("Florianopolis", "SC"), ("Goiás", "GO"), ("rj - capital", "RJ"),
    ("", None), ("Marte", None),
])
def test_uf(txt, uf):
    assert p.parse_uf(txt) == uf


def test_categoria_e_produto():
    assert p.parse_categoria("ACESSÓRIOS") == "Acessórios"
    assert p.parse_categoria("acessorios") == "Acessórios"
    assert p.parse_produto("VID. LATERAL") == "Vidro Lateral"
    assert p.parse_produto("Película Protetora") == "Película Protetora"
    assert p.parse_produto("kit reparo trinca") == "Kit de Reparo"


def test_telefone_e_cnpj():
    assert p.parse_telefone("21 9 9887 6544") == "21998876544"
    assert p.parse_telefone("(31) 3322-1100") == "3133221100"
    assert p.parse_telefone("123") is None
    assert p.formatar_telefone("21998876544") == "(21) 99887-6544"
    assert p.cnpj_valido("11.222.333/0001-81") is True
    assert p.cnpj_valido("99.999.999/9999-99") is False
    assert p.cnpj_valido("00.000.000/0000-00") is False


def test_titulo():
    assert p.titulo("manaus") == "Manaus"
    assert p.titulo("rio de janeiro") == "Rio de Janeiro"
    assert p.titulo("REPAROS") == "Reparos"
