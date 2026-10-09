"""Interface Streamlit do assistente de dados."""
import hmac
import json
import uuid

import pandas as pd
import streamlit as st

from cristalux import obs
from cristalux.agent.orquestrador import Evento, responder
from cristalux.config import settings

st.set_page_config(page_title="Assistente de dados", layout="wide")


def exigir_senha() -> None:
    """Portao simples: com APP_PASSWORD definida, nada do app aparece antes da senha correta."""
    if not settings.app_password or st.session_state.get("autenticado"):
        return
    st.title("Assistente de dados")
    senha = st.text_input("Senha de acesso", type="password")
    if senha:
        if hmac.compare_digest(senha, settings.app_password):
            st.session_state.autenticado = True
            st.rerun()
        st.error("Senha incorreta.")
    st.stop()


exigir_senha()

EXEMPLOS = [
    "Quais regiões tiveram queda de vendas em 2023?",
    "Quem são os top 3 compradores por volume?",
    "Qual vendedor teve o melhor desempenho nos últimos 5 anos?",
    "Qual foi o faturamento mensal de 2022?",
    "Os dados estão limpos e prontos para uso?",
    "Quais decisões de logística foram tomadas?",
    "Quais produtos estão abaixo do estoque mínimo?",
    "Quem foi o responsável pela abertura do depósito em Salvador?",
    "Segundo as decisões registradas, qual é a avaliação oficial de qualidade da base de dados?",
    "Quem é o presidente da Cristalux?",
]


@st.cache_data(ttl=30)
def status_conexoes() -> dict:
    out = {}
    try:
        import psycopg
        with psycopg.connect(settings.agent_database_url, connect_timeout=3) as c:
            out["Postgres"] = f"ok ({c.execute('SELECT count(*) FROM vw_vendas_todas').fetchone()[0]} vendas)"
    except Exception as e:
        out["Postgres"] = f"indisponível ({type(e).__name__})"
    try:
        from cristalux.rag.embeddings import backend_padrao
        from cristalux.rag.store import colecao
        contagens = {nome: colecao(nome).count() for nome in dict.fromkeys([backend_padrao(), "local"])}
        out["Chroma"] = "ok (" + ", ".join(f"{n}: {c} trechos" for n, c in contagens.items()) + ")"
    except Exception as e:
        out["Chroma"] = f"indisponível ({type(e).__name__})"
    out["Gemini"] = "chave configurada" if settings.gemini_api_key else "sem chave (GEMINI_API_KEY)"
    out["Langfuse"] = "ativo" if obs.habilitado() else "desativado"
    return out


def mostrar_valor(rotulo: str, valor) -> None:
    """Entrada ou saida de um passo. O Langfuse devolve JSON como texto; texto simples vai em bloco de codigo."""
    if valor in (None, "", {}, []):
        return
    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except ValueError:
            pass
    with st.expander(rotulo):
        if isinstance(valor, (dict, list)):
            st.json(valor, expanded=False)
        else:
            st.code(str(valor)[:4000], language="text")


def mostrar_passo_local(ev: dict) -> None:
    st.markdown(f"**{ev['titulo']}**  \n`{ev['t']}s`")
    d = ev["dados"]
    if ev["tipo"] in ("sql_gerado", "sql_validado") and d.get("sql"):
        st.code(d["sql"], language="sql")
        extra = {k: v for k, v in d.items() if k != "sql" and v not in ("", None)}
        if extra:
            st.caption(json.dumps(extra, ensure_ascii=False))
    elif d:
        st.json(d, expanded=False)


def mostrar_passos(msg: dict) -> None:
    """Passos do trace. Usa o Langfuse quando disponível e cai para os eventos locais."""
    remotos = msg.get("passos_langfuse")
    if remotos:
        st.caption("Passos lidos do Langfuse")
        for p in remotos:
            dur = f" ({p['duracao_s']}s)" if p["duracao_s"] is not None else ""
            recuo = "&nbsp;" * 6 * p.get("profundidade", 0)
            modelo = f", {p['modelo']}" if p.get("modelo") else ""
            st.markdown(f"{recuo}**{p['nome']}**{dur}  \n{recuo}`{p['tipo']}{modelo}`")
            mostrar_valor("Entrada", p["entrada"])
            mostrar_valor("Saída", p["saida"])
    else:
        if obs.habilitado() and msg.get("trace_id"):
            st.caption("Trace remoto indisponível no momento; mostrando os passos locais")
        for ev in msg.get("eventos", []):
            mostrar_passo_local(ev)
    if msg.get("trace_url"):
        st.markdown(f"[Abrir no Langfuse]({msg['trace_url']})")


