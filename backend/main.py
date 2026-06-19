import logging, sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from core.embedding_manager import EmbeddingManager
from core.ingestion_pipeline import IngestionPipeline
from core.rag_engine import RAGEngine
from core.chat_history import init_db
from api import chat, documents, history

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("app.log")]
)
logger = logging.getLogger(__name__)

embedding_manager: EmbeddingManager = None
ingestion_pipeline: IngestionPipeline = None
rag_engine: RAGEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedding_manager, ingestion_pipeline, rag_engine
    logger.info("=" * 55)
    logger.info("🚀  RAG Chatbot v2 đang khởi động...")
    logger.info("=" * 55)
    try:
        init_db()
        logger.info("📦  Loading embedding model...")
        embedding_manager = EmbeddingManager(
            model_name=settings.embedding_model,
            persist_dir=settings.chroma_persist_dir,
            collection_name=settings.chroma_collection_name,
            embedding_provider=settings.embedding_provider,
            gemini_api_key=settings.gemini_api_key,
            gemini_embedding_model=settings.gemini_embedding_model,
        )
        ingestion_pipeline = IngestionPipeline(embedding_manager)
        rag_engine = RAGEngine(embedding_manager)

        stats = embedding_manager.get_stats()
        logger.info(f"✅  LLM: {settings.llm_provider.upper()} | {settings.active_model_name}")
        logger.info(f"📊  DB: {stats['total_chunks']} chunks | {stats.get('total_files',0)} files")
        logger.info(f"🌐  http://{settings.host}:{settings.port}  |  /docs")
        logger.info("=" * 55)
    except Exception as e:
        logger.error(f"❌  Lỗi khởi động: {e}")
        raise
    yield
    logger.info("👋  Server đang tắt...")


app = FastAPI(
    title="RAG Chatbot API v2",
    version="2.0.0",
    description="RAG: FastAPI + ChromaDB + **Groq**/Gemini/Claude/Ollama + SQLite",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(chat.router,      prefix="/api", tags=["Chat"])
app.include_router(history.router,   prefix="/api", tags=["History"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])


@app.get("/api/health")
async def health():
    stats = embedding_manager.get_stats() if embedding_manager else {}
    provider_ok = True
    provider_detail = ""

    if settings.llm_provider == "groq":
        provider_ok = bool(settings.groq_api_key and
                          settings.groq_api_key != "your_groq_api_key_here")
        if not provider_ok:
            provider_detail = "GROQ_API_KEY chưa cấu hình. Lấy free tại console.groq.com"
    elif settings.llm_provider == "gemini":
        provider_ok = bool(settings.gemini_api_key and
                          settings.gemini_api_key != "your_gemini_api_key_here")
        if not provider_ok:
            provider_detail = "GEMINI_API_KEY chưa cấu hình"
    elif settings.llm_provider == "claude":
        provider_ok = bool(settings.anthropic_api_key)
        if not provider_ok:
            provider_detail = "ANTHROPIC_API_KEY chưa cấu hình"
    elif settings.llm_provider == "ollama":
        import httpx
        try:
            httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
        except Exception:
            provider_ok = False
            provider_detail = f"Ollama không chạy tại {settings.ollama_base_url}"

    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "model": settings.active_model_name,
        "provider_ready": provider_ok,
        "provider_detail": provider_detail,
        "embedding_provider": settings.embedding_provider,
        "db_stats": stats,
    }


@app.get("/")
async def root():
    return {"message": "RAG Chatbot v2", "docs": "/docs", "health": "/api/health"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        reload_dirs=["api", "core"] if settings.debug else None,
        log_level="info"
    )
