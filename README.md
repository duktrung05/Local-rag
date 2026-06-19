Local RAG Chatbot

Chatbot hỏi-đáp dựa trên tài liệu cá nhân, sử dụng kiến trúc RAG (Retrieval-Augmented Generation). Người dùng tải lên tài liệu (PDF, DOCX, TXT, MD, CSV), hệ thống tự động xử lý, lưu trữ vector và trả lời câu hỏi dựa trên nội dung tài liệu đó — kèm trích dẫn nguồn.

Cấu trúc dự án

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
