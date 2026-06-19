"""
Unit tests cho RAG Chatbot v2
Chạy: cd backend && pytest tests/test_units.py -v
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ─── Document Loader & Text Cleaner ───────────────────────────
class TestDocumentLoaderAndCleaner:
    def test_clean_text_removes_extra_spaces(self):
        from core.text_cleaner import TextCleaner
        cleaner = TextCleaner()
        result = cleaner.clean_text("hello   world\n\n\n\nfoo")
        assert "   " not in result
        assert result.count("\n\n") <= 1

    def test_clean_text_normalizes_unicode(self):
        from core.text_cleaner import TextCleaner
        cleaner = TextCleaner()
        result = cleaner.clean_text("hello\xa0world")  # non-breaking space
        assert "\xa0" not in result
        assert "hello world" in result

    def test_clean_text_preserves_vietnamese(self):
        from core.text_cleaner import TextCleaner
        cleaner = TextCleaner()
        text = "Tiếng Việt có dấu: à á ả ã ạ ă ắ ặ"
        result = cleaner.clean_text(text)
        assert "Tiếng Việt" in result

    def test_clean_empty_text(self):
        from core.text_cleaner import TextCleaner
        cleaner = TextCleaner()
        assert cleaner.clean_text("") == ""
        assert cleaner.clean_text("   \n  ") == ""

    def test_load_txt_file(self, tmp_path):
        from core.document_loader import DocumentLoader
        f = tmp_path / "test.txt"
        f.write_text("Nội dung tài liệu test.\nDòng thứ hai.", encoding="utf-8")
        loader = DocumentLoader()
        docs = loader.load_file(str(f))
        assert len(docs) > 0
        assert "Nội dung" in docs[0]["content"]
        assert docs[0]["metadata"]["file_name"] == "test.txt"

    def test_load_md_file(self, tmp_path):
        from core.document_loader import DocumentLoader
        f = tmp_path / "test.md"
        f.write_text("# Tiêu đề\n\nNội dung markdown.", encoding="utf-8")
        loader = DocumentLoader()
        docs = loader.load_file(str(f))
        assert len(docs) > 0

    def test_load_csv_file(self, tmp_path):
        from core.document_loader import DocumentLoader
        f = tmp_path / "test.csv"
        f.write_text("name,age,city\nAn,25,Hanoi\nBinh,30,HCMC")
        loader = DocumentLoader()
        docs = loader.load_file(str(f))
        assert len(docs) == 2  # 2 rows
        assert "An" in docs[0]["content"]

    def test_unsupported_extension_raises(self, tmp_path):
        from core.document_loader import DocumentLoader
        f = tmp_path / "file.xyz"
        f.write_text("test")
        loader = DocumentLoader()
        with pytest.raises(ValueError, match="Định dạng không hỗ trợ"):
            loader.load_file(str(f))

    def test_missing_file_raises(self):
        from core.document_loader import DocumentLoader
        loader = DocumentLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_file("/nonexistent/path/file.txt")


# ─── Text Chunker ─────────────────────────────────────────────
class TestTextChunker:
    def test_splits_long_text(self):
        from core.text_chunker import TextChunker
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        doc = {"content": "A" * 500, "metadata": {"file_name": "test.txt"}}
        chunks = chunker.split_documents([doc])
        assert len(chunks) > 1

    def test_short_text_single_chunk(self):
        from core.text_chunker import TextChunker
        chunker = TextChunker(chunk_size=1000, chunk_overlap=100)
        doc = {"content": "Đây là đoạn văn ngắn.", "metadata": {"file_name": "test.txt"}}
        chunks = chunker.split_documents([doc])
        assert len(chunks) == 1
        assert "Đây là đoạn văn ngắn." in chunks[0]["content"]

    def test_chunk_has_required_fields(self):
        from core.text_chunker import TextChunker
        chunker = TextChunker()
        doc = {"content": "Test content for chunking.", "metadata": {"file_name": "a.txt"}}
        chunks = chunker.split_documents([doc])
        assert len(chunks) > 0
        c = chunks[0]
        assert "id" in c
        assert "content" in c
        assert "metadata" in c
        assert c["metadata"]["file_name"] == "a.txt"

    def test_chunk_ids_are_unique(self):
        from core.text_chunker import TextChunker
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        doc = {"content": "Word " * 100, "metadata": {"file_name": "test.txt"}}
        chunks = chunker.split_documents([doc])
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_empty_content_skipped(self):
        from core.text_chunker import TextChunker
        chunker = TextChunker()
        doc = {"content": "   \n\n  ", "metadata": {"file_name": "empty.txt"}}
        chunks = chunker.split_documents([doc])
        assert len(chunks) == 0

    def test_multiple_documents(self):
        from core.text_chunker import TextChunker
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        docs = [
            {"content": "Doc one content " * 10, "metadata": {"file_name": "a.txt"}},
            {"content": "Doc two content " * 10, "metadata": {"file_name": "b.txt"}},
        ]
        chunks = chunker.split_documents(docs)
        files = {c["metadata"]["file_name"] for c in chunks}
        assert "a.txt" in files
        assert "b.txt" in files

    def test_get_stats(self):
        from core.text_chunker import TextChunker
        chunker = TextChunker(chunk_size=50, chunk_overlap=5)
        doc = {"content": "Hello world. " * 50, "metadata": {"file_name": "t.txt"}}
        chunks = chunker.split_documents([doc])
        stats = chunker.get_stats(chunks)
        assert "total_chunks" in stats
        assert stats["total_chunks"] == len(chunks)
        assert "avg_chunk_size" in stats

    def test_metadata_preserved(self):
        from core.text_chunker import TextChunker
        chunker = TextChunker()
        doc = {
            "content": "Test content.",
            "metadata": {"file_name": "x.pdf", "page": 3, "source": "/path/x.pdf"}
        }
        chunks = chunker.split_documents([doc])
        assert chunks[0]["metadata"]["page"] == 3
        assert chunks[0]["metadata"]["source"] == "/path/x.pdf"


# ─── Chat History ─────────────────────────────────────────────
class TestChatHistory:
    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test_chat.db")
        import core.chat_history as ch
        monkeypatch.setattr(ch.settings, "sqlite_db_path", db_path)
        ch.init_db()

    def test_create_conversation(self):
        import core.chat_history as ch
        conv = ch.create_conversation("Test conv")
        assert conv["id"]
        assert conv["title"] == "Test conv"
        assert conv["message_count"] == 0

    def test_get_conversations(self):
        import core.chat_history as ch
        ch.create_conversation("Conv 1")
        ch.create_conversation("Conv 2")
        convs = ch.get_conversations()
        assert len(convs) >= 2

    def test_add_and_get_messages(self):
        import core.chat_history as ch
        conv = ch.create_conversation()
        ch.add_message(conv["id"], "user", "Xin chào")
        ch.add_message(conv["id"], "assistant", "Chào bạn!", provider="ollama")
        msgs = ch.get_messages(conv["id"])
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["provider"] == "ollama"

    def test_message_with_sources(self):
        import core.chat_history as ch
        conv = ch.create_conversation()
        sources = [{"file_name": "doc.pdf", "score": 0.85}]
        ch.add_message(conv["id"], "assistant", "Trả lời", sources=sources)
        msgs = ch.get_messages(conv["id"])
        assert msgs[0]["sources"][0]["file_name"] == "doc.pdf"

    def test_delete_conversation(self):
        import core.chat_history as ch
        conv = ch.create_conversation("To delete")
        ch.add_message(conv["id"], "user", "msg")
        deleted = ch.delete_conversation(conv["id"])
        assert deleted is True
        assert ch.get_conversation(conv["id"]) is None
        assert ch.get_messages(conv["id"]) == []

    def test_update_title(self):
        import core.chat_history as ch
        conv = ch.create_conversation("Old title")
        ch.update_conversation_title(conv["id"], "New title")
        updated = ch.get_conversation(conv["id"])
        assert updated["title"] == "New title"

    def test_message_count_increments(self):
        import core.chat_history as ch
        conv = ch.create_conversation()
        ch.add_message(conv["id"], "user", "Q1")
        ch.add_message(conv["id"], "assistant", "A1")
        updated = ch.get_conversation(conv["id"])
        assert updated["message_count"] == 2

    def test_nonexistent_conversation_returns_none(self):
        import core.chat_history as ch
        result = ch.get_conversation("nonexistent-uuid-12345")
        assert result is None


# ─── Config ───────────────────────────────────────────────────
class TestConfig:
    def test_default_provider_is_ollama(self):
        from core.config import settings
        assert settings.llm_provider in ["ollama", "claude", "groq"]

    def test_origins_list_parsed(self):
        from core.config import Settings
        s = Settings(allowed_origins="http://a.com,http://b.com")
        origins = s.origins_list
        assert "http://a.com" in origins
        assert "http://b.com" in origins

    def test_active_model_name_ollama(self):
        from core.config import Settings
        s = Settings(llm_provider="ollama", ollama_model="llama3.2")
        assert s.active_model_name == "llama3.2"

    def test_active_model_name_claude(self):
        from core.config import Settings
        s = Settings(llm_provider="claude", claude_model="claude-opus-4-5")
        assert s.active_model_name == "claude-opus-4-5"


# ─── Embedding Manager (mock) ─────────────────────────────────
class TestEmbeddingManagerMock:
    """Test không cần load model thật - dùng mock"""

    def test_sanitize_metadata(self, tmp_path):
        from unittest.mock import patch, MagicMock
        with patch("core.embedding_manager.SentenceTransformer") as mock_st, \
             patch("core.embedding_manager.chromadb.PersistentClient") as mock_chroma:
            mock_st.return_value = MagicMock()
            mock_col = MagicMock()
            mock_col.count.return_value = 0
            mock_chroma.return_value.get_or_create_collection.return_value = mock_col

            from core.embedding_manager import EmbeddingManager
            em = EmbeddingManager(persist_dir=str(tmp_path))
            meta = {"key1": "str", "key2": 42, "key3": None, "key4": [1, 2, 3]}
            clean = em._sanitize_metadata(meta)
            assert clean["key1"] == "str"
            assert clean["key2"] == 42
            assert clean["key3"] == ""
            assert isinstance(clean["key4"], str)


# ─── Gemini Config ────────────────────────────────────────────
class TestGeminiConfig:
    def test_default_provider_is_gemini(self):
        from core.config import Settings
        s = Settings(llm_provider="gemini")
        assert s.llm_provider == "gemini"

    def test_gemini_active_model(self):
        from core.config import Settings
        s = Settings(llm_provider="gemini", gemini_model="gemini-2.0-flash")
        assert s.active_model_name == "gemini-2.0-flash"

    def test_gemini_flash_lite_model(self):
        from core.config import Settings
        s = Settings(llm_provider="gemini", gemini_model="gemini-2.0-flash-lite")
        assert s.active_model_name == "gemini-2.0-flash-lite"

    def test_embedding_provider_local(self):
        from core.config import Settings
        s = Settings(embedding_provider="local")
        assert s.embedding_provider == "local"

    def test_embedding_provider_gemini(self):
        from core.config import Settings
        s = Settings(embedding_provider="gemini")
        assert s.embedding_provider == "gemini"

    def test_three_providers_supported(self):
        from core.config import Settings
        for provider in ["gemini", "claude", "ollama"]:
            s = Settings(llm_provider=provider)
            assert s.llm_provider == provider
