"""Comparacao entre o resultado do SQL gerado e o gabarito (execution accuracy)."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter


def _norm(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (int, float)):
        return f"{round(float(v), 2):.2f}"
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode().strip().lower()
    return re.sub(r"\s+", " ", s)


def _celulas(linha) -> Counter:
    return Counter(_norm(v) for v in (linha.values() if isinstance(linha, dict) else linha))


def _contido(esperado: Counter, obtido: Counter) -> bool:
    return all(obtido[k] >= n for k, n in esperado.items())


def comparar(gabarito: dict, colunas: list[str], linhas: list[dict]) -> tuple[bool, str]:
    """Ignora nomes de colunas e colunas extras. Linhas esperadas precisam aparecer no resultado."""
    tipo = gabarito["tipo"]
    if tipo == "vazio":
        ok = len(linhas) == 0 or all(all(v in (None, 0, 0.0) for v in l.values()) for l in linhas)
        return ok, "sem linhas ou zero" if ok else f"esperava vazio, veio {linhas[:2]}"

    # Uma linha esperada pode ser {"ou": [linhaA, linhaB]} (empate no corte do top N): qualquer alternativa vale.
    esperadas = [[_celulas(a) for a in l["ou"]] if isinstance(l, dict) else [_celulas(l)] for l in gabarito["linhas"]]
    if tipo == "escalar":
        alvo = _norm(gabarito["linhas"][0][0])
        achou = any(alvo in _celulas(l) for l in linhas)
        return achou, f"esperado {alvo}, obtido {linhas[:2]}"

    if len(linhas) != len(esperadas):
        return False, f"esperava {len(esperadas)} linhas, veio {len(linhas)}"
    obtidas = [_celulas(l) for l in linhas]
    if gabarito.get("ordenada"):
        ok = all(any(_contido(alt, o) for alt in e) for e, o in zip(esperadas, obtidas))
        return ok, "ordem/valores conferem" if ok else f"esperado {gabarito['linhas']}, obtido {linhas}"
    restantes = list(obtidas)
    for e in esperadas:
        idx = next((i for i, o in enumerate(restantes) if any(_contido(alt, o) for alt in e)), None)
        if idx is None:
            return False, f"linha esperada ausente: {e}; obtido {linhas}"
        restantes.pop(idx)
    return True, "linhas conferem"
