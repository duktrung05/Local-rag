# Giới thiệu về RAG Chatbot

## Tổng quan

RAG (Retrieval-Augmented Generation) là kỹ thuật kết hợp tìm kiếm thông tin từ cơ sở dữ liệu với khả năng sinh văn bản của mô hình ngôn ngữ lớn (LLM).

## Các thành phần chính

### 1. Document Loader
Document Loader chịu trách nhiệm đọc và trích xuất nội dung từ các định dạng file khác nhau:
- PDF: Sử dụng thư viện pypdf để trích xuất text từng trang
- TXT/MD: Đọc trực tiếp nội dung text
- DOCX: Sử dụng python-docx để đọc các đoạn văn
- CSV: Chuyển đổi từng hàng thành văn bản có thể đọc được

### 2. Text Chunker
Sau khi load tài liệu, văn bản được chia thành các đoạn nhỏ (chunks) với kích thước khoảng 1000 ký tự, có phần chồng lấp (overlap) 200 ký tự để đảm bảo ngữ cảnh không bị mất.

### 3. Embedding Manager
Mỗi chunk được chuyển thành vector số học (embedding) bằng mô hình sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, hỗ trợ cả tiếng Việt và tiếng Anh.

### 4. ChromaDB
Vector Database lưu trữ tất cả embeddings cùng với nội dung gốc và metadata. Khi người dùng hỏi, hệ thống sẽ tìm các chunks có độ tương đồng cosine cao nhất.

### 5. RAG Engine
Engine chính thực hiện toàn bộ quy trình:
1. Nhận câu hỏi từ người dùng
2. Chuyển câu hỏi thành embedding
3. Tìm top-K chunks liên quan nhất từ ChromaDB
4. Xây dựng prompt với ngữ cảnh từ các chunks
5. Gọi Claude API để sinh câu trả lời
6. Trả kết quả về frontend

## Ưu điểm của RAG

- **Chính xác**: Câu trả lời dựa trên tài liệu thực tế, không hallucinate
- **Cập nhật**: Có thể thêm tài liệu mới bất kỳ lúc nào
- **Trích dẫn nguồn**: Biết câu trả lời đến từ tài liệu nào
- **Đa ngôn ngữ**: Hỗ trợ tiếng Việt và tiếng Anh

## Cách sử dụng

1. Upload tài liệu qua giao diện web (kéo thả hoặc chọn file)
2. Đợi hệ thống xử lý (Load → Clean → Chunk → Embed → Store)
3. Đặt câu hỏi trong khung chat
4. Nhận câu trả lời với trích dẫn nguồn tài liệu

## Thông số kỹ thuật

| Thông số | Giá trị mặc định |
|----------|-----------------|
| Chunk size | 1000 ký tự |
| Chunk overlap | 200 ký tự |
| Top-K results | 5 chunks |
| Similarity threshold | 0.3 |
| Embedding dimensions | 384 |
| LLM | claude-opus-4-5 |
