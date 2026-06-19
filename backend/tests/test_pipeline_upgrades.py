import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.text_cleaner import TextCleaner
from core.text_chunker import TextChunker
from core.config import settings
import core.chat_history as ch


class TestPipelineUpgrades:
    def test_text_cleaner(self):
        cleaner = TextCleaner()
        # Test Unicode normalization (NFC)
        text = "A\u030a"
        cleaned = cleaner.clean_text(text)
        assert cleaned == "Å"
        
        # Test null and control character removal
        text_with_control = "hello\x00world\x0e!"
        assert cleaner.clean_text(text_with_control) == "helloworld!"
        
        # Test whitespace trim
        text_whitespace = "  hello   world  \n\n\n  foo  "
        assert cleaner.clean_text(text_whitespace) == "hello world\n\nfoo"
        
        # Test clean_documents
        docs = [{"content": "  hello  "}, {"content": ""}]
        cleaned_docs = cleaner.clean_documents(docs)
        assert len(cleaned_docs) == 1
        assert cleaned_docs[0]["content"] == "hello"

    def test_chunking_strategies(self):
        # 1. Token chunking strategy (default)
        settings.chunking_strategy = "token"
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        doc = {"content": "Hello standard token chunker. " * 5, "metadata": {"file_name": "test.txt"}}
        chunks = chunker.split_documents([doc])
        assert len(chunks) > 0
        
        # 2. Semantic chunking strategy (mocking embedding_manager)
        settings.chunking_strategy = "semantic"
        mock_embedding_manager = MagicMock()
        # Mock embed_batch: trả về các vector mô phỏng
        mock_embedding_manager.embed_batch.return_value = [
            [1.0, 0.0],  # s1
            [1.0, 0.0],  # s2 (giống s1)
            [0.0, 1.0],  # s3 (khác hoàn toàn)
            [0.0, 1.0],  # s4 (giống s3)
        ]
        
        chunker_semantic = TextChunker(chunk_size=1000, chunk_overlap=0, embedding_manager=mock_embedding_manager)
        text = "Câu thứ nhất. Câu thứ hai tương tự. Nhưng câu thứ ba đổi chủ đề. Câu thứ tư giống câu ba."
        
        doc_semantic = {"content": text, "metadata": {"file_name": "semantic.txt"}}
        chunks_semantic = chunker_semantic.split_documents([doc_semantic])
        
        assert len(chunks_semantic) > 0
        # Reset settings
        settings.chunking_strategy = "token"

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test_history.db")
        monkeypatch.setattr(ch.settings, "sqlite_db_path", db_path)
        ch.init_db()

    def test_chat_history_limit(self):
        conv = ch.create_conversation("History limit test")
        cid = conv["id"]
        
        # Thêm 15 tin nhắn vào lịch sử
        for i in range(15):
            ch.add_message(cid, "user" if i % 2 == 0 else "assistant", f"Message {i}")
            
        # Lấy toàn bộ lịch sử không giới hạn
        all_msgs = ch.get_messages(cid)
        assert len(all_msgs) == 15
        
        # Lấy lịch sử với giới hạn 10 tin
        limited_msgs = ch.get_messages(cid, limit=10)
        assert len(limited_msgs) == 10
        # Đảm bảo thứ tự thời gian tăng dần (ASC) từ Message 5 đến Message 14
        assert limited_msgs[0]["content"] == "Message 5"
        assert limited_msgs[-1]["content"] == "Message 14"

    def test_reranker_mock(self):
        # Mock CrossEncoder
        with patch("sentence_transformers.CrossEncoder") as mock_encoder_cls:
            mock_encoder = MagicMock()
            mock_encoder.predict.return_value = [0.1, 0.9, 0.5]
            mock_encoder_cls.return_value = mock_encoder
            
            # Mô phỏng settings use_reranker = True
            with patch.object(settings, "use_reranker", True), \
                 patch.object(settings, "reranker_top_n", 2):
                 
                from core.rag_engine import RAGEngine
                mock_em = MagicMock()
                engine = RAGEngine(mock_em)
                
                assert engine.reranker is not None
                
                docs = [
                    {"content": "Tài liệu 1", "score": 0.8, "metadata": {}},
                    {"content": "Tài liệu 2", "score": 0.7, "metadata": {}},
                    {"content": "Tài liệu 3", "score": 0.6, "metadata": {}},
                ]
                
                reranked = engine.rerank("Query", docs)
                # Chỉ giữ lại top_n = 2
                assert len(reranked) == 2
                # Tài liệu 2 có điểm dự đoán cao nhất (0.9), nên lên đầu
                assert reranked[0]["content"] == "Tài liệu 2"
                assert reranked[0]["score"] == 0.9
                # Tài liệu 3 có điểm dự đoán 0.5, đứng thứ hai
                assert reranked[1]["content"] == "Tài liệu 3"
                assert reranked[1]["score"] == 0.5
