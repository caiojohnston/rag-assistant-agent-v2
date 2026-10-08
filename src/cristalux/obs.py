"""Instrumentacao com Langfuse (SDK v4) seguindo as boas praticas da documentacao.

- Cada chamada ao Gemini e uma `generation` com nome estavel, modelo, tokens (inclusive de raciocinio), entrada e
  saida no formato de mensagens e o resumo do raciocinio. A integracao OpenInference foi testada e descartada: gerava
  nomes genericos, despejava cabecalhos HTTP na saida e nao capturava o raciocinio.
- Agente, tools, retriever e guardrails sao observacoes manuais, com tipo correto e nomes estaveis (verbo primeiro).
- Entrada e saida de cada observacao sao definidas explicitamente, sem despejar argumentos de funcao.
- Dados pessoais sao mascarados antes do envio (`mask`).
- Sem chaves configuradas tudo vira no-op e o app segue funcionando.
"""
from __future__ import annotations

import contextlib
import os
import re
from typing import Any, Callable

from cristalux.config import settings

_iniciado = False

_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_RE_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_RE_TELEFONE = re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b")


def mascarar(dado: Any) -> Any:
    """Troca e-mail, CNPJ e telefone por marcadores, em qualquer estrutura aninhada."""
    if isinstance(dado, str):
        dado = _RE_EMAIL.sub("[email]", dado)
        dado = _RE_CNPJ.sub("[cnpj]", dado)
        return _RE_TELEFONE.sub("[telefone]", dado)
    if isinstance(dado, dict):
        return {k: mascarar(v) for k, v in dado.items()}
    if isinstance(dado, (list, tuple)):
        return [mascarar(v) for v in dado]
    return dado


def _versao() -> str | None:
    """APP_VERSION (Docker/Railway) ou o hash curto do git, para saber qual codigo gerou cada trace."""
    if os.getenv("APP_VERSION"):
        return os.environ["APP_VERSION"]
    if os.getenv("RAILWAY_GIT_COMMIT_SHA"):  # injetada pelo Railway em cada deploy
        return os.environ["RAILWAY_GIT_COMMIT_SHA"][:7]
    try:
        import subprocess
        from cristalux.config import ROOT
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              timeout=3).stdout.strip() or None
    except Exception:
        return None


def habilitado() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def iniciar() -> None:
    """Cria o cliente Langfuse e ativa a integracao do Gemini. Idempotente; deve rodar apos o carregamento do .env."""
    global _iniciado
    if _iniciado or not habilitado():
        return
    _iniciado = True
    from langfuse import Langfuse

    Langfuse(
        public_key=settings.langfuse_public_key, secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_host,
        environment=os.getenv("LANGFUSE_TRACING_ENVIRONMENT", "development"),
        release=_versao(),
        mask=lambda data, **_: mascarar(data),
    )


def observar(name: str | None = None, as_type: str | None = None) -> Callable:
    """Decorator @observe sem captura automatica de argumentos (entrada e saida sao definidas a mao)."""
    def deco(fn):
        if not habilitado():
            return fn
        iniciar()
        from langfuse import observe
        return observe(name=name or fn.__name__, as_type=as_type, capture_input=False, capture_output=False)(fn)
    return deco


def _cliente():
    from langfuse import get_client
    return get_client()


def atualizar(**kw: Any) -> None:
    """Atualiza a observacao ativa (input, output, metadata, level, status_message...)."""
    if habilitado():
        try:
            _cliente().update_current_span(**kw)
        except Exception:
            pass


def atualizar_geracao(**kw: Any) -> None:
    if habilitado():
        try:
            _cliente().update_current_generation(**kw)
        except Exception:
            pass


@contextlib.contextmanager
def contexto(session_id: str | None = None, tags: list[str] | None = None, metadata: dict | None = None,
             user_id: str | None = None, version: str | None = None):
    """Propaga session_id, tags e metadata para todas as observacoes criadas dentro do bloco."""
    if not habilitado():
        yield
        return
    iniciar()
    from langfuse import propagate_attributes

    meta = {k: str(v) for k, v in (metadata or {}).items() if v is not None}
    with propagate_attributes(session_id=session_id, tags=tags, metadata=meta or None, user_id=user_id, version=version):
        yield


@contextlib.contextmanager
def geracao(name: str, model: str, input: Any = None, model_parameters: dict | None = None):
    """`generation` do Langfuse. Quem chama preenche output, usage_details e metadata com .update()."""
    if not habilitado():
        class _Nulo:
            def update(self, **_): ...
        yield _Nulo()
        return
    iniciar()
    with _cliente().start_as_current_observation(name=name, as_type="generation", model=model, input=input,
                                                 model_parameters=model_parameters) as g:
        yield g


@contextlib.contextmanager
def observacao(name: str, as_type: str = "span", input: Any = None, **kw: Any):
    """Context manager para um passo sem funcao propria (por exemplo, a validacao de SQL)."""
    if not habilitado():
        class _Nulo:
            def update(self, **_): ...
        yield _Nulo()
        return
    iniciar()
    with _cliente().start_as_current_observation(name=name, as_type=as_type, input=input, **kw) as o:
        yield o


def trace_id() -> str | None:
    if not habilitado():
        return None
    try:
        return _cliente().get_current_trace_id()
    except Exception:
        return None


def trace_url(tid: str | None) -> str | None:
    if not (habilitado() and tid):
        return None
    try:
        return _cliente().get_trace_url(trace_id=tid)
    except Exception:
        return None


def pontuar(tid: str | None, nome: str, valor: float | str | bool, comentario: str | None = None,
            tipo: str | None = None) -> None:
    """Registra um score no trace (feedback do usuario ou resultado de avaliacao)."""
    if not (habilitado() and tid):
        return
    try:
        _cliente().create_score(trace_id=tid, name=nome, value=valor, comment=comentario, data_type=tipo)
    except Exception:
        pass


def descarregar() -> None:
    if habilitado():
        try:
            _cliente().flush()
        except Exception:
            pass


def buscar_passos(tid: str | None, tentativas: int = 6, espera: float = 1.5) -> list[dict] | None:
    """Passos do trace lidos da API do Langfuse (a ingestao e assincrona, entao tenta algumas vezes)."""
    if not (habilitado() and tid):
        return None
    import time
    for _ in range(tentativas):
        try:
            # A API v1 de traces nao existe para organizacoes novas; a v2 de observacoes e a oficial.
            r = _cliente().api.observations.get_many(trace_id=tid, fields="core,basic,time,io,metadata,model,usage",
                                                     limit=100)
            observacoes = sorted(r.data, key=lambda o: str(getattr(o, "start_time", "")))
            if observacoes:
                por_id = {o.id: o for o in observacoes}

                def nivel(o):
                    n, p = 0, o.parent_observation_id
                    while p and p in por_id:
                        n, p = n + 1, por_id[p].parent_observation_id
                    return n

                return [{"nome": o.name, "tipo": str(o.type), "duracao_s": round(o.latency, 2) if o.latency else None,
                         "entrada": o.input, "saida": o.output, "nivel": str(o.level), "profundidade": nivel(o),
                         "modelo": o.model, "uso": getattr(o, "usage_details", None)} for o in observacoes]
        except Exception:
            pass
        time.sleep(espera)
    return None
