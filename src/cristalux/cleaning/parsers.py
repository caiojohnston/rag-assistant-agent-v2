"""Funcoes puras de parse e normalizacao de campos.

Cada funcao recebe o texto bruto da celula e devolve o valor normalizado ou None.
Quando ha um motivo de rejeicao a funcao devolve (valor, motivo). Nada aqui toca
em arquivos ou banco, o que permite testar com os casos reais dos CSV.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

# Textos que representam "sem valor" nos arquivos.
NULOS = {"", "n/a", "na", "null", "none", "nan", "desconhecido", "-", "--"}


def fold(texto: str | None) -> str:
    """Minusculo, sem acento, espacos colapsados."""
    if texto is None:
        return ""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def limpar(texto: str | None) -> str | None:
    """Remove espacos extras e converte marcadores de nulo em None."""
    if texto is None:
        return None
    t = re.sub(r"\s+", " ", str(texto)).strip()
    return None if t.lower() in NULOS else t


# ---------------------------------------------------------------- datas

_RE_ISO = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")
_RE_BR = re.compile(r"^(\d{1,2})([-/.])(\d{1,2})\2(\d{2}|\d{4})$")


def parse_data(texto: str | None) -> tuple[date | None, str | None, bool]:
    """Devolve (data, motivo_de_rejeicao, ambigua).

    Formatos aceitos: aaaa-mm-dd, aaaa/mm/dd, dd/mm/aaaa, dd-mm-aaaa, dd.mm.aaaa e
    as variantes com ano de dois digitos. Convencao brasileira (dia primeiro).
    Motivos: vazia, formato_desconhecido, inexistente.
    """
    t = limpar(texto)
    if t is None:
        return None, "vazia", False
    m = _RE_ISO.match(t)
    if m:
        ano, mes, dia = (int(x) for x in m.groups())
        ambigua = False
    else:
        m = _RE_BR.match(t)
        if not m:
            return None, "formato_desconhecido", False
        dia, sep, mes, ano_txt = m.groups()
        dia, mes = int(dia), int(mes)
        ano = int(ano_txt) + (2000 if len(ano_txt) == 2 else 0)
        # Com hifen o arquivo mistura dd-mm e mm-dd; com barra e ponto ha evidencia de dd/mm.
        ambigua = sep == "-" and dia <= 12 and mes <= 12 and dia != mes
    try:
        return date(ano, mes, dia), None, ambigua
    except ValueError:
        return None, "inexistente", False


# ---------------------------------------------------------------- numeros

_RE_MILHAR = re.compile(r"^\d{1,3}(\.\d{3})+$")


def parse_numero(texto: str | None) -> float | None:
    """Converte 'R$ 1.424,08', '1424.08', 'R$ 80.000', '3,5%' e '3.5' em float."""
    t = limpar(texto)
    if t is None:
        return None
    t = t.replace("R$", "").replace("%", "").replace(" ", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif _RE_MILHAR.match(t):
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def parse_inteiro(texto: str | None) -> int | None:
    n = parse_numero(texto)
    if n is None or n != int(n):
        return None
    return int(n)


def parse_desconto(texto: str | None) -> tuple[float | None, str | None]:
    """Devolve (fracao, flag). 5, 5% e 0.05 viram 0.05. 'Sim' e vazio viram None.

    flag: 'desconto_indefinido' (Sim, vazio ou N/A) ou None.
    """
    t = limpar(texto)
    if t is None:
        return None, "desconto_indefinido"
    f = fold(t)
    if f in {"nao", "nenhum", "sem desconto"}:
        return 0.0, None
    if f in {"sim", "s"}:
        return None, "desconto_indefinido"
    n = parse_numero(t)
    if n is None:
        return None, "desconto_indefinido"
    if n < 0:
        return None, "desconto_indefinido"
    # Valores de 0 a 1 sem simbolo de porcentagem ja sao fracao; o resto e percentual.
    frac = n if (n <= 1 and "%" not in t) else n / 100
    return round(frac, 4), None


# ---------------------------------------------------------------- categorias

_STATUS_VENDA = {
    "concluida": "concluida", "concluido": "concluida", "fechado": "concluida", "fechada": "concluida",
    "cancelada": "cancelada", "cancelado": "cancelada",
    "devolvida": "devolvida", "devolvido": "devolvida",
    "pendente": "pendente", "em aberto": "pendente",
}


def parse_status_venda(texto: str | None) -> str | None:
    return _STATUS_VENDA.get(fold(limpar(texto)))


_CATEGORIAS = {"reparos": "Reparos", "vidros": "Vidros", "acessorios": "Acessórios", "sensores": "Sensores"}


def parse_categoria(texto: str | None) -> str | None:
    return _CATEGORIAS.get(fold(limpar(texto)))


# Nome canonico do produto (RN-18b).
_PRODUTOS = {
    "kit de reparo": "Kit de Reparo", "kit reparo": "Kit de Reparo", "kit reparo trinca": "Kit de Reparo",
    "moldura": "Moldura de Parabrisas", "moldura parabrisas": "Moldura de Parabrisas",
    "parabrisas diant.": "Parabrisas Dianteiro", "parabrisas dianteiro": "Parabrisas Dianteiro",
    "pelicula": "Película Protetora", "pelicula protetora": "Película Protetora",
    "sensor chuva": "Sensor de Chuva", "sensor de chuva": "Sensor de Chuva",
    "teto solar": "Teto Solar",
    "vid. lateral": "Vidro Lateral", "vidro lateral": "Vidro Lateral",
    "vidro lateral dir.": "Vidro Lateral Direito", "vidro lateral esq.": "Vidro Lateral Esquerdo",
    "vid. traseiro": "Vidro Traseiro", "vidro traseiro": "Vidro Traseiro",
    "vidro traseiro completo": "Vidro Traseiro",
}


def parse_produto(texto: str | None) -> str | None:
    t = limpar(texto)
    if t is None:
        return None
    return _PRODUTOS.get(fold(t), t.title())


# ---------------------------------------------------------------- regiao / UF

_UF_NOMES = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA",
    "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG", "para": "PA",
    "paraiba": "PB", "parana": "PR", "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ",
    "rio grande do norte": "RN", "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR",
    "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE", "tocantins": "TO",
}
_UF_SIGLAS = set(_UF_NOMES.values())
_UF_APELIDOS = {
    "s.paulo": "SP", "m.gerais": "MG",
    # cidades que aparecem na coluna de regiao
    "salvador": "BA", "florianopolis": "SC", "porto alegre": "RS", "curitiba": "PR",
    "manaus": "AM", "belo horizonte": "MG", "goiania": "GO", "londrina": "PR", "joinville": "SC",
}


def parse_uf(texto: str | None) -> str | None:
    """'SP - Capital', 'S.Paulo', 'sao paulo' e 'Salvador' viram a sigla da UF."""
    t = limpar(texto)
    if t is None:
        return None
    f = fold(t)
    if f in _UF_APELIDOS:
        return _UF_APELIDOS[f]
    if f in _UF_NOMES:
        return _UF_NOMES[f]
    if f.upper() in _UF_SIGLAS:
        return f.upper()
    # 'SP - Capital', 'PR-Curitiba', 'RS-Sul': a sigla vem antes do separador.
    prefixo = re.split(r"\s*-\s*", f, maxsplit=1)[0]
    if prefixo.upper() in _UF_SIGLAS:
        return prefixo.upper()
    return None


# ---------------------------------------------------------------- contato e documentos

def so_digitos(texto: str | None) -> str | None:
    t = limpar(texto)
    if t is None:
        return None
    d = re.sub(r"\D", "", t)
    return d or None


def parse_telefone(texto: str | None) -> str | None:
    """Mantem so os digitos; aceita 10 (fixo) ou 11 (celular) digitos."""
    d = so_digitos(texto)
    return d if d and len(d) in (10, 11) else None


def formatar_telefone(digitos: str | None) -> str | None:
    if not digitos:
        return None
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"


def parse_email(texto: str | None) -> str | None:
    t = limpar(texto)
    if t is None or "@" not in t:
        return None
    return t.lower()


def cnpj_valido(cnpj: str | None) -> bool:
    d = so_digitos(cnpj)
    if not d or len(d) != 14 or len(set(d)) == 1:
        return False

    def dv(base: str, pesos: list[int]) -> str:
        r = sum(int(a) * b for a, b in zip(base, pesos)) % 11
        return "0" if r < 2 else str(11 - r)

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6] + p1
    d1 = dv(d[:12], p1)
    d2 = dv(d[:12] + d1, p2)
    return d[12:] == d1 + d2


def formatar_cnpj(digitos: str | None) -> str | None:
    if not digitos or len(digitos) != 14:
        return digitos
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"


def parse_status_cadastro(texto: str | None) -> str | None:
    f = fold(limpar(texto))
    return f if f in {"ativo", "inativo"} else None


def titulo(texto: str | None) -> str | None:
    """Capitaliza nomes ('manaus' -> 'Manaus', 'REPAROS' -> 'Reparos') sem quebrar preposicoes."""
    t = limpar(texto)
    if t is None:
        return None
    menores = {"de", "da", "do", "das", "dos", "e"}
    palavras = t.lower().split(" ")
    return " ".join(p if (i and p in menores) else p.capitalize() for i, p in enumerate(palavras))
