import logging
import os
from typing import Dict, Any, List
from pathlib import Path

from core.document_loader import DocumentLoader
from core.text_cleaner import TextCleaner
from core.text_chunker import TextChunker
from core.embedding_manager import EmbeddingManager
from core.config import settings

logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(self, embedding_manager: EmbeddingManager):
        self.loader = DocumentLoader()
        self.cleaner = TextCleaner()
        self.chunker = TextChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            embedding_manager=embedding_manager
        )
        self.embedding_manager = embedding_manager
        
        logger.info("IngestionPipeline khởi tạo")
    
    def ingest_file(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        logger.info(f"=== Bắt đầu ingest: {path.name} ===")
        
        result = {
            "file": path.name,
            "file_path": str(path),
            "documents_loaded": 0,
            "chunks_created": 0,
            "vectors_added": 0,
            "vectors_skipped": 0,
            "chunk_stats": {}
        }
        
        try:
            # Step 1 & 2: Load và làm sạch
            logger.info(f"[1/3] Loading: {path.name}")
            raw_documents = self.loader.load_file(file_path)
            documents = self.cleaner.clean_documents(raw_documents)
            result["documents_loaded"] = len(documents)
            
            if not documents:
                logger.warning(f"Không có nội dung từ: {path.name}")
                return result
            
            # Step 3: Chia chunk
            logger.info(f"[2/3] Chia chunk ({len(documents)} documents)")
            chunks = self.chunker.split_documents(documents)
            result["chunks_created"] = len(chunks)
            result["chunk_stats"] = self.chunker.get_stats(chunks)
            
            if not chunks:
                logger.warning(f"Không tạo được chunk từ: {path.name}")
                return result
            
            # Step 4 & 5: Embed và lưu
            logger.info(f"[3/3] Tạo embedding và lưu ({len(chunks)} chunks)")
            store_result = self.embedding_manager.add_documents(chunks)
            result["vectors_added"] = store_result["added"]
            result["vectors_skipped"] = store_result["skipped"]
            
            logger.info(
                f"=== Hoàn tất {path.name}: "
                f"{result['documents_loaded']} docs, "
                f"{result['chunks_created']} chunks, "
                f"{result['vectors_added']} vectors added ==="
            )
            
        except Exception as e:
            logger.error(f"Lỗi khi ingest {path.name}: {e}")
            result["error"] = str(e)
            raise
        
        return result
    
    def ingest_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        """Nạp tất cả file trong thư mục"""
        dir_path = Path(dir_path)
        results = []
        
        supported_files = [
            f for f in dir_path.rglob("*")
            if f.suffix.lower() in DocumentLoader.SUPPORTED_EXTENSIONS
        ]
        
        logger.info(f"Tìm thấy {len(supported_files)} file trong {dir_path}")
        
        for file_path in supported_files:
            try:
                result = self.ingest_file(str(file_path))
                results.append(result)
            except Exception as e:
                results.append({
                    "file": file_path.name,
                    "error": str(e)
                })
        
        return results
    
    def reingest_file(self, file_path: str) -> Dict[str, Any]:
        """Xóa và nạp lại một file"""
        path = Path(file_path)
        
        # Xóa chunks cũ
        deleted = self.embedding_manager.delete_documents_by_file(path.name)
        logger.info(f"Đã xóa {deleted} chunks cũ của {path.name}")
        
        # Nạp lại
        return self.ingest_file(file_path)
