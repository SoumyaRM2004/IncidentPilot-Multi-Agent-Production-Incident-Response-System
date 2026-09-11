import logging
from typing import List, Dict, Any
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.config import settings
from app.rag.runbooks import load_and_chunk_runbooks

logger = logging.getLogger(__name__)


class RunbookRetriever:
    _instance = None

    def __init__(self):
        self.embedding_model = TextEmbedding(model_name=settings.embedding_model_name)
        self.collection_name = settings.qdrant_collection

        # Dynamically determine embedding vector dimension
        probe_vector = next(self.embedding_model.embed(["dimension_probe"]))
        self.vector_size = len(probe_vector)

        # Initialize Qdrant Client based on URL or embedded path
        if settings.qdrant_url == ":memory:":
            self.client = QdrantClient(":memory:")
        elif settings.qdrant_url.startswith("http"):
            self.client = QdrantClient(url=settings.qdrant_url)
        else:
            self.client = QdrantClient(path=settings.qdrant_url)

        self._ensure_collection_and_index()

    def _ensure_collection_and_index(self):
        """Creates collection if not exists and ingests chunked runbooks."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
            self.index_runbooks()

    def index_runbooks(self) -> int:
        """Loads and indexes all runbook markdown files into Qdrant."""
        chunks = load_and_chunk_runbooks()
        if not chunks:
            return 0

        texts = [chunk["content"] for chunk in chunks]
        embeddings = list(self.embedding_model.embed(texts))

        points = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            points.append(
                PointStruct(
                    id=i + 1,
                    vector=emb.tolist(),
                    payload={
                        "chunk_id": chunk["chunk_id"],
                        "source": chunk["source"],
                        "title": chunk["title"],
                        "section": chunk["section"],
                        "content": chunk["content"],
                    },
                )
            )

        self.client.upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def search_runbooks(
        self,
        query: str,
        limit: int = None,
        min_score: float = None
    ) -> List[Dict[str, Any]]:
        """Semantic search against indexed operational runbooks."""
        limit = limit or settings.rag_limit
        min_score = min_score if min_score is not None else settings.rag_score_threshold

        query_embedding = list(self.embedding_model.embed([query]))[0].tolist()

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=limit,
            score_threshold=min_score,
            with_payload=True
        )

        results = []
        for hit in response.points:
            payload = hit.payload or {}
            chunk_id = payload.get("chunk_id", f"RUNBOOK-{hit.id}")
            results.append({
                "evidence_id": chunk_id,
                "source_type": "runbook",
                "source": payload.get("source", "operational_runbook"),
                "service": "all",
                "score": round(float(hit.score), 3),
                "finding": f"Runbook guidance [{payload.get('source')} - {payload.get('section')}]: {payload.get('content')[:140]}...",
                "details": {
                    "source_doc": payload.get("source"),
                    "title": payload.get("title"),
                    "section": payload.get("section"),
                    "similarity_score": round(float(hit.score), 3),
                    "content": payload.get("content")
                }
            })

        return results


_retriever_instance = None


def get_retriever() -> RunbookRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = RunbookRetriever()
    return _retriever_instance
