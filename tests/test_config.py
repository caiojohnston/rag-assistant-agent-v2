from cristalux import config


def test_url_do_agente_deriva_da_database_url(monkeypatch):
    monkeypatch.delenv("AGENT_DATABASE_URL", raising=False)
    url = config._url_do_agente("postgresql://postgres:p%40ss@postgres.railway.internal:5432/railway", "seg/redo")
    assert url == "postgresql://cristalux_agent_ro:seg%2Fredo@postgres.railway.internal:5432/railway"


def test_url_do_agente_explicita_tem_precedencia(monkeypatch):
    monkeypatch.setenv("AGENT_DATABASE_URL", "postgresql://x:y@h/d")
    assert config._url_do_agente("postgresql://a:b@c/d", "z") == "postgresql://x:y@h/d"
