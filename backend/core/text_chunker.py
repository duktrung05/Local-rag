from typing import List, Dict, Any, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging
import hashlib
import re
import numpy as np

logger = logging.getLogger(__name__)


class TextChunker:
    """Chia văn bản thành các chunk phù hợp để embedding"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, embedding_manager: Optional[Any] = None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_manager = embedding_manager
        
        # Separators hỗ trợ tiếng Việt
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",    # Paragraph
                "\n",      # Line break
                ".",       # Sentence end (English)
                "。",      # Sentence end (CJK)
                "!",
                "?",
                "！",
                "？",
                ";",
                "；",
                ",",
                "，",
                " ",
                ""
            ],
            length_function=len,
            is_separator_regex=False,
        )
        
        logger.info(
            f"TextChunker khởi tạo: chunk_size={chunk_size}, overlap={chunk_overlap}, "
            f"has_embedding_manager={embedding_manager is not None}"
        )
    
    def split_documents(
        self, 
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Chia list documents thành chunks
        
        Args:
            documents: List[{"content": str, "metadata": dict}]
        
        Returns:
            List[{"id": str, "content": str, "metadata": dict}]
        """
        all_chunks = []
        
        for doc in documents:
            chunks = self._split_single_doc(doc)
            all_chunks.extend(chunks)
        
        logger.info(
            f"Chia {len(documents)} documents thành {len(all_chunks)} chunks"
        )
        
        return all_chunks
    
    def _split_single_doc(
        self, 
        document: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Chia một document thành nhiều chunks"""
        content = document.get("content", "")
        metadata = document.get("metadata", {}).copy()
        
        if not content.strip():
            return []
        
        # Chia text
        from core.config import settings
        if settings.chunking_strategy == "semantic" and self.embedding_manager is not None:
            text_chunks = self._semantic_chunk_text(content)
        else:
            text_chunks = self.splitter.split_text(content)
        
        chunks = []
        for i, chunk_text in enumerate(text_chunks):
            if not chunk_text.strip():
                continue
            
            # Tạo unique ID cho chunk
            chunk_id = self._generate_chunk_id(
                metadata.get("file_name", "unknown"),
                metadata.get("page", 0),
                i,
                chunk_text
            )
            
            # Metadata cho chunk
            chunk_metadata = {
                **metadata,
                "chunk_index": i,
                "total_chunks": len(text_chunks),
                "chunk_size": len(chunk_text),
            }
            
            chunks.append({
                "id": chunk_id,
                "content": chunk_text,
                "metadata": chunk_metadata
            })
        
        return chunks
    
    def _generate_chunk_id(
        self, 
        file_name: str, 
        page: int, 
        chunk_idx: int,
        content: str
    ) -> str:
        """Tạo ID duy nhất cho chunk dựa trên nội dung"""
        hash_input = f"{file_name}_{page}_{chunk_idx}_{content[:100]}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def get_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Thống kê về các chunks"""
        if not chunks:
            return {"total": 0}
        
        sizes = [len(c["content"]) for c in chunks]
        
        return {
            "total_chunks": len(chunks),
            "avg_chunk_size": sum(sizes) / len(sizes),
            "min_chunk_size": min(sizes),
            "max_chunk_size": max(sizes),
            "total_characters": sum(sizes)
        }

    def _semantic_chunk_text(self, text: str) -> List[str]:
        """Chia văn bản dựa theo độ tương đồng ngữ nghĩa (Semantic Chunking)"""
        if not text.strip():
            return []
            
        # 1. Tách văn bản thành các câu dùng regex
        # Hỗ trợ dấu chấm, hỏi, cảm thán (cả VN/EN và CJK) và newline theo sau
        raw_sentences = re.split(r'(?<=[.!?。！？\n])\s+', text)
        sentences = [s.strip() for s in raw_sentences if s.strip()]
        
        if not sentences:
            return []
        if len(sentences) == 1:
            return sentences
            
        # 2. Tạo embedding cho từng câu
        try:
            embeddings = self.embedding_manager.embed_batch(sentences, task_type="retrieval_document")
        except Exception as e:
            logger.warning(f"Lỗi khi embed các câu cho Semantic Chunking, fallback sang token chunking: {e}")
            return self.splitter.split_text(text)
            
        # 3. Tính độ tương đồng cosine giữa các câu kề nhau
        similarities = []
        for i in range(len(embeddings) - 1):
            v1 = np.array(embeddings[i])
            v2 = np.array(embeddings[i+1])
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 == 0 or norm2 == 0:
                sim = 0.0
            else:
                sim = float(np.dot(v1, v2) / (norm1 * norm2))
            similarities.append(sim)
            
        # 4. Xác định các điểm ngắt (split points) tại các điểm tương đồng giảm sâu
        # Dùng khoảng cách (distance = 1.0 - similarity)
        distances = [1.0 - sim for sim in similarities]
        
        # Ngưỡng phân vị (80th percentile của distance làm mặc định)
        if distances:
            threshold = np.percentile(distances, 80)
            split_indices = {i for i, d in enumerate(distances) if d >= threshold}
        else:
            split_indices = set()
            
        # 5. Gom cụm các câu thành các chunk đảm bảo kích thước không vượt quá chunk_size
        chunks = []
        current_chunk = []
        current_len = 0
        
        for i, sentence in enumerate(sentences):
            # Nếu bản thân câu đó quá dài hơn chunk_size, dùng splitter thường chia nhỏ nó
            if len(sentence) > self.chunk_size:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_len = 0
                
                sub_chunks = self.splitter.split_text(sentence)
                chunks.extend(sub_chunks)
                continue
                
            sentence_len = len(sentence)
            
            # Nếu thêm câu này vượt quá chunk_size HOẶC câu trước đó là điểm ngắt ngữ nghĩa
            if current_chunk and (current_len + sentence_len > self.chunk_size or (i - 1) in split_indices):
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_len = sentence_len
            else:
                current_chunk.append(sentence)
                current_len += sentence_len + (1 if current_len > 0 else 0)
                
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return chunks
