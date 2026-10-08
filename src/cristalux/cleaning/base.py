"""Estruturas e utilitarios compartilhados pelos modulos de limpeza."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from cristalux.cleaning.parsers import fold


@dataclass
class Resultado:
    """Saida de uma limpeza: tabela limpa, linhas rejeitadas e contagens."""

    clean: pd.DataFrame
    quarantine: pd.DataFrame
    stats: dict = field(default_factory=dict)

    def conferir_conservacao(self, linhas_brutas: int) -> None:
        total = len(self.clean) + len(self.quarantine)
        assert total == linhas_brutas, f"conservacao falhou: {total} != {linhas_brutas}"


def ler_csv(caminho) -> pd.DataFrame:
    """Le o CSV como texto puro, sem converter nada, com o numero da linha de origem."""
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False, encoding="utf-8")
    df.insert(0, "linha_origem", range(2, len(df) + 2))  # linha 1 e o cabecalho
    return df


def canonico_por_fold(valores: pd.Series) -> dict[str, str]:
    """Para cada valor 'dobrado' (sem acento e caixa) escolhe a melhor grafia observada.

    Prefere a que tem acento e, depois, a que nao esta toda em maiuscula ou minuscula.
    """
    melhor: dict[str, tuple] = {}
    for v in valores.dropna().unique():
        chave = fold(v)
        if not chave:
            continue
        nota = (any(ord(c) > 127 for c in v), not (v.islower() or v.isupper()))
        if chave not in melhor or nota > melhor[chave][0]:
            melhor[chave] = (nota, v)
    return {k: v for k, (_, v) in melhor.items()}


def completude(linha: dict, colunas: list[str]) -> int:
    """Quantidade de campos preenchidos entre as colunas informadas."""
    def cheio(v):
        return v not in (None, "") and not (isinstance(v, float) and pd.isna(v))

    return sum(1 for c in colunas if cheio(linha.get(c)))
