"""Configuracao lida de variaveis de ambiente (compativel com Docker e Railway)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

def _raiz() -> Path:
    """Raiz do projeto: APP_ROOT (Docker), a pasta do repositorio (instalacao editavel) ou o diretorio atual."""
    if os.getenv("APP_ROOT"):
        return Path(os.environ["APP_ROOT"])
    candidata = Path(__file__).resolve().parents[2]
    return candidata if (candidata / "sql").exists() else Path.cwd()


ROOT = _raiz()


def _url_do_agente(database_url: str, senha: str) -> str:
    """URL do papel somente leitura. AGENT_DATABASE_URL, se definida; senao deriva da DATABASE_URL (Railway)."""
    if os.getenv("AGENT_DATABASE_URL"):
        return os.environ["AGENT_DATABASE_URL"]
    from urllib.parse import quote, urlsplit, urlunsplit

    u = urlsplit(database_url)
    porta = f":{u.port}" if u.port else ""
    return urlunsplit((u.scheme, f"cristalux_agent_ro:{quote(senha, safe='')}@{u.hostname}{porta}", u.path, u.query, ""))


def _path(name: str, default: str) -> Path:
    p = Path(os.getenv(name, default))
    return p if p.is_absolute() else ROOT / p


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cristalux")
    agent_db_password: str = os.getenv("AGENT_DB_PASSWORD", "agent_ro_local")
    agent_database_url: str = _url_do_agente(
        os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cristalux"),
        os.getenv("AGENT_DB_PASSWORD", "agent_ro_local"))
    # Senha de acesso ao app. Vazia = sem protecao (so para uso local).
    app_password: str = os.getenv("APP_PASSWORD", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    # Modelos de reserva, na ordem, quando a cota diaria do principal acaba (ou ele fica indisponivel).
    gemini_fallback_models: tuple = tuple(m.strip() for m in os.getenv(
        "GEMINI_FALLBACK_MODELS", "gemini-3-flash-preview,gemini-3.6-flash,gemini-3.5-flash,gemini-flash-lite-latest"
    ).split(",") if m.strip())
    gemini_embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    langfuse_host: str = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    langfuse_public_key: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    # gemini | local | hash. Sem chave do Gemini cai em local.
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "")
    rag_k: int = int(os.getenv("RAG_K", "5"))
    rag_threshold: float | None = float(os.getenv("RAG_THRESHOLD")) if os.getenv("RAG_THRESHOLD") else None
    llm_cache: bool = os.getenv("LLM_CACHE", "0") == "1"
    # minimal | low | medium | high: quanto o modelo raciocina antes de responder (afeta latencia e custo).
    gemini_thinking: str = os.getenv("GEMINI_THINKING_LEVEL", "low")
    data_dir: Path = _path("DATA_DIR", "dados_raw")
    reports_dir: Path = _path("REPORTS_DIR", "reports")
    chroma_path: Path = _path("CHROMA_PATH", "chroma_db")
    sql_dir: Path = ROOT / "sql"


settings = Settings()

# Janela de analise do enunciado.
ANO_INICIO = 2020
ANO_FIM = 2024
