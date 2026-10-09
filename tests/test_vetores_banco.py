"""Persistencia dos vetores do Chroma no Postgres (precisa do Postgres local, como os outros testes de banco)."""
import psycopg
import pytest

from cristalux.config import settings
from cristalux.db.setup import conectar, setup
from cristalux.rag import store
from cristalux.rag.embeddings import HashEmbedder
from tests.test_rag import chunks  # noqa: F401

pytestmark = pytest.mark.db


def _banco() -> bool:
    try:
        setup()
        return True
    except Exception:
        return False


if not _banco():
    pytest.skip("Postgres indisponivel", allow_module_level=True)


def test_salvar_e_restaurar_vetores(tmp_path):
    object.__setattr__(settings, "chroma_path", tmp_path / "a")
    store.indexar(chunks(), HashEmbedder())
    assert store.salvar_no_banco("hash") == 3

    object.__setattr__(settings, "chroma_path", tmp_path / "b")   # novo container: colecao vazia
    assert store.colecao("hash").count() == 0
    assert store.restaurar_do_banco("hash") == 3
    r = store.indexar(chunks(), HashEmbedder())
    assert r["novos"] == 0 and r["total"] == 3                    # nada precisou ser embedado de novo

    with conectar() as c:
        c.execute("DELETE FROM meta.vetores WHERE backend = 'hash'")
