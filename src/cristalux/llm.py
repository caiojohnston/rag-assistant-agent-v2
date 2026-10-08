"""Cliente do Gemini com repeticao em erro transitorio e cache opcional em disco."""
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
            time.sleep(espera)
            espera = min(espera * 2, 60)


def _chave_cache(modelo: str, system: str | None, prompt: str, json_mode: bool) -> Path:
    h = hashlib.sha256(json.dumps([modelo, system, prompt, json_mode], ensure_ascii=False).encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


@obs.observar(name="gemini.generate", as_type="generation")
def gerar_texto(prompt: str, system: str | None = None, temperature: float = 0.0, json_mode: bool = False,
                modelo: str | None = None) -> str:
    from google.genai import types

    modelo = modelo or settings.gemini_model
    arquivo = _chave_cache(modelo, system, prompt, json_mode)
    if settings.llm_cache and arquivo.exists():
        texto = json.loads(arquivo.read_text(encoding="utf-8"))["texto"]
        obs.atualizar_geracao(model=modelo, input=prompt, output=texto, metadata={"cache": True})
        return texto

    config = types.GenerateContentConfig(
        system_instruction=system, temperature=temperature,
        response_mime_type="application/json" if json_mode else None)
    resp = com_repeticao(lambda: cliente().models.generate_content(model=modelo, contents=prompt, config=config))
    texto = resp.text or ""
    uso = getattr(resp, "usage_metadata", None)
    obs.atualizar_geracao(
        model=modelo, input=prompt, output=texto,
        usage_details={"input": getattr(uso, "prompt_token_count", 0) or 0,
                       "output": getattr(uso, "candidates_token_count", 0) or 0})
    if settings.llm_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps({"texto": texto}, ensure_ascii=False), encoding="utf-8")
    return texto
