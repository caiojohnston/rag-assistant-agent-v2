"""Metricas RAGAS (faithfulness, answer relevancy, context recall) usando o Gemini como juiz.

Ressalva registrada no README: o mesmo modelo gera e julga a resposta, o que tende a inflar as notas.
"""
from __future__ import annotations

from cristalux.config import settings


def avaliar(amostras: list[dict]) -> dict[str, dict] | None:
    """amostras: [{id, pergunta, resposta, contextos, referencia}]. Devolve {id: {metrica: nota}} ou None se indisponivel."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
        from ragas import EvaluationDataset, evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import Faithfulness, LLMContextRecall, ResponseRelevancy
    except Exception as e:  # dependencia ausente ou incompativel
        print(f"RAGAS indisponivel: {type(e).__name__}: {e}")
        return None
    if not settings.gemini_api_key:
        return None

    llm = LangchainLLMWrapper(ChatGoogleGenerativeAI(model=settings.gemini_model, google_api_key=settings.gemini_api_key,
                                                     temperature=0))
    emb = LangchainEmbeddingsWrapper(GoogleGenerativeAIEmbeddings(
        model=f"models/{settings.gemini_embedding_model}", google_api_key=settings.gemini_api_key))
    validas = [a for a in amostras if a["contextos"]]
    if not validas:
        return {}
    ds = EvaluationDataset.from_list([{
        "user_input": a["pergunta"], "response": a["resposta"], "retrieved_contexts": a["contextos"],
        "reference": a["referencia"]} for a in validas])
    try:
        res = evaluate(ds, metrics=[Faithfulness(), ResponseRelevancy(), LLMContextRecall()], llm=llm, embeddings=emb,
                       show_progress=False)
    except Exception as e:
        print(f"RAGAS falhou: {type(e).__name__}: {e}")
        return None
    df = res.to_pandas()
    saida = {}
    for a, (_, linha) in zip(validas, df.iterrows()):
        saida[a["id"]] = {k: (None if linha.get(k) != linha.get(k) else round(float(linha[k]), 3))
                          for k in ("faithfulness", "answer_relevancy", "context_recall") if k in linha}
    return saida
