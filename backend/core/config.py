from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    # ── LLM Provider ─────────────────────────────────────────────
    # "groq"   → Groq Cloud (KHUYẾN NGHỊ cho VN - miễn phí, cực nhanh)
    # "gemini" → Google Gemini (hay bị 429 ở VN)
    # "claude" → Anthropic Claude (trả phí)
    # "ollama" → Local model (hoàn toàn offline)
    llm_provider: str = Field(default="groq", env="LLM_PROVIDER")

    # ── Groq (FREE - 14,400 req/ngày, cực nhanh) ─────────────────
    # Lấy key tại: https://console.groq.com
    groq_api_key: str = Field(default="", env="GROQ_API_KEY")
    # Models Groq (2025):
    #   llama-3.3-70b-versatile   → KHUYẾN NGHỊ: mạnh + tiếng Việt tốt
    #   llama-3.1-8b-instant      → siêu nhanh, nhẹ
    #   mixtral-8x7b-32768        → context dài 32k
    #   gemma2-9b-it              → Google Gemma 2
    groq_model: str = Field(default="llama-3.3-70b-versatile", env="GROQ_MODEL")

    # ── Gemini (hay bị 429 ở Việt Nam) ───────────────────────────
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", env="GEMINI_MODEL")

    # ── Anthropic Claude ──────────────────────────────────────────
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    claude_model: str = Field(default="claude-opus-4-5", env="CLAUDE_MODEL")

    # ── Ollama (local) ────────────────────────────────────────────
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.2", env="OLLAMA_MODEL")

    # ── Embedding ─────────────────────────────────────────────────
    embedding_provider: str = Field(default="local", env="EMBEDDING_PROVIDER")
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        env="EMBEDDING_MODEL"
    )
    gemini_embedding_model: str = Field(
        default="models/text-embedding-004",
        env="GEMINI_EMBEDDING_MODEL"
    )

    # ── Vector DB ─────────────────────────────────────────────────
    chroma_persist_dir: str = Field(default="./data/chroma_db", env="CHROMA_PERSIST_DIR")
    chroma_collection_name: str = Field(default="documents", env="CHROMA_COLLECTION_NAME")

    # ── SQLite ────────────────────────────────────────────────────
    sqlite_db_path: str = Field(default="./data/chat_history.db", env="SQLITE_DB_PATH")

    # ── Chunking ──────────────────────────────────────────────────
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")
    chunking_strategy: str = Field(default="token", env="CHUNKING_STRATEGY")  # "token" hoặc "semantic"

    # ── Retrieval ─────────────────────────────────────────────────
    top_k_results: int = Field(default=5, env="TOP_K_RESULTS")
    similarity_threshold: float = Field(default=0.3, env="SIMILARITY_THRESHOLD")
    use_reranker: bool = Field(default=True, env="USE_RERANKER")
    reranker_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        env="RERANKER_MODEL"
    )
    reranker_top_n: int = Field(default=3, env="RERANKER_TOP_N")

    # ── Chat History ──────────────────────────────────────────────
    chat_history_limit: int = Field(default=10, env="CHAT_HISTORY_LIMIT")

    # ── Generation ────────────────────────────────────────────────
    max_tokens: int = Field(default=2048, env="MAX_TOKENS")
    temperature: float = Field(default=0.7, env="TEMPERATURE")

    # ── Server ────────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    debug: bool = Field(default=False, env="DEBUG")
    allowed_origins: str = Field(default="*", env="ALLOWED_ORIGINS")

    # ── Upload ────────────────────────────────────────────────────
    upload_dir: str = "./data/documents"
    max_file_size: int = 50 * 1024 * 1024
    allowed_extensions: List[str] = [".pdf", ".txt", ".docx", ".md", ".csv"]

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def active_model_name(self) -> str:
        mapping = {
            "groq":   self.groq_model,
            "gemini": self.gemini_model,
            "claude": self.claude_model,
            "ollama": self.ollama_model,
        }
        return mapping.get(self.llm_provider, self.groq_model)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

for d in [settings.chroma_persist_dir, settings.upload_dir, "./data"]:
    os.makedirs(d, exist_ok=True)
