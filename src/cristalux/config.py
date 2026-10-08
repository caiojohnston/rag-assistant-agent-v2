"""Configuracao lida de variaveis de ambiente (compativel com Docker e Railway)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]


def _path(name: str, default: str) -> Path:
    p = Path(os.getenv(name, default))
    return p if p.is_absolute() else ROOT / p


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cristalux")
    agent_database_url: str = os.getenv(
        "AGENT_DATABASE_URL", "postgresql://cristalux_agent_ro:agent_ro_local@localhost:5432/cristalux"
    )
    agent_db_password: str = os.getenv("AGENT_DB_PASSWORD", "agent_ro_local")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    langfuse_host: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    data_dir: Path = _path("DATA_DIR", "dados_raw")
    reports_dir: Path = _path("REPORTS_DIR", "reports")
    chroma_path: Path = _path("CHROMA_PATH", "chroma_db")
    sql_dir: Path = ROOT / "sql"


settings = Settings()

# Janela de analise do enunciado.
ANO_INICIO = 2020
ANO_FIM = 2024
