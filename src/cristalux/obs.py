"""Wrapper fino do Langfuse. Sem chaves configuradas, tudo vira no-op e o app segue funcionando."""
from __future__ import annotations

from typing import Any, Callable

from cristalux.config import settings


def habilitado() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def observar(name: str | None = None, as_type: str | None = None) -> Callable:
    """Decorator @observe quando o Langfuse esta configurado; senao devolve a funcao intacta."""
    def deco(fn):
        if not habilitado():
            return fn
        from langfuse import observe
        return observe(name=name or fn.__name__, as_type=as_type)(fn)
    return deco


def _cliente():
    from langfuse import get_client
    return get_client()


def atualizar_span(**kw: Any) -> None:
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


def descarregar() -> None:
    if habilitado():
        try:
            _cliente().flush()
        except Exception:
            pass


def buscar_passos(tid: str | None, tentativas: int = 6, espera: float = 1.5) -> list[dict] | None:
    """Passos do trace lidos da API do Langfuse (ingestao e assincrona, entao tenta algumas vezes)."""
    if not (habilitado() and tid):
        return None
    import time
    for _ in range(tentativas):
        try:
            tr = _cliente().api.trace.get(tid)
            observacoes = list(getattr(tr, "observations", None) or [])
            if observacoes:
                observacoes.sort(key=lambda o: str(getattr(o, "start_time", "")))
                passos = []
                for o in observacoes:
                    ini, fim = getattr(o, "start_time", None), getattr(o, "end_time", None)
                    dur = round((fim - ini).total_seconds(), 2) if ini and fim else None
                    passos.append({"nome": getattr(o, "name", ""), "tipo": str(getattr(o, "type", "")),
                                   "duracao_s": dur, "entrada": getattr(o, "input", None),
                                   "saida": getattr(o, "output", None), "nivel": str(getattr(o, "level", ""))})
                return passos
        except Exception:
            pass
        time.sleep(espera)
    return None
