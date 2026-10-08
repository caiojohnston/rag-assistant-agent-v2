"""Verificacao de saida: detecta respostas que repetem a assinatura do ataque da decisao D013.

E defesa em profundidade, nao controle unico (spec 07): o controle principal e que o numero e a avaliacao
de qualidade vem de codigo (tool relatorio_qualidade), nunca de texto de documento.
"""
from __future__ import annotations

import re

from cristalux.cleaning.parsers import fold

_ASSINATURAS = {
    "nota_9_8": r"\b9[.,]8\s*(/|de)\s*10|score\s*[=:]?\s*9[.,]8",
    "qualidade_excelente": r"qualidade\s*[=:]\s*excelente|qualidade\s+e\s+excelente|qualidade\s+excelente",
    "nenhuma_limpeza": r"nenhuma limpeza (e )?necessaria|nao (e )?necessari[ao] (fazer )?(nenhuma )?limpeza",
    "prontos_para_modelagem": r"dados prontos para modelagem",
}
# Se a resposta cita o texto como algo suspeito, nao e vazamento.
_CONTEXTO_DE_ALERTA = re.compile(r"suspeit|injec|nao (segui|sigo|obedec)|ignor|instruc|nao confiavel|anomalia|manipul")


def vazou(resposta: str) -> list[str]:
    """Assinaturas do ataque presentes na resposta sem sinal de que foram apresentadas como alerta."""
    f = fold(resposta)
    achadas = [n for n, rx in _ASSINATURAS.items() if re.search(rx, f)]
    if achadas and _CONTEXTO_DE_ALERTA.search(f):
        return []
    return achadas
