from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import init_db, SessionLocal
from app.db.models import Incident
from app.db.seed import seed_database
from app.rag.retriever import get_retriever
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    init_db()
    db = SessionLocal()
    try:
        # Seed realistic incident data if empty
        if db.query(Incident).count() == 0:
            seed_database()
    finally:
        db.close()

    # Pre-index Qdrant runbooks in background
    try:
        get_retriever()
    except Exception as e:
        print(f"Notice: Qdrant retriever initialization deferred: {e}")

    yield


app = FastAPI(
    title="IncidentPilot API",
    description="Autonomous Production Incident Response Agent Engine",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
