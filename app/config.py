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
    groq_rate_limit_cooldown_seconds: float = 60.0
    # Bounded post-report grace period (in minutes) for telemetry collection.
    # Metrics and logs emitted during initial triage or delayed by pipeline ingestion buffering
    # (e.g. 1-5 min scraping/flush intervals) shortly after reported_at are captured,
    # while excluding unrelated future data.
    telemetry_post_report_grace_minutes: int = 5
    allowed_origins: list = ["http://localhost:8501", "http://127.0.0.1:8501"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
