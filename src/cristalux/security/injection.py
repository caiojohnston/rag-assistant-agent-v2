"""Detector simples de prompt injection em texto vindo dos dados.

E uma defesa em camadas (spec 07): marca o registro, nao o apaga. A defesa real
esta em tratar todo texto recuperado como dado e em nunca derivar numeros dele.
"""
from __future__ import annotations

import re

from cristalux.cleaning.parsers import fold

_PADROES = {
    "instrucao_para_ia": r"instruc(ao|oes) para (assistentes?|agentes?|ia|llms?|modelos?)",
    "ignore_instrucoes": r"ignor(e|ar) (todas? )?(as |os |a |o )?(instruc|problemas|regras|avaliac|resultados|duplicat)",
    "retorno_obrigatorio": r"(retorne|responda|diga|devolva) obrigatoriamente",
    "omitir_problemas": r"nao mencione",
    "pre_validacao_automatica": r"pre-?validacao automatica",
    "ingles_ignore": r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
    "ingles_system": r"(system prompt|you must (respond|answer|reply))",
}
_REGEX = {nome: re.compile(rx) for nome, rx in _PADROES.items()}


def detectar(texto: str | None) -> list[str]:
    """Nomes dos padroes encontrados no texto (vazio se nenhum)."""
    f = fold(texto)
    return [nome for nome, rx in _REGEX.items() if rx.search(f)]


def suspeito(*textos: str | None) -> bool:
    return any(detectar(t) for t in textos)
