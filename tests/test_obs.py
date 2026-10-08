"""Formato das generations enviadas ao Langfuse e mascaramento de dados pessoais."""
from types import SimpleNamespace

from google.genai import types

from cristalux.llm import extrair_saida, para_mensagens
from cristalux.obs import mascarar


def test_mascarar_email_cnpj_telefone_em_estruturas_aninhadas():
    dado = {"a": "fale com ana@empresa.com.br", "b": ["CNPJ 12.345.678/0001-90", {"c": "tel (11) 98765-4321"}], "n": 7}
    saida = mascarar(dado)
    assert "[email]" in saida["a"] and "ana@" not in saida["a"]
    assert "[cnpj]" in saida["b"][0]
    assert "[telefone]" in saida["b"][1]["c"]
    assert saida["n"] == 7


def test_mascarar_nao_altera_valores_monetarios_nem_ids():
    assert mascarar("R$ 133.868,40 em 2022, venda VD0054") == "R$ 133.868,40 em 2022, venda VD0054"


def test_historico_vira_mensagens_openai_com_tool_calls():
    contents = [
        types.Content(role="user", parts=[types.Part.from_text(text="top 3 compradores?")]),
        types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="consultar_dados", args={"pergunta": "x"}))]),
        types.Content(role="user", parts=[types.Part.from_function_response(name="consultar_dados", response={"resultado": {"total_linhas": 3}})]),
    ]
    m = para_mensagens("instrucoes", contents)
    assert [x["role"] for x in m] == ["system", "user", "assistant", "tool"]
    assert m[2]["tool_calls"][0]["function"]["name"] == "consultar_dados"
    assert m[2]["tool_calls"][0]["function"]["arguments"] == '{"pergunta": "x"}'  # JSON em string, como o Langfuse espera
    assert m[3]["tool_call_id"] == m[2]["tool_calls"][0]["id"] or m[3]["tool_call_id"].startswith("call_")
    assert "total_linhas" in m[3]["content"]


def test_pensamento_nao_entra_nas_mensagens_e_vai_para_o_campo_reasoning():
    partes = [types.Part(text="vou consultar o banco", thought=True), types.Part.from_text(text="Resposta final")]
    resp = SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(role="model", parts=partes))])
    msg, pensamento = extrair_saida(resp)
    assert msg == {"role": "assistant", "content": "Resposta final"}
    assert pensamento == "vou consultar o banco"
    historico = para_mensagens(None, [types.Content(role="model", parts=partes)])
    assert historico[0]["content"] == "Resposta final"
