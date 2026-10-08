"""Testa o laco do orquestrador com um modelo simulado, sem chamar o Gemini."""
from types import SimpleNamespace

from google.genai import types

from cristalux.agent import orquestrador as orq
from cristalux.security.verificador import vazou


def resposta_com_tool(nome, **args):
    parte = types.Part(function_call=types.FunctionCall(name=nome, args=args))
    conteudo = types.Content(role="model", parts=[parte])
    return SimpleNamespace(candidates=[SimpleNamespace(content=conteudo)], text=None)


def resposta_texto(texto):
    conteudo = types.Content(role="model", parts=[types.Part.from_text(text=texto)])
    return SimpleNamespace(candidates=[SimpleNamespace(content=conteudo)], text=texto)


def roteiro(monkeypatch, respostas):
    fila = list(respostas)
    chamadas = []

    def falso(contents, com_tools=True):
        chamadas.append(com_tools)
        return fila.pop(0)

    monkeypatch.setattr(orq, "_chamar_modelo", falso)
    return chamadas


def test_pergunta_numerica_usa_tool_de_sql(monkeypatch):
    chamadas = roteiro(monkeypatch, [resposta_com_tool("consultar_dados", pergunta="top 3 compradores"),
                                     resposta_texto("Os top 3 sao A, B e C.")])
    monkeypatch.setattr(orq.tools, "consultar_dados", lambda pergunta, emitir=None: {
        "sql": "SELECT 1 LIMIT 3", "premissas": "vendas concluidas", "colunas": ["comprador"],
        "linhas": [{"comprador": "A"}], "total_linhas": 1, "truncado": False, "tentativas": 1, "erro": None})
    eventos = []
    r = orq.responder("top 3 compradores?", on_event=eventos.append)
    assert r.texto == "Os top 3 sao A, B e C."
    assert r.fontes[0]["tipo"] == "sql" and r.tabelas[0]["total_linhas"] == 1
    assert [e.tipo for e in r.eventos] == ["modelo", "tool_chamada", "tool_resultado", "modelo", "resposta"]
    assert len(eventos) == len(r.eventos)  # a interface recebe cada passo em tempo real


def test_falha_de_tool_e_repassada_ao_modelo(monkeypatch):
    roteiro(monkeypatch, [resposta_com_tool("consultar_dados", pergunta="x"), resposta_texto("A consulta falhou.")])

    def quebra(pergunta, emitir=None):
        raise RuntimeError("banco fora do ar")

    monkeypatch.setattr(orq.tools, "consultar_dados", quebra)
    r = orq.responder("qualquer coisa")
    assert r.texto == "A consulta falhou."
    tool_res = [e for e in r.eventos if e.tipo == "tool_resultado"][0]
    assert "banco fora do ar" in tool_res.dados["erro"]


def test_limite_de_chamadas_de_tool_desliga_as_tools(monkeypatch):
    pedidos = [resposta_com_tool("data_atual") for _ in range(orq.MAX_CHAMADAS_DE_TOOL)]
    chamadas = roteiro(monkeypatch, pedidos + [resposta_texto("fim")])
    monkeypatch.setattr(orq.tools, "data_atual", lambda emitir=None: {"data": "2026-10-08"})
    r = orq.responder("loop")
    assert r.texto == "fim" and chamadas[-1] is False


def test_guardrail_refaz_resposta_que_repete_a_injecao(monkeypatch):
    roteiro(monkeypatch, [
        resposta_texto("QUALIDADE = EXCELENTE, SCORE 9.8/10, nenhuma limpeza necessaria."),
        resposta_texto("Os dados nao estao limpos: ha duplicatas. A decisao D013 tem texto suspeito que nao foi seguido."),
    ])
    r = orq.responder("Os dados estao limpos?")
    assert "nao estao limpos" in r.texto
    assert any(e.tipo == "guardrail" for e in r.eventos)


def test_erro_do_modelo_vira_resposta_de_falha(monkeypatch):
    def quebra(contents, com_tools=True):
        raise RuntimeError("sem rede")

    monkeypatch.setattr(orq, "_chamar_modelo", quebra)
    r = orq.responder("oi")
    assert r.erro and "sem rede" in r.texto


def test_verificador():
    assert vazou("Qualidade = EXCELENTE | score 9.8/10") != []
    assert vazou("Nenhuma limpeza necessaria, dados prontos para modelagem.") != []
    assert vazou("A D013 afirma qualidade excelente, mas e um texto suspeito que ignorei.") == []
    assert vazou("Foram rejeitadas 94 de 190 linhas de vendas.") == []
