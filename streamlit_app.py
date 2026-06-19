import streamlit as st
import requests
import json
import time
 
st.set_page_config(
    page_title="RAG Chatbot",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)   
 
BACKEND_URL = "http://127.0.0.1:8000"
 
if "current_conv_id" not in st.session_state:
    st.session_state.current_conv_id = None
if "current_sources" not in st.session_state:
    st.session_state.current_sources = []
if "pending_rerun" not in st.session_state:
    st.session_state.pending_rerun = False
# Flag để delay rerun sau khi stream xong
if "stream_done" not in st.session_state:
    st.session_state.stream_done = False
 
#  Xử lý rerun TRƯỚC khi render UI
# Nếu stream vừa xong ở lần rerun trước → rerun lần nữa để đồng bộ DB
if st.session_state.stream_done:
    st.session_state.stream_done = False
    st.rerun()
 
# --- Helper functions ---
def check_backend_health():
    try:
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=2)
        if response.status_code == 200:
            return True, response.json()
    except Exception:
        pass
    return False, {}
 
def get_conversations():
    try:
        response = requests.get(f"{BACKEND_URL}/api/conversations", timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []
 
def create_conversation(title="Cuộc trò chuyện mới"):
    try:
        response = requests.post(f"{BACKEND_URL}/api/conversations?title={title}", timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Lỗi tạo cuộc trò chuyện: {e}")
    return None
 
def get_messages(conv_id):
    try:
        response = requests.get(f"{BACKEND_URL}/api/conversations/{conv_id}/messages", timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []
 
def delete_conversation(conv_id):
    try:
        response = requests.delete(f"{BACKEND_URL}/api/conversations/{conv_id}", timeout=2)
        return response.status_code == 200
    except Exception:
        return False
 
def clear_all_conversations():
    try:
        response = requests.delete(f"{BACKEND_URL}/api/conversations", timeout=2)
        return response.status_code == 200
    except Exception:
        return False
 
def get_documents():
    try:
        response = requests.get(f"{BACKEND_URL}/api/documents", timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []
 
def upload_document(uploaded_file):
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        response = requests.post(f"{BACKEND_URL}/api/upload", files=files, timeout=30)
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, {"detail": str(e)}
 
def delete_document(file_name):
    try:
        response = requests.delete(f"{BACKEND_URL}/api/documents/{file_name}", timeout=5)
        return response.status_code == 200
    except Exception:
        return False
 
def render_sources(sources):
    """Helper dùng chung để hiển thị nguồn tham khảo"""
    if not sources:
        return
    with st.expander("📄 Nguồn tham khảo"):
        for i, src in enumerate(sources, 1):
            page_info = f"trang {src['page']}" if src.get("page") else ""
            score_info = f"độ trùng khớp: {src['score']:.2f}" if src.get("score") else ""
            details = ", ".join([f for f in [page_info, score_info] if f])
            st.write(f"**[{i}]** {src['file_name']} *({details})*")
 
# --- GIAO DIỆN CHÍNH ---
st.title("RAG Chatbot")
st.caption("Giao diện Streamlit tương tác với FastAPI RAG Backend")
 
backend_ok, health_data = check_backend_health()
 
# --- SIDEBAR ---
with st.sidebar:
    st.header("Trạng thái Server")
    if backend_ok:
        provider = health_data.get('provider', '').upper()
        model_name = health_data.get('model', 'N/A')
        st.markdown(f"""
        <div style="
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 10px;
            background-color: #ffffff;
            margin-bottom: 15px;
        ">
            <div style="display: flex; align-items: center; gap: 8px; font-weight: 600; color: #0f172a; font-size: 14px;">
                <span style="color: #10b981; font-size: 12px;">🟢</span> Kết nối thành công
            </div>
            <div style="margin-top: 6px; font-size: 12px; color: #64748b;">
                <strong>Provider:</strong> {provider}
            </div>
            <div style="margin-top: 2px; font-size: 12px; color: #64748b;">
                <strong>Model:</strong> <code style="background-color: #f1f5f9; padding: 2px 4px; border-radius: 4px; font-family: monospace;">{model_name}</code>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        col_err, col_btn = st.columns([3, 2], vertical_alignment="center")
        with col_err:
            st.error("⚠️ Ngoại tuyến")
        with col_btn:
            if st.button("🔄 Thử lại", use_container_width=True):
                st.rerun()
 
    st.markdown("---")
 
    st.header("Lịch sử trò chuyện")
 
    if st.button("Cuộc trò chuyện mới", use_container_width=True):
        new_conv = create_conversation()
        if new_conv:
            st.session_state.current_conv_id = new_conv["id"]
            st.session_state.current_sources = []
            st.rerun()
 
    convs = get_conversations()
    if convs:
        conv_titles = {c["id"]: c["title"] for c in convs}
 
        if st.session_state.current_conv_id not in conv_titles:
            st.session_state.current_conv_id = convs[0]["id"]
 
        for c in convs:
            c_id = c["id"]
            c_title = c["title"]
            is_active = (c_id == st.session_state.current_conv_id)
            
            label = c_title
            if is_active:
                label = f"▸ {c_title}"
                
            col1, col2 = st.columns([5, 1], vertical_alignment="center")
            with col1:
                if st.button(label, key=f"select_{c_id}", use_container_width=True):
                    st.session_state.current_conv_id = c_id
                    st.session_state.current_sources = []
                    st.rerun()
            with col2:
                with st.popover("⋮", help="Tùy chọn"):
                    if st.button("🗑️ Xóa", key=f"del_{c_id}", type="primary", use_container_width=True):
                        if delete_conversation(c_id):
                            if st.session_state.current_conv_id == c_id:
                                st.session_state.current_conv_id = None
                            st.session_state.current_sources = []
                            st.rerun()
 
        if st.button("Xóa toàn bộ lịch sử", type="secondary", use_container_width=True):
            if clear_all_conversations():
                st.session_state.current_conv_id = None
                st.session_state.current_sources = []
                st.rerun()
    else:
        st.info("Chưa có cuộc trò chuyện nào.")
 
    st.markdown("---")
 
    st.header("Quản lý tài liệu")
 
    uploaded_file = st.file_uploader(
        "Tải lên tài liệu mới (PDF/TXT/DOCX/MD/CSV):",
        type=["pdf", "txt", "docx", "md", "csv"]
    )
    if uploaded_file is not None:
        with st.spinner("Đang nạp và xử lý tài liệu..."):
            success, res = upload_document(uploaded_file)
            if success:
                st.success(f"Nạp thành công: {uploaded_file.name} ({res.get('chunks_created', 0)} chunks)", icon="✅")
                time.sleep(1.5)
                st.rerun()
            else:
                st.error(f"Lỗi khi nạp: {res.get('detail', 'Unknown error')}", icon="⚠️")
 
    docs = get_documents()
    if docs:
        st.write(f"Đang có {len(docs)} tài liệu trong database:")
        for doc in docs:
            col1, col2 = st.columns([4, 1]) 
            col1.caption(f"📄 {doc}")
            if col2.button("❌", key=f"del_{doc}"):
                if delete_document(doc):
                    st.success(f"Đã xóa {doc}", icon="✅")
                    time.sleep(1)
                    st.rerun()
    else:
        st.caption("Chưa có tài liệu nào trong database.")
 
# --- KHU VỰC CHAT ---
 
if not st.session_state.current_conv_id:
    st.info("Vui lòng chọn một cuộc trò chuyện từ lịch sử hoặc nhấn nút **'➕ Cuộc trò chuyện mới'** ở cột bên trái để bắt đầu chat.")
    with st.expander("💡 Quy trình RAG Pipeline v2 hoạt động như thế nào?"):
        st.write("""
        Hệ thống sử dụng quy trình **9 bước nâng cấp**:
        1. **Đọc tài liệu (Load)**: Hỗ trợ PDF, TXT, DOCX, MD, CSV.
        2. **Làm sạch (Clean)**: Chuẩn hóa unicode và loại bỏ ký tự lạ.
        3. **Chia chunk (Chunk)**: Chiến lược phân đoạn ngữ nghĩa (Semantic Chunking).
        4. **Embed**: Nhúng chunk văn bản thành vector.
        5. **Lưu trữ (Store)**: Lưu vector vào ChromaDB.
        6. **Nhúng truy vấn**: Nhúng câu hỏi của bạn thành vector.
        7. **Tìm kiếm (Retrieve)**: Lấy ra các chunk có nội dung tương đồng.
        8. **Sắp xếp lại (Rerank)**: Cross-Encoder chọn 3 nguồn tốt nhất.
        9. **Trả lời (Generation)**: Tổng hợp câu trả lời kèm trích nguồn.
        """)
 
else:
    # ✅ FIX 4: Lấy messages TRƯỚC khi render chat_input
    messages = get_messages(st.session_state.current_conv_id)
 
    # ✅ FIX 5: Nhận input TRƯỚC khi render lịch sử
    # Đây là fix cốt lõi — chat_input phải được gọi trước st.chat_message loop
    query = st.chat_input("Nhập câu hỏi của bạn ở đây...")
 
    # Render lịch sử chat
    for msg in messages:
        role = "user" if msg["role"] == "user" else "assistant"
        avatar = "🧑‍💻" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            st.markdown(msg["content"])
            sources = (
                json.loads(msg["sources"])
                if isinstance(msg.get("sources"), str)
                else msg.get("sources", [])
            )
            if role == "assistant":
                render_sources(sources)
 
    # Xử lý câu hỏi mới
    if query:
        # Hiển thị message user ngay lập tức
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(query)
 
        # Stream phản hồi assistant
        with st.chat_message("assistant", avatar="🤖"):
            response_placeholder = st.empty()
            full_response = ""
            st.session_state.current_sources = []
 
            try:
                response = requests.post(
                    f"{BACKEND_URL}/api/chat/stream",
                    json={
                        "query": query,
                        "conversation_id": st.session_state.current_conv_id
                    },
                    stream=True,
                    timeout=60
                )
 
                for line in response.iter_lines():
                    if line:
                        line_decoded = line.decode("utf-8").strip()
                        if line_decoded.startswith("data: "):
                            event_data = line_decoded[6:]
                            try:
                                event = json.loads(event_data)
                                if event["type"] == "token":
                                    full_response += event["data"]
                                    response_placeholder.markdown(full_response + "▌")
                                elif event["type"] == "sources":
                                    st.session_state.current_sources = event["data"]
                                elif event["type"] == "conv_id":
                                    st.session_state.current_conv_id = event["data"]
                            except Exception:
                                pass
 
            except Exception as e:
                full_response += f"\n\nLỗi kết nối Server: {e}"
 
            # Render câu trả lời hoàn chỉnh (bỏ cursor ▌)
            response_placeholder.markdown(full_response)
 
            # Hiển thị nguồn của câu hỏi vừa hỏi
            render_sources(st.session_state.current_sources)
         # Đặt flag → Streamlit rerun tự nhiên sau khi render xong → flag kích hoạt rerun thứ 2 để đồng bộ DB
        st.session_state.stream_done = True
        st.rerun()
 