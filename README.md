# Local RAG Chatbot

Chatbot hỏi-đáp dựa trên tài liệu cá nhân, sử dụng kiến trúc **RAG (Retrieval-Augmented Generation)**. Người dùng tải lên tài liệu (PDF, DOCX, TXT, MD, CSV), hệ thống tự động xử lý, lưu trữ vector và trả lời câu hỏi dựa trên nội dung tài liệu đó — kèm trích dẫn nguồn.

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Backend API | FastAPI |
| Frontend | Streamlit |
| Vector Database | ChromaDB |
| Embedding Model | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (chạy local, hỗ trợ tiếng Việt) |
| LLM | Llama 3.3 70B Versatile (qua Groq API) |
| Định dạng tài liệu hỗ trợ | PDF, DOCX, TXT, MD, CSV |

## Tính năng chính

- 📄 Tải lên và quản lý nhiều tài liệu, tự động chunking + embedding
- 💬 Chat đa phiên (lưu nhiều cuộc hội thoại riêng biệt, xem lại lịch sử)
- ⚡ Trả lời theo dạng streaming (hiển thị từng token như ChatGPT)
- 🔍 Trích dẫn nguồn rõ ràng — biết câu trả lời lấy từ tài liệu nào
- 🇻🇳 Hỗ trợ tốt tiếng Việt nhờ embedding model đa ngôn ngữ
- 🗑️ Quản lý tài liệu: xoá từng tài liệu hoặc toàn bộ lịch sử chat

## Cài đặt & Chạy

### Yêu cầu
- Python 3.10+
- API key từ [Groq](https://console.groq.com) (miễn phí)

### Các bước

```bash
# 1. Clone repo
git clone https://github.com/duktrung05/Local-rag.git
cd Local-rag

# 2. Tạo môi trường ảo
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Khai báo API key
cp .env.example .env
# Mở file .env và điền GROQ_API_KEY=<your_key_here>

# 5. Chạy backend
python main.py
```

Mở terminal khác, chạy frontend:

```bash
cd Local-rag
streamlit run streamlit_app.py
```

Truy cập `http://localhost:8501` để sử dụng.

> Hoặc dùng script có sẵn: `start.bat` (Windows) / `start.sh` (macOS/Linux) để khởi động cả hai cùng lúc.

## Cấu trúc dự án

```
Local-rag/
├── backend/
│   ├── core/
│   │   ├── chat_history.py        # Quản lý lịch sử hội thoại
│   │   ├── config.py              # Cấu hình hệ thống
│   │   ├── document_loader.py      # Đọc tài liệu (PDF/DOCX/TXT/MD/CSV)
│   │   ├── embedding_manager.py    # Vector hoá văn bản
│   │   ├── ingestion_pipeline.py   # Pipeline xử lý tài liệu đầu vào
│   │   ├── rag_engine.py          # Logic retrieval + sinh câu trả lời
│   │   ├── text_chunker.py        # Chia văn bản thành chunk
│   │   └── text_cleaner.py        # Làm sạch văn bản
│   ├── data/                      # Dữ liệu & vector store (không commit)
│   └── main.py                    # FastAPI entrypoint
├── scripts/
│   └── ingest.py                  # Script nạp tài liệu thủ công
├── streamlit_app.py                # Frontend Streamlit
├── requirements.txt
├── start.bat / start.sh
└── .env.example
```


