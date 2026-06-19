import os
import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel

from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class DocumentInfo(BaseModel):
    file_name: str
    file_size: int
    file_type: str


class IngestResult(BaseModel):
    file: str
    documents_loaded: int = 0
    chunks_created: int = 0
    vectors_added: int = 0
    vectors_skipped: int = 0
    status: str = "success"
    error: str = None


class DBStats(BaseModel):
    total_chunks: int
    total_files: int
    files: List[str]
    model: str


def get_pipeline():
    from main import ingestion_pipeline
    if ingestion_pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline chưa được khởi tạo.")
    return ingestion_pipeline


def get_em():
    from main import embedding_manager
    if embedding_manager is None:
        raise HTTPException(status_code=503, detail="Embedding manager chưa khởi tạo.")
    return embedding_manager


@router.post("/upload", response_model=IngestResult)
async def upload_document(file: UploadFile = File(...), pipeline=Depends(get_pipeline)):
    """Upload và tự động chạy RAG pipeline"""
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ: {ext}. Chấp nhận: {', '.join(settings.allowed_extensions)}"
        )
    content = await file.read()
    if len(content) > settings.max_file_size:
        raise HTTPException(status_code=400,
                            detail=f"File quá lớn. Tối đa {settings.max_file_size // 1024 // 1024}MB")

    file_path = Path(settings.upload_dir) / file.filename
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        result = pipeline.ingest_file(str(file_path))
        result["status"] = "success"
        return IngestResult(**result)
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents", response_model=List[DocumentInfo])
async def list_documents():
    """Danh sách tài liệu đã upload"""
    upload_dir = Path(settings.upload_dir)
    docs = []
    for p in upload_dir.iterdir():
        if p.suffix.lower() in settings.allowed_extensions:
            docs.append(DocumentInfo(
                file_name=p.name,
                file_size=p.stat().st_size,
                file_type=p.suffix.lower()
            ))
    return sorted(docs, key=lambda x: x.file_name)


@router.delete("/documents/{file_name}")
async def delete_document(file_name: str, em=Depends(get_em)):
    """Xóa tài liệu và vectors tương ứng"""
    file_path = Path(settings.upload_dir) / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File không tồn tại: {file_name}")
    deleted_vectors = em.delete_documents_by_file(file_name)
    file_path.unlink()
    return {"message": f"Đã xóa {file_name}", "vectors_deleted": deleted_vectors}


@router.post("/documents/{file_name}/reingest", response_model=IngestResult)
async def reingest_document(file_name: str, pipeline=Depends(get_pipeline)):
    """Xóa và nạp lại tài liệu"""
    file_path = Path(settings.upload_dir) / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File không tồn tại: {file_name}")
    result = pipeline.reingest_file(str(file_path))
    result["status"] = "success"
    return IngestResult(**result)


@router.get("/stats", response_model=DBStats)
async def get_stats(em=Depends(get_em)):
    """Thống kê vector database"""
    return DBStats(**em.get_stats())
