"""Montagem dos chunks (spec 03). Cada decisao e um chunk; documentos longos sao divididos por paragrafo."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

MAX_TOKENS = 300  # estimativa: ~1,5 token por palavra em portugues


@dataclass
class Chunk:
    fonte: str
    id: str
    texto: str
    metadata: dict = field(default_factory=dict)

    @property
    def chunk_id(self) -> str:
        """ID deterministico: o mesmo conteudo sempre gera o mesmo id (upsert incremental)."""
        h = hashlib.sha1(f"{self.fonte}|{self.id}|{self.texto}".encode("utf-8")).hexdigest()[:20]
        return f"{self.fonte}-{self.id}-{h}"


def estimar_tokens(texto: str) -> int:
    return int(len(texto.split()) * 1.5)


def dividir(texto: str, limite: int = MAX_TOKENS) -> list[str]:
    """Divide por paragrafo (e, se preciso, por frase) respeitando o limite."""
    if estimar_tokens(texto) <= limite:
        return [texto]
    partes, atual = [], ""
    for par in re.split(r"\n+", texto):
        for frase in re.split(r"(?<=[.;:])\s+", par):
            if atual and estimar_tokens(atual + " " + frase) > limite:
                partes.append(atual.strip())
                atual = ""
            atual += (" " if atual else "") + frase
    if atual.strip():
        partes.append(atual.strip())
    return partes


def chunk_decisao(d: dict) -> Chunk:
    data = d["data"]
    data_txt = data.strftime("%d/%m/%Y") if hasattr(data, "strftime") else str(data or "sem data")
    ano = data.year if hasattr(data, "year") else None
    texto = (f"Decisao {d['id_decisao']}, data {data_txt}, tipo {d['tipo']}, responsavel {d['responsavel']}, "
             f"impacto {d['impacto']}. Descricao: {d['descricao']}. Resultado: {d['resultado']}. "
             f"Observacoes: {d['observacoes']}")
    meta = {"fonte": "decisao", "id": d["id_decisao"], "tipo": d["tipo"] or "", "responsavel": d["responsavel"] or "",
            "impacto": d["impacto"] or "", "ano": ano or 0,
            "confianca": "nao_confiavel" if d.get("suspeita_injection") else "alta"}
    return Chunk("decisao", d["id_decisao"], texto, meta)


def chunks_dicionario(views: dict) -> list[Chunk]:
    out = []
    for view, info in views.items():
        cols = "; ".join(f"{c}: {desc}" for c, desc in info["colunas"].items())
        texto = f"Dicionario de dados da view {view}. {info['descricao']} Colunas: {cols}"
        for i, parte in enumerate(dividir(texto)):
            out.append(Chunk("dicionario", f"{view}#{i}", parte, {"fonte": "dicionario", "id": view, "confianca": "alta"}))
    return out


def chunks_qualidade(relatorio: dict) -> list[Chunk]:
    out = []
    for a in relatorio["arquivos"]:
        linhas = [f"Qualidade do arquivo {a['arquivo']}: {a['linhas_brutas']} linhas brutas, "
                  f"{a['linhas_limpas']} limpas, {a['linhas_quarentena']} em quarentena."]
        for pr in a["problemas"]:
            pct = f", {pr['percentual']}%" if pr["percentual"] is not None else ""
            linhas.append(f"Problema {pr['tipo']}: {pr['volume']} ocorrencias{pct}. Impacto: {pr['impacto']}")
        for i, parte in enumerate(dividir("\n".join(linhas))):
            out.append(Chunk("qualidade", f"{a['arquivo']}#{i}", parte,
                             {"fonte": "qualidade", "id": a["arquivo"], "confianca": "alta"}))
    return out


_RE_RN = re.compile(r"^[|\-\s]*\**(RN-\d+[a-z]?)\b")


def chunks_regras(markdown: str) -> list[Chunk]:
    """Uma regra de limpeza (RN-xx) por chunk, lida da spec 01."""
    out = []
    for linha in markdown.splitlines():
        m = _RE_RN.match(linha)
        if m:
            texto = "Regra de limpeza " + re.sub(r"\s*\|\s*", " ", linha.strip("|- ")).strip()
            out.append(Chunk("regra", m.group(1), texto, {"fonte": "regra", "id": m.group(1), "confianca": "alta"}))
    return out
