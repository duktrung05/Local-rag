import re
import os
import csv
from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DocumentLoader:
    """Load và làm sạch nội dung tài liệu từ nhiều định dạng"""
    
    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx", ".md", ".csv"}
    
    def load_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load một file và trả về list các document chunks với metadata
        
        Returns:
            List[Dict]: [{"content": str, "metadata": dict}, ...]
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File không tồn tại: {file_path}")
        
        ext = path.suffix.lower()
        
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Định dạng không hỗ trợ: {ext}")
        
        logger.info(f"Loading file: {path.name} ({ext})")
        
        loaders = {
            ".pdf": self._load_pdf,
            ".txt": self._load_text,
            ".md": self._load_text,
            ".docx": self._load_docx,
            ".csv": self._load_csv,
        }
        
        raw_docs = loaders[ext](str(path))
        
        # Gán metadata cho từng document thô
        loaded_docs = []
        for doc in raw_docs:
            if doc["content"].strip():  # Bỏ qua doc rỗng
                doc["metadata"]["file_name"] = path.name
                doc["metadata"]["file_path"] = str(path)
                doc["metadata"]["file_type"] = ext
                loaded_docs.append(doc)
        
        logger.info(f"Loaded {len(loaded_docs)} documents từ {path.name}")
        return loaded_docs
    
    def load_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        """Load tất cả file được hỗ trợ trong thư mục"""
        dir_path = Path(dir_path)
        all_docs = []
        
        for file_path in dir_path.rglob("*"):
            if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                try:
                    docs = self.load_file(str(file_path))
                    all_docs.extend(docs)
                except Exception as e:
                    logger.error(f"Lỗi khi load {file_path}: {e}")
        
        return all_docs
    
    def _load_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """Load file PDF"""
        try:
            from pypdf import PdfReader
            
            reader = PdfReader(file_path)
            docs = []
            
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    docs.append({
                        "content": text,
                        "metadata": {
                            "page": i + 1,
                            "total_pages": len(reader.pages),
                            "source": file_path
                        }
                    })
            
            return docs
        except Exception as e:
            logger.error(f"Lỗi load PDF: {e}")
            raise
    
    def _load_text(self, file_path: str) -> List[Dict[str, Any]]:
        """Load file TXT hoặc MD"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            return [{
                "content": content,
                "metadata": {"source": file_path}
            }]
        except Exception as e:
            logger.error(f"Lỗi load text file: {e}")
            raise
    
    def _load_docx(self, file_path: str) -> List[Dict[str, Any]]:
        """Load file DOCX"""
        try:
            from docx import Document
            
            doc = Document(file_path)
            paragraphs = []
            
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)
            
            # Gộp thành các section
            content = "\n\n".join(paragraphs)
            
            return [{
                "content": content,
                "metadata": {"source": file_path}
            }]
        except Exception as e:
            logger.error(f"Lỗi load DOCX: {e}")
            raise
    
    def _load_csv(self, file_path: str) -> List[Dict[str, Any]]:
        """Load file CSV - mỗi row là một document"""
        try:
            docs = []
            
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                
                for i, row in enumerate(reader):
                    # Convert row to readable text
                    content = " | ".join([f"{k}: {v}" for k, v in row.items() if v])
                    
                    if content.strip():
                        docs.append({
                            "content": content,
                            "metadata": {
                                "row": i + 1,
                                "source": file_path,
                                "columns": ", ".join(headers)
                            }
                        })
            
            return docs
        except Exception as e:
            logger.error(f"Lỗi load CSV: {e}")
            raise
    

