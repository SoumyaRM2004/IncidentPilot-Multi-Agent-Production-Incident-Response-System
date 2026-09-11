from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    database_url: str = "sqlite:///./incidentpilot.db"
    qdrant_url: str = ":memory:"
    qdrant_collection: str = "runbooks"
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    rag_score_threshold: float = 0.35
    rag_limit: int = 3
    max_investigation_iterations: int = 2
    min_supporting_evidence_count: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