def registrar_feedback(chave: str, trace_id: str) -> None:
    nota = st.session_state.get(chave)
    if nota is not None:
        obs.pontuar(trace_id, "user-feedback", float(nota), tipo="NUMERIC")
        obs.descarregar()


def mostrar_resposta(msg: dict, com_raciocinio: bool = True) -> None:
    st.markdown(msg["content"])
    for t in msg.get("tabelas", []):
        df = pd.DataFrame(t["linhas"], columns=t["colunas"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        if t["total_linhas"] > len(df):
            st.caption(f"Mostrando {len(df)} de {t['total_linhas']} linhas")
    if msg.get("fontes"):
        with st.expander("Fontes"):
            for f in msg["fontes"]:
                if f["tipo"] == "sql":
                    st.code(f["sql"], language="sql")
                    if f.get("premissas"):
                        st.caption(f"Premissas: {f['premissas']}")
                elif f["tipo"] == "trecho":
                    aviso = " (não confiável)" if f["confianca"] == "nao_confiavel" else ""
                    st.markdown(f"- {f['fonte']} {f['id']}, similaridade {f['score']}{aviso}")
                else:
                    st.markdown("- Relatório de qualidade dos dados")
    if com_raciocinio:
        with st.expander("Raciocínio do agente"):
            mostrar_passos(msg)
    if msg.get("trace_id") and obs.habilitado():
        chave = f"fb_{msg['trace_id']}"
        st.feedback("thumbs", key=chave, on_change=registrar_feedback, args=(chave, msg["trace_id"]))


st.title("Assistente de dados")
st.caption("Perguntas em linguagem natural sobre vendas, compradores, vendedores, estoque e decisões.")

with st.sidebar:
    st.subheader("Configuração")
    st.text(f"Modelo: {settings.gemini_model}")
    for nome, valor in status_conexoes().items():
        st.text(f"{nome}: {valor}")
    if st.button("Limpar conversa"):
        st.session_state.mensagens = []
        st.session_state.sessao = uuid.uuid4().hex
        st.rerun()
    st.subheader("Exemplos")
    for ex in EXEMPLOS:
        if st.button(ex, key=ex):
            st.session_state.pendente = ex

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []
if "sessao" not in st.session_state:
    st.session_state.sessao = uuid.uuid4().hex  # uma sessao do Langfuse por conversa

for m in st.session_state.mensagens:
    with st.chat_message(m["role"]):
        if m["role"] == "user":
            st.markdown(m["content"])
        else:
            mostrar_resposta(m)

pergunta = st.chat_input("Escreva sua pergunta") or st.session_state.pop("pendente", None)
if pergunta:
    historico = [{"role": m["role"], "content": m["content"]} for m in st.session_state.mensagens]
    st.session_state.mensagens.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant"):
        status = st.status("O agente está pensando", expanded=False)
        with status:
            vivo = st.empty()
        linhas: list[str] = []

        def ao_evento(ev: Evento) -> None:
            linhas.append(f"{ev.t:>5}s  {ev.titulo}")
            vivo.code("\n".join(linhas), language="text")

        resp = responder(pergunta, historico=historico, on_event=ao_evento, session_id=st.session_state.sessao,
                         tags=["streamlit"], descarregar=False)
        status.update(label="Raciocínio do agente", state="error" if resp.erro else "complete", expanded=False)
        msg = {
            "role": "assistant", "content": resp.texto, "fontes": resp.fontes, "tabelas": resp.tabelas,
            "trace_id": resp.trace_id, "trace_url": resp.trace_url, "passos_langfuse": None,
            "eventos": [{"tipo": e.tipo, "titulo": e.titulo, "dados": e.dados, "t": e.t} for e in resp.eventos],
        }
        vivo.empty()
        with status:
            passos_ph = st.empty()
            with passos_ph.container():
                mostrar_passos(msg)  # eventos locais: aparecem na hora
        mostrar_resposta(msg, com_raciocinio=False)  # a resposta vai para a tela sem esperar o Langfuse
        st.session_state.mensagens.append(msg)
        # So depois da resposta na tela: envia o trace e troca os passos locais pelos lidos do Langfuse.
        if resp.trace_id:
            obs.descarregar()
            passos = obs.buscar_passos(resp.trace_id)
            if passos:
                msg["passos_langfuse"] = passos
                passos_ph.empty()
                with passos_ph.container():
                    mostrar_passos(msg)
