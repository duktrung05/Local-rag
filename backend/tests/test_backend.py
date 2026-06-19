"""
Test tự động backend với pytest
Chạy: cd backend && pytest tests/ -v
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from unittest.mock import patch, MagicMock
    # Mock SentenceTransformer và CrossEncoder để chạy offline và tránh tải model thật
    with patch("sentence_transformers.SentenceTransformer") as mock_st, \
         patch("sentence_transformers.CrossEncoder") as mock_ce:
         
        import numpy as np
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1] * 384)
        mock_st.return_value = mock_model
        
        mock_ce_model = MagicMock()
        mock_ce_model.predict.return_value = [0.9]
        mock_ce.return_value = mock_ce_model
        
        from main import app
        # Chạy trong context manager để kích hoạt lifespan events (bao gồm tạo bảng SQLite)
        with TestClient(app) as c:
            yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "provider" in data
    assert "db_stats" in data


def test_list_documents(client):
    r = client.get("/api/documents")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_db_stats(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total_chunks" in data
    assert "total_files" in data


def test_create_conversation(client):
    r = client.post("/api/conversations?title=Test+conv")
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["title"] == "Test conv"
    return data["id"]


def test_list_conversations(client):
    r = client.get("/api/conversations")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_messages_empty(client):
    # Tạo conversation rồi lấy messages
    conv = client.post("/api/conversations?title=Msg+test").json()
    conv_id = conv["id"]
    r = client.get(f"/api/conversations/{conv_id}/messages")
    assert r.status_code == 200
    assert r.json() == []


def test_update_conversation_title(client):
    conv = client.post("/api/conversations?title=Old").json()
    conv_id = conv["id"]
    r = client.patch(f"/api/conversations/{conv_id}/title",
                     json={"title": "New Title"})
    assert r.status_code == 200


def test_delete_conversation(client):
    conv = client.post("/api/conversations?title=To+delete").json()
    conv_id = conv["id"]
    r = client.delete(f"/api/conversations/{conv_id}")
    assert r.status_code == 200
    # Verify gone
    r2 = client.get(f"/api/conversations/{conv_id}")
    assert r2.status_code == 404


def test_chat_no_docs(client):
    """Chat khi chưa có tài liệu - vẫn phải trả lời được"""
    r = client.post("/api/chat", json={"query": "Xin chào"})
    # 200 nếu LLM sẵn sàng, 503 nếu chưa cấu hình
    assert r.status_code in [200, 503]


def test_upload_txt(client, tmp_path):
    txt = tmp_path / "test_doc.txt"
    txt.write_text("Đây là tài liệu test về trí tuệ nhân tạo và machine learning.", encoding="utf-8")
    with open(txt, "rb") as f:
        r = client.post("/api/upload", files={"file": ("test_doc.txt", f, "text/plain")})
    assert r.status_code == 200
    data = r.json()
    assert data["chunks_created"] > 0


def test_upload_invalid_extension(client, tmp_path):
    f_path = tmp_path / "file.xyz"
    f_path.write_text("test")
    with open(f_path, "rb") as f:
        r = client.post("/api/upload", files={"file": ("file.xyz", f, "text/plain")})
    assert r.status_code == 400
