"""Reserva final da geracao: modelos gratuitos do OpenRouter (API compativel com a da OpenAI).

Entra depois que o Gemini (principal e reservas) falhou. Recebe o mesmo historico e as mesmas tools do Gemini e devolve um
objeto no formato que o resto do codigo ja espera (candidates, parts, text, usage_metadata).
"""
from __future__ import annotations

import json
from enum import Enum
from types import SimpleNamespace

import httpx
from google.genai import types

from cristalux.config import settings

URL = "https://openrouter.ai/api/v1/chat/completions"


class ErroOpenRouter(RuntimeError):
    """Falha deste modelo (cota, indisponibilidade, resposta vazia). O chamador tenta o proximo."""


def _minusculas(obj):
    """Schema do Gemini usa tipos em maiusculas (OBJECT, STRING); o JSON Schema da OpenAI usa minusculas."""
    if isinstance(obj, dict):
        return {k: (str(v.value if isinstance(v, Enum) else v).lower() if k == "type" else _minusculas(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_minusculas(v) for v in obj]
    return obj


def ferramentas_openai(config) -> list[dict]:
    """Converte as declaracoes de funcao do Gemini para o formato `tools` da OpenAI."""
    saida = []
    for tool in getattr(config, "tools", None) or []:
        for fd in getattr(tool, "function_declarations", None) or []:
            params = _minusculas(fd.parameters.model_dump(exclude_none=True)) if fd.parameters else {"type": "object", "properties": {}}
            saida.append({"type": "function", "function": {"name": fd.name, "description": fd.description or "",
                                                           "parameters": params}})
    return saida


def _post(corpo: dict) -> dict:
    if not settings.openrouter_api_key:
        raise ErroOpenRouter("OPENROUTER_API_KEY nao configurada")
    try:
        r = httpx.post(URL, json=corpo, timeout=90.0, headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}", "Content-Type": "application/json",
            "X-Title": "Assistente de dados"})
    except httpx.HTTPError as e:
        raise ErroOpenRouter(f"{type(e).__name__}: {e}") from e
    if r.status_code != 200:
        raise ErroOpenRouter(f"HTTP {r.status_code}: {r.text[:200]}")
    dados = r.json()
    if dados.get("error"):
        raise ErroOpenRouter(f"erro do provedor: {str(dados['error'])[:200]}")
    return dados


def adaptar(dados: dict):
    """Resposta da OpenAI para o formato do google-genai que o orquestrador usa."""
    escolhas = dados.get("choices") or []
    if not escolhas:
        raise ErroOpenRouter("resposta sem choices")
    msg = escolhas[0].get("message") or {}
    texto = (msg.get("content") or "").strip()
    partes = []
    if msg.get("reasoning"):
        partes.append(types.Part(text=str(msg["reasoning"]), thought=True))
    if texto:
        partes.append(types.Part.from_text(text=texto))
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        partes.append(types.Part(function_call=types.FunctionCall(id=tc.get("id"), name=fn.get("name"), args=args)))
    if not texto and not any(getattr(p, "function_call", None) for p in partes):
        raise ErroOpenRouter("resposta vazia")
    uso = dados.get("usage") or {}
    return SimpleNamespace(
        candidates=[SimpleNamespace(content=types.Content(role="model", parts=partes),
                                    finish_reason=escolhas[0].get("finish_reason"))],
        text=texto,
        usage_metadata=SimpleNamespace(prompt_token_count=uso.get("prompt_tokens", 0),
                                       candidates_token_count=uso.get("completion_tokens", 0),
                                       thoughts_token_count=None, cached_content_token_count=None))


def gerar(modelo: str, contents, config, system: str | None):
    """Uma chamada a um modelo gratuito do OpenRouter, com o historico e as tools do Gemini."""
    from cristalux.llm import para_mensagens

    corpo = {"model": modelo, "messages": para_mensagens(system, contents), "temperature": 0}
    tools = ferramentas_openai(config)
    if tools:
        corpo["tools"] = tools
    return adaptar(_post(corpo))
