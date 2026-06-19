import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingManager:
    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        persist_dir: str = "./data/chroma_db",
        collection_name: str = "documents",
        embedding_provider: str = "local",
        gemini_api_key: str = "",
        gemini_embedding_model: str = "models/text-embedding-004",
    ):
        self.embedding_provider = embedding_provider
        self.model_name = model_name

        # Khởi tạo embedding model
        if embedding_provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=gemini_api_key)
            self._genai = genai
            self._gemini_embed_model = gemini_embedding_model
            logger.info(f"Embedding: Gemini ({gemini_embedding_model})")
        else:
            self.model = SentenceTransformer(model_name)
            logger.info(f"Embedding: Local SentenceTransformer ({model_name})")

        # Khởi tạo ChromaDB
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"ChromaDB: {persist_dir} | collection: {collection_name}")

    # ── Embed ──────────────────────────────────────────────────────
    def embed_text(self, text: str) -> List[float]:
        if self.embedding_provider == "gemini":
            result = self._genai.embed_content(
                model=self._gemini_embed_model,
                content=text,
                task_type="retrieval_query"
            )
            return result["embedding"]
        else:
            import numpy as np
            emb = self.model.encode(text, normalize_embeddings=True)
            return emb.tolist()

    def embed_batch(self, texts: List[str], task_type: str = "retrieval_document") -> List[List[float]]:
        if self.embedding_provider == "gemini":
            # Gemini batch: tối đa 100 texts/call
            all_embeddings = []
            batch_size = 100
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                result = self._genai.embed_content(
                    model=self._gemini_embed_model,
                    content=batch,
                    task_type=task_type
                )
                all_embeddings.extend(result["embedding"])
            return all_embeddings
        else:
            embeddings = self.model.encode(
                texts, normalize_embeddings=True,
                batch_size=32,
                show_progress_bar=len(texts) > 50
            )
            return embeddings.tolist()

    # ── Add Documents ──────────────────────────────────────────────
    def add_documents(self, chunks: List[Dict[str, Any]],
                      batch_size: int = 100) -> Dict[str, Any]:
        if not chunks:
            return {"added": 0, "skipped": 0}

        existing_ids = set(self.collection.get()["ids"])
        new_chunks = [c for c in chunks if c["id"] not in existing_ids]
        skipped = len(chunks) - len(new_chunks)

        if not new_chunks:
            return {"added": 0, "skipped": skipped}

        logger.info(f"Tạo embedding cho {len(new_chunks)} chunks...")
        total_added = 0

        for i in range(0, len(new_chunks), batch_size):
            batch = new_chunks[i:i + batch_size]
            ids = [c["id"] for c in batch]
            texts = [c["content"] for c in batch]
            metadatas = [self._sanitize_metadata(c["metadata"]) for c in batch]
            embeddings = self.embed_batch(texts, task_type="retrieval_document")

            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )
            total_added += len(batch)
            logger.info(f"  Đã lưu {total_added}/{len(new_chunks)} chunks")

        return {"added": total_added, "skipped": skipped,
                "total_in_db": self.collection.count()}

    # ── Search ─────────────────────────────────────────────────────
    def search(self, query: Optional[str] = None, top_k: int = 5,
               where: Optional[Dict] = None, query_embedding: Optional[List[float]] = None) -> List[Dict[str, Any]]:
        if self.collection.count() == 0:
            return []

        if query_embedding is None:
            if query is None:
                raise ValueError("Phải cung cấp query hoặc query_embedding")
            query_embedding = self.embed_text(query)
            
        n = min(top_k, self.collection.count())

        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        documents = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                documents.append({
                    "content": doc,
                    "metadata": meta,
                    "score": round(1 - dist, 4),
                })
        return documents

    # ── Delete ─────────────────────────────────────────────────────
    def delete_documents_by_file(self, file_name: str) -> int:
        results = self.collection.get(
            where={"file_name": file_name}, include=["ids"])
        # ids trả về trực tiếp dưới dạng list trong phiên bản mới hơn
        ids = results.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
            logger.info(f"Đã xóa {len(ids)} chunks của: {file_name}")
        return len(ids)

    # ── Stats ──────────────────────────────────────────────────────
    def get_stats(self) -> Dict[str, Any]:
        count = self.collection.count()
        if count == 0:
            return {"total_chunks": 0, "total_files": 0,
                    "files": [], "model": self.model_name,
                    "embedding_provider": self.embedding_provider}

        all_items = self.collection.get(include=["metadatas"])
        files = {m["file_name"] for m in all_items.get("metadatas", [])
                 if m and "file_name" in m}

        return {
            "total_chunks": count,
            "total_files": len(files),
            "files": sorted(files),
            "model": self.model_name,
            "embedding_provider": self.embedding_provider,
        }

    def _sanitize_metadata(self, metadata: Dict) -> Dict:
        sanitized = {}
        for k, v in metadata.items():
            if isinstance(v, (str, int, float, bool)):
                sanitized[k] = v
            elif v is None:
                sanitized[k] = ""
            else:
                sanitized[k] = str(v)
        return sanitized
