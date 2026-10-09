"""Reserva final da geracao: modelos gratuitos do OpenRouter."""
import pytest
from google.genai import types

from cristalux import llm, llm_openrouter as orr


def test_ferramentas_no_formato_openai():
    cfg = types.GenerateContentConfig(tools=[types.Tool(function_declarations=[types.FunctionDeclaration(
        name="consultar_dados", description="x", parameters=types.Schema(
            type=types.Type.OBJECT, properties={"pergunta": types.Schema(type=types.Type.STRING)}, required=["pergunta"]))])])
    tools = orr.ferramentas_openai(cfg)
    assert tools[0]["function"]["name"] == "consultar_dados"
    assert tools[0]["function"]["parameters"]["type"] == "object"
    assert tools[0]["function"]["parameters"]["properties"]["pergunta"]["type"] == "string"


def test_resposta_com_tool_call_vira_formato_do_gemini():
    resp = orr.adaptar({"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "abc", "type": "function", "function": {"name": "consultar_dados", "arguments": "{\"pergunta\": \"x\"}"}}]},
        "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 10, "completion_tokens": 3}})
    fc = resp.candidates[0].content.parts[0].function_call
    assert fc.name == "consultar_dados" and dict(fc.args) == {"pergunta": "x"} and fc.id == "abc"
    assert resp.usage_metadata.prompt_token_count == 10


def test_resposta_de_texto():
    resp = orr.adaptar({"choices": [{"message": {"content": "Olá"}}]})
    assert resp.text == "Olá" and resp.candidates[0].content.parts[0].text == "Olá"


def test_resposta_vazia_ou_sem_choices_e_erro():
    with pytest.raises(orr.ErroOpenRouter):
        orr.adaptar({"choices": [{"message": {"content": ""}}]})
    with pytest.raises(orr.ErroOpenRouter):
        orr.adaptar({})


def test_sem_chave_e_erro(monkeypatch):
    object.__setattr__(llm.settings, "openrouter_api_key", "")
    with pytest.raises(orr.ErroOpenRouter):
        orr._post({})


def test_cadeia_cai_no_openrouter_quando_o_gemini_todo_falha(monkeypatch):
    class Modelos:
        def generate_content(self, model, contents, config):
            raise llm.CotaDiariaEsgotada("acabou")

    monkeypatch.setattr(llm, "cliente", lambda: type("C", (), {"models": Modelos()})())
    object.__setattr__(llm.settings, "gemini_fallback_models", ("g2",))
    object.__setattr__(llm.settings, "openrouter_api_key", "chave-de-teste")
    object.__setattr__(llm.settings, "openrouter_models", ("modelo-ruim:free", "modelo-bom:free"))
    llm._ESGOTADOS.clear()

    def falso(modelo, contents, config, sistema):
        if modelo == "modelo-ruim:free":
            raise orr.ErroOpenRouter("HTTP 429")
        return "ok-openrouter"

    monkeypatch.setattr(orr, "gerar", falso)
    resp, usado = llm._gerar_com_reserva("g1", [], None)
    assert usado == "openrouter:modelo-bom:free" and resp == "ok-openrouter"
    object.__setattr__(llm.settings, "openrouter_api_key", "")
    llm._ESGOTADOS.clear()


def test_extrair_json_tolera_cerca_de_codigo():
    from cristalux.agent.sql_agent import extrair_json

    assert extrair_json('{"sql": "SELECT 1"}')["sql"] == "SELECT 1"
    assert extrair_json('```json\n{"sql": "SELECT 2"}\n```')["sql"] == "SELECT 2"
    assert extrair_json('Claro! {"sql": "SELECT 3", "premissas": "x"} pronto')["sql"] == "SELECT 3"
    assert extrair_json("nao e json") == {"sql": "", "premissas": ""}
