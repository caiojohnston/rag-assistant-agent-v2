"""Embeddings. Tres backends: Gemini (padrao com chave), local multilingue (fastembed) e hash (testes)."""
from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Protocol

from cristalux import obs
from cristalux.config import settings


class Embedder(Protocol):
    nome: str

    def embed_documents(self, textos: list[str]) -> list[list[float]]: ...
    def embed_query(self, texto: str) -> list[float]: ...


class GeminiEmbedder:
    nome = "gemini"

    def __init__(self, modelo: str | None = None):
        self.modelo = modelo or settings.gemini_embedding_model

    def _embed(self, textos: list[str], task: str) -> list[list[float]]:
        from google.genai import types

        from cristalux.llm import cliente, com_repeticao

        saida: list[list[float]] = []
        for i in range(0, len(textos), 50):
            lote = textos[i:i + 50]
            r = com_repeticao(lambda: cliente().models.embed_content(
                model=self.modelo, contents=lote, config=types.EmbedContentConfig(task_type=task)))
            saida += [e.values for e in r.embeddings]
        return saida

    def embed_documents(self, textos):
        with obs.observacao("embed-documents", "embedding", input={"quantidade": len(textos)}, model=self.modelo):
            return self._embed(textos, "RETRIEVAL_DOCUMENT")

    def embed_query(self, texto):
        with obs.observacao("embed-query", "embedding", input=texto, model=self.modelo) as span:
            vetor = self._embed([texto], "RETRIEVAL_QUERY")[0]
            span.update(output={"dimensoes": len(vetor)})
            return vetor


class LocalEmbedder:
    """Modelo multilingue ONNX via fastembed, roda sem rede depois do primeiro download."""

    nome = "local"

    def __init__(self, modelo: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        from fastembed import TextEmbedding

        self.modelo = modelo
        self._m = TextEmbedding(model_name=modelo)

    def embed_documents(self, textos):
        return [v.tolist() for v in self._m.embed(textos)]

    def embed_query(self, texto):
        return self.embed_documents([texto])[0]


class HashEmbedder:
    """Saco de palavras com hash. Deterministico e sem rede: so para testes unitarios."""

    nome = "hash"
    DIM = 256

    def _vec(self, texto: str) -> list[float]:
        v = [0.0] * self.DIM
        for tok in re.findall(r"\w+", texto.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.DIM] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, textos):
        return [self._vec(t) for t in textos]

    def embed_query(self, texto):
        return self._vec(texto)


class ComFallback:
    """Gemini como primario; se a cota diaria de embeddings acabar, usa o modelo local pelo resto do processo.

    `nome` muda para "local" apos a troca, e quem usa (retriever, indexador) escolhe a colecao do Chroma e o
    threshold pelo nome atual. As duas colecoes sao mantidas pelo indexador (rag/index.py).
    """

    def __init__(self, primario, secundario=None):
        self.primario = primario
        self._secundario = secundario
        self._trocou = False

    @property
    def nome(self) -> str:
        return self._secundario_nome() if self._trocou else self.primario.nome

    def usar_secundario(self) -> None:
        """Forca o modelo de reserva (ex.: a colecao do primario esta vazia)."""
        self._trocou = True

    def _secundario_nome(self) -> str:
        return self._get_secundario().nome

    def _get_secundario(self):
        if self._secundario is None:
            self._secundario = LocalEmbedder()
        return self._secundario

    def _chamar(self, metodo: str, arg):
        from cristalux.llm import CotaDiariaEsgotada

        if not self._trocou:
            try:
                return getattr(self.primario, metodo)(arg)
            except CotaDiariaEsgotada:
                self._trocou = True
                print("aviso: cota de embeddings do Gemini esgotada; usando o modelo local")
        return getattr(self._get_secundario(), metodo)(arg)

    def embed_documents(self, textos):
        return self._chamar("embed_documents", textos)

    def embed_query(self, texto):
        return self._chamar("embed_query", texto)


# Threshold de similaridade (cosseno) por backend. Calibrados em reports/experimentos.md (varredura de threshold, spec 06).
THRESHOLD_PADRAO = {"gemini": 0.70, "local": 0.50, "hash": 0.2}


def backend_padrao() -> str:
    if settings.embedding_backend:
        return settings.embedding_backend
    return "gemini" if settings.gemini_api_key else "local"


def get_embedder(backend: str | None = None) -> Embedder:
    backend = backend or backend_padrao()
    if backend == "gemini":
        # EMBEDDING_FALLBACK=off desliga a troca automatica para o modelo local quando a cota acaba.
        return GeminiEmbedder() if os.getenv("EMBEDDING_FALLBACK", "local") == "off" else ComFallback(GeminiEmbedder())
    if backend == "local":
        return LocalEmbedder()
    if backend == "hash":
        return HashEmbedder()
    raise ValueError(f"backend de embedding desconhecido: {backend}")
