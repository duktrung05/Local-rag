#!/usr/bin/env python3
"""
Script CLI để nạp tài liệu vào hệ thống
Dùng: python scripts/ingest.py --file path/to/file.pdf
       python scripts/ingest.py --dir path/to/directory
"""
import sys
import argparse
import logging
from pathlib import Path

# Thêm backend vào path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from core.config import settings
from core.embedding_manager import EmbeddingManager
from core.ingestion_pipeline import IngestionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Nạp tài liệu vào RAG Chatbot"
    )
    parser.add_argument("--file", help="Đường dẫn đến file")
    parser.add_argument("--dir", help="Đường dẫn đến thư mục chứa tài liệu")
    parser.add_argument("--reingest", action="store_true", help="Nạp lại (xóa dữ liệu cũ)")
    parser.add_argument("--stats", action="store_true", help="Xem thống kê database")
    
    args = parser.parse_args()
    
    # Khởi tạo
    print("🔄 Đang khởi tạo hệ thống...")
    em = EmbeddingManager(
        model_name=settings.embedding_model,
        persist_dir=settings.chroma_persist_dir,
        collection_name=settings.chroma_collection_name
    )
    pipeline = IngestionPipeline(em)
    
    if args.stats:
        stats = em.get_stats()
        print("\n📊 Thống kê Vector Database:")
        print(f"   - Tổng chunks: {stats['total_chunks']}")
        print(f"   - Tổng files: {stats.get('total_files', 0)}")
        print(f"   - Files: {', '.join(stats.get('files', []))}")
        print(f"   - Model: {stats['model']}")
        return
    
    if not args.file and not args.dir:
        parser.print_help()
        sys.exit(1)
    
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ File không tồn tại: {args.file}")
            sys.exit(1)
        
        print(f"\n📄 Đang xử lý: {file_path.name}")
        
        if args.reingest:
            result = pipeline.reingest_file(str(file_path))
        else:
            result = pipeline.ingest_file(str(file_path))
        
        print(f"\n✅ Hoàn tất!")
        print(f"   - Documents loaded: {result['documents_loaded']}")
        print(f"   - Chunks created: {result['chunks_created']}")
        print(f"   - Vectors added: {result['vectors_added']}")
        print(f"   - Vectors skipped: {result['vectors_skipped']}")
    
    elif args.dir:
        dir_path = Path(args.dir)
        if not dir_path.exists():
            print(f"❌ Thư mục không tồn tại: {args.dir}")
            sys.exit(1)
        
        print(f"\n📁 Đang xử lý thư mục: {dir_path}")
        results = pipeline.ingest_directory(str(dir_path))
        
        print(f"\n✅ Hoàn tất {len(results)} files!")
        total_chunks = sum(r.get('chunks_created', 0) for r in results)
        total_vectors = sum(r.get('vectors_added', 0) for r in results)
        
        for r in results:
            status = "✅" if 'error' not in r else "❌"
            print(f"   {status} {r['file']}: {r.get('chunks_created', 0)} chunks")
        
        print(f"\n📊 Tổng: {total_chunks} chunks, {total_vectors} vectors mới")


if __name__ == "__main__":
    main()
