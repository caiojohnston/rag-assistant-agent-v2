"""Cliente do Gemini: repeticao em erro transitorio, cache opcional em disco e registro das generations no Langfuse."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from cristalux import obs
from cristalux.config import ROOT, settings

CACHE_DIR = ROOT / ".cache" / "llm"
_cliente = None


class LLMIndisponivel(RuntimeError):
    pass


class CotaDiariaEsgotada(RuntimeError):
    """429 com espera longa: a cota diaria do free tier acabou. Repetir em segundos nao adianta."""


def _espera_sugerida(erro) -> float | None:
    """Segundos que a API pede para esperar (campo retryDelay), quando informado."""
    import re

    m = re.search(r"retryDelay'?\"?: '?\"?(\d+(?:\.\d+)?)s", str(erro)) or re.search(r"retry in (?:(\d+)h)?(?:(\d+)m)?(\d+(?:\.\d+)?)s", str(erro))
    if not m:
        return None
    partes = [float(g) for g in m.groups() if g]
    if len(m.groups()) == 3:  # formato "7h31m19s"
        h, mi, s = (float(g) if g else 0.0 for g in m.groups())
        return h * 3600 + mi * 60 + s
    return partes[0]


def cliente():
    global _cliente
    if _cliente is None:
        if not settings.gemini_api_key:
            raise LLMIndisponivel("GEMINI_API_KEY nao configurada")
        from google import genai
        _cliente = genai.Client(api_key=settings.gemini_api_key)
    return _cliente


def com_repeticao(fn, tentativas: int = 5):
    """Repete em 429/5xx com espera crescente (o free tier tem limite por minuto)."""
    from google.genai import errors

    espera = 4.0
    for i in range(tentativas):
        try:
            return fn()
        except (errors.ClientError, errors.ServerError) as e:
            codigo = getattr(e, "code", None)
            if codigo not in (429, 500, 502, 503, 504) or i == tentativas - 1:
                raise
            sugerida = _espera_sugerida(e) if codigo == 429 else None
            if sugerida and sugerida > 120:
                raise CotaDiariaEsgotada(f"cota do modelo esgotada; a API pede {int(sugerida // 60)} min de espera") from e
            time.sleep(max(espera, sugerida or 0))
            espera = min(espera * 2, 60)


def config_raciocinio():
    """Nivel de raciocinio configuravel (latencia e custo) e pedido do resumo do raciocinio."""
    from google.genai import types

    nivel = {"minimal": types.ThinkingLevel.MINIMAL, "low": types.ThinkingLevel.LOW,
             "medium": types.ThinkingLevel.MEDIUM, "high": types.ThinkingLevel.HIGH}.get(settings.gemini_thinking.lower())
    return types.ThinkingConfig(thinking_level=nivel, include_thoughts=True)


# ----------------------------------------------------------- formato de mensagens para o Langfuse

def _args_json(args) -> str:
    return json.dumps(dict(args or {}), ensure_ascii=False, default=str)


def para_mensagens(system: str | None, contents) -> list[dict]:
    """Converte o historico do Gemini para mensagens no formato OpenAI, que o Langfuse renderiza como conversa."""
    if isinstance(contents, str):
        contents = [type("C", (), {"role": "user", "parts": [type("P", (), {"text": contents, "function_call": None,
                                                                            "function_response": None, "thought": False})()]})()]
    mensagens = [{"role": "system", "content": system}] if system else []
    contador = 0
    for c in contents:
        texto, chamadas = [], []
        for p in c.parts or []:
            fc, fr = getattr(p, "function_call", None), getattr(p, "function_response", None)
            if fc:
                contador += 1
                chamadas.append({"id": fc.id or f"call_{contador}", "type": "function",
                                 "function": {"name": fc.name, "arguments": _args_json(fc.args)}})
            elif fr:
                mensagens.append({"role": "tool", "name": fr.name, "tool_call_id": fr.id or f"call_{contador}",
                                  "content": json.dumps(fr.response, ensure_ascii=False, default=str)})
            elif getattr(p, "text", None) and not getattr(p, "thought", False):
                texto.append(p.text)
        if texto or chamadas:
            papel = "assistant" if c.role == "model" else "user"
            msg = {"role": papel, "content": "\n".join(texto)}
            if chamadas:
                msg["tool_calls"] = chamadas
            mensagens.append(msg)
    return mensagens


def extrair_saida(resp) -> tuple[dict, str]:
    """Mensagem do assistente (texto e chamadas de tool) e o resumo do raciocinio do modelo."""
    texto, pensamento, chamadas = [], [], []
    partes = resp.candidates[0].content.parts if resp.candidates and resp.candidates[0].content else []
    for i, p in enumerate(partes, 1):
        if getattr(p, "function_call", None):
            fc = p.function_call
            chamadas.append({"id": fc.id or f"call_{i}", "type": "function",
                             "function": {"name": fc.name, "arguments": _args_json(fc.args)}})
        elif getattr(p, "text", None):
            (pensamento if getattr(p, "thought", False) else texto).append(p.text)
    msg = {"role": "assistant", "content": "\n".join(texto)}
    if chamadas:
        msg["tool_calls"] = chamadas
    return msg, "\n".join(pensamento).strip()


def chamar_gemini(nome: str, contents, config=None, system: str | None = None, modelo: str | None = None,
                  parametros: dict | None = None):
    """Uma chamada ao Gemini registrada como `generation` com nome estavel.

    Registra modelo, tokens (entrada, saida e raciocinio), mensagens de entrada e saida e o resumo do raciocinio.
    """
    modelo = modelo or settings.gemini_model
    with obs.geracao(nome, modelo, input=para_mensagens(system, contents), model_parameters=parametros) as g:
        resp = com_repeticao(lambda: cliente().models.generate_content(model=modelo, contents=contents, config=config))
        saida, pensamento = extrair_saida(resp)
        uso = getattr(resp, "usage_metadata", None)
        detalhes = {"input": getattr(uso, "prompt_token_count", 0) or 0,
                    "output": getattr(uso, "candidates_token_count", 0) or 0}
        if getattr(uso, "thoughts_token_count", None):
            detalhes["output_reasoning_tokens"] = uso.thoughts_token_count
        if getattr(uso, "cached_content_token_count", None):
            detalhes["input_cached_tokens"] = uso.cached_content_token_count
        if pensamento:
            saida["reasoning"] = pensamento[:3000]
        g.update(output=saida, usage_details=detalhes,
                 metadata={"pensamento_chars": len(pensamento), "finish_reason": str(
                     getattr(resp.candidates[0], "finish_reason", "")) if resp.candidates else ""})
    return resp


# ----------------------------------------------------------- geracao simples de texto

def _chave_cache(modelo: str, system: str | None, prompt: str, json_mode: bool) -> Path:
    h = hashlib.sha256(json.dumps([modelo, system, prompt, json_mode], ensure_ascii=False).encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def gerar_texto(prompt: str, system: str | None = None, temperature: float = 0.0, json_mode: bool = False,
                modelo: str | None = None, nome: str = "generate-text") -> str:
    from google.genai import types

    modelo = modelo or settings.gemini_model
    arquivo = _chave_cache(modelo, system, prompt, json_mode)
    if settings.llm_cache and arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))["texto"]

    config = types.GenerateContentConfig(
        system_instruction=system, temperature=temperature,
        thinking_config=config_raciocinio(),
        response_mime_type="application/json" if json_mode else None)
    resp = chamar_gemini(nome, [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])], config,
                         system=system, modelo=modelo, parametros={"temperature": temperature, "json": json_mode})
    texto = resp.text or ""
    if settings.llm_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps({"texto": texto}, ensure_ascii=False), encoding="utf-8")
    return texto
