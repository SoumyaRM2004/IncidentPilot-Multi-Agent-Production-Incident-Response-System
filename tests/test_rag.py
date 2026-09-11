from app.rag.runbooks import load_and_chunk_runbooks
from app.rag.retriever import get_retriever


def test_runbook_chunking():
    chunks = load_and_chunk_runbooks()
    assert len(chunks) >= 5
    for c in chunks:
        assert c["chunk_id"].startswith("RUNBOOK-")
        assert c["source"].endswith(".md")
        assert c["title"] != ""
        assert c["section"] != ""
        assert len(c["content"]) > 20


def test_retriever_search():
    retriever = get_retriever()
    results = retriever.search_runbooks("database connection pool timeout overflow", limit=2)
    assert len(results) > 0
    top = results[0]
    assert "database_connection_pool" in top["source"]
    assert top["evidence_id"].startswith("RUNBOOK-")
    assert top["score"] > 0.4
