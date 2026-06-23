import streamlit as st
import requests
import json
import time

st.set_page_config(
    page_title="Local RAG Chatbot v2",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

BACKEND_URL = "http://127.0.0.1:8000"

# --- Inject Premium Custom CSS ---
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">

<style>
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .stApp {
        background-color: #fafbfc;
    }

    /* Headings */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 600;
        color: #0f172a;
    }

    /* Status Badge CSS */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: 9999px;
        font-size: 13px;
        font-weight: 500;
        border: 1px solid transparent;
    }
    .status-online {
        background-color: #ecfdf5;
        color: #065f46;
        border-color: #a7f3d0;
    }
    .status-offline {
        background-color: #fef2f2;
        color: #991b1b;
        border-color: #fca5a5;
    }

    /* Card Layouts */
    .premium-card {
        background: white;
        border-radius: 12px;
        padding: 16px 20px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
        margin-bottom: 16px;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .premium-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }

    /* Chat bubble enhancements */
    .chat-bubble-sources {
        font-size: 12.5px;
        margin-top: 10px;
        padding: 10px 14px;
        background-color: #f8fafc;
        border-left: 3px solid #3b82f6;
        border-radius: 4px 12px 12px 4px;
        color: #475569;
    }

    /* Clean File management list */
    .file-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 14px;
        background-color: #ffffff;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        margin-bottom: 8px;
    }

    /* Micro-animations */
    button {
        transition: all 0.2s ease-in-out !important;
    }
    button:hover {
        transform: scale(1.02);
    }
</style>
""", unsafe_allow_html=True)


# --- Initialize Session States ---
if "current_conv_id" not in st.session_state:
    st.session_state.current_conv_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversations" not in st.session_state:
    st.session_state.conversations = []
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "chat"


# --- Backend Helper Functions ---
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
            st.session_state.conversations = response.json()
            return st.session_state.conversations
    except Exception:
        pass
    return st.session_state.conversations

def create_conversation(title="Cuộc trò chuyện mới"):
    try:
        response = requests.post(f"{BACKEND_URL}/api/conversations?title={title}", timeout=2)
        if response.status_code == 200:
            conv = response.json()
            get_conversations()
            return conv
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
        if response.status_code == 200:
            get_conversations()
            return True
    except Exception:
        pass
    return False

def clear_all_conversations():
    try:
        response = requests.delete(f"{BACKEND_URL}/api/conversations", timeout=2)
        if response.status_code == 200:
            get_conversations()
            return True
    except Exception:
        pass
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
        response = requests.post(f"{BACKEND_URL}/api/upload", files=files, timeout=45)
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, {"detail": str(e)}

def delete_document(file_name):
    try:
        response = requests.delete(f"{BACKEND_URL}/api/documents/{file_name}", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def format_size(bytes_size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"

# --- RENDER SOURCES COMPONENT ---
def render_sources(sources):
    if not sources:
        return
    
    source_items = []
    for i, src in enumerate(sources, 1):
        page_info = f"trang {src['page']}" if src.get("page") else ""
        score_info = f"độ chính xác: {src['score']:.2f}" if src.get("score") else ""
        details = ", ".join([f for f in [page_info, score_info] if f])
        details_str = f" ({details})" if details else ""
        source_items.append(f"**[{i}]** {src['file_name']}{details_str}")
        
    sources_html = "\n\n".join(source_items)
    with st.expander("📄 Nguồn trích dẫn"):
        st.markdown(sources_html)


# --- APP STATE HANDLERS ---
def handle_select_conversation(conv_id):
    st.session_state.current_conv_id = conv_id
    st.session_state.messages = get_messages(conv_id)

def handle_create_conversation():
    new_conv = create_conversation()
    if new_conv:
        handle_select_conversation(new_conv["id"])


# --- MAIN LAYOUT SETUP ---
backend_ok, health_data = check_backend_health()
conversations = get_conversations()

# Check if selected conversation still exists
if st.session_state.current_conv_id and not any(c["id"] == st.session_state.current_conv_id for c in conversations):
    st.session_state.current_conv_id = None
    st.session_state.messages = []

# Sidebar implementation
with st.sidebar:
    st.markdown("<h2 style='margin-top:0;'>🤖 RAG Chatbot v2</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Health Status
    st.markdown("### Trạng thái hệ thống")
    if backend_ok:
        provider = health_data.get('provider', '').upper()
        model_name = health_data.get('model', 'N/A')
        st.markdown(f"""
        <div class="status-badge status-online">🟢 Trực tuyến</div>
        <div style="font-size:12.5px; color:#64748b; margin-top:8px; line-height:1.4;">
            <b>Provider:</b> {provider}<br/>
            <b>Model:</b> <code style="font-size:11px; padding:1px 3px; background:#f1f5f9; border-radius:3px;">{model_name}</code>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="status-badge status-offline">🔴 Ngoại tuyến</div>
        <div style="font-size:12.5px; color:#64748b; margin-top:8px;">
            Không tìm thấy kết nối tới API Server.
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔄 Thử kết nối lại", use_container_width=True):
            st.rerun()

    st.markdown("---")
    
    # Conversations section
    st.markdown("### Lịch sử trò chuyện")
    if st.button("➕ Cuộc trò chuyện mới", use_container_width=True, type="primary"):
        handle_create_conversation()
        st.rerun()
        
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    
    if conversations:
        for c in conversations:
            c_id = c["id"]
            c_title = c["title"]
            is_active = (c_id == st.session_state.current_conv_id)
            
            button_label = f"💬 {c_title}"
            if is_active:
                button_label = f"👉 {c_title}"
            
            col_btn, col_opt = st.columns([5, 1], vertical_alignment="center")
            with col_btn:
                # Selecting chat
                if st.button(button_label, key=f"sel_{c_id}", use_container_width=True, 
                             type="secondary" if not is_active else "primary"):
                    handle_select_conversation(c_id)
                    st.rerun()
            with col_opt:
                with st.popover("⋮", help="Hành động"):
                    if st.button("🗑️ Xóa", key=f"del_conv_{c_id}", type="primary", use_container_width=True):
                        if delete_conversation(c_id):
                            if st.session_state.current_conv_id == c_id:
                                st.session_state.current_conv_id = None
                                st.session_state.messages = []
                            st.rerun()
        
        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
        if st.button("🗑️ Xóa toàn bộ lịch sử", type="secondary", use_container_width=True):
            if clear_all_conversations():
                st.session_state.current_conv_id = None
                st.session_state.messages = []
                st.rerun()
    else:
        st.info("Chưa có cuộc trò chuyện nào.")


# --- MAIN SCREEN ---
if not st.session_state.current_conv_id:
    # LANDING PAGE when no chat selected
    st.markdown("<h1 style='text-align: center; margin-top: 50px; font-size: 3rem;'>🤖 Trợ lý thông minh RAG v2</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2rem; color: #64748b;'>Hệ thống hỏi đáp tài liệu thông minh sử dụng trí tuệ nhân tạo</p>", unsafe_allow_html=True)
    
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    
    col_feat1, col_feat2, col_feat3 = st.columns(3)
    with col_feat1:
        st.markdown("""
        <div class="premium-card">
            <h3>📂 Hỗ trợ đa dạng</h3>
            <p style="font-size: 14px; color:#475569;">Nạp các tài liệu PDF, DOCX, TXT, MD, CSV và cả tệp Excel (.xlsx) cực kì nhanh chóng.</p>
        </div>
        """, unsafe_allow_html=True)
    with col_feat2:
        st.markdown("""
        <div class="premium-card">
            <h3>⚡ Tìm kiếm ngữ nghĩa lai</h3>
            <p style="font-size: 14px; color:#475569;">Sử dụng Vector Embedding để tìm kiếm các văn bản liên quan kết hợp với Cross-Encoder Reranker lọc ra nguồn tin cậy.</p>
        </div>
        """, unsafe_allow_html=True)
    with col_feat3:
        st.markdown("""
        <div class="premium-card">
            <h3>💬 Stream trả lời tức thì</h3>
            <p style="font-size: 14px; color:#475569;">Trải nghiệm tốc độ sinh câu trả lời từng từ một theo thời gian thực (Stream Response) kèm trích nguồn chi tiết.</p>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
    st.info("💡 Vui lòng bấm vào nút **'➕ Cuộc trò chuyện mới'** ở góc trái để bắt đầu hỏi đáp tài liệu.")
    
else:
    # CHAT & DOC MANAGEMENT TABS
    tab_chat, tab_docs = st.tabs(["💬 Trò chuyện", "📂 Quản lý tài liệu"])
    
    # ── TAB 1: CHAT INTERACTION ──────────────────────────────────────
    with tab_chat:
        # Render message history
        for msg in st.session_state.messages:
            role = "user" if msg["role"] == "user" else "assistant"
            avatar = "🧑‍💻" if role == "user" else "🤖"
            with st.chat_message(role, avatar=avatar):
                st.markdown(msg["content"])
                
                # Check for sources
                sources = msg.get("sources", [])
                if isinstance(sources, str):
                    try:
                        sources = json.loads(sources)
                    except Exception:
                        sources = []
                        
                if role == "assistant" and sources:
                    render_sources(sources)

        # Handle user chat input
        query = st.chat_input("Nhập câu hỏi của bạn tại đây...")
        
        if query:
            # Append User message to Session State & Display instantly
            st.session_state.messages.append({"role": "user", "content": query})
            with st.chat_message("user", avatar="🧑‍💻"):
                st.markdown(query)
            
            # Display Assistant typing placeholder
            with st.chat_message("assistant", avatar="🤖"):
                response_placeholder = st.empty()
                full_response = ""
                sources_list = []
                
                try:
                    # Stream call from backend
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
                                        sources_list = event["data"]
                                    elif event["type"] == "conv_id":
                                        st.session_state.current_conv_id = event["data"]
                                except Exception:
                                    pass
                                    
                    # Display final complete response without cursor
                    response_placeholder.markdown(full_response)
                    if sources_list:
                        render_sources(sources_list)
                    
                    # Update local state so page redraws correctly on state events
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": full_response,
                        "sources": sources_list
                    })
                    
                except Exception as e:
                    error_msg = f"⚠️ Lỗi kết nối API Server: {e}"
                    response_placeholder.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg,
                        "sources": []
                    })
                    
                # Smooth update without forced double-rerun
                st.rerun()

    # ── TAB 2: DOCUMENT MANAGEMENT ───────────────────────────────────
    with tab_docs:
        st.markdown("### 📂 Quản lý kho tài liệu RAG")
        st.caption("Các tệp tài liệu được tải lên sẽ được chuyển đổi thành vector nhúng ngữ nghĩa và lưu trữ trong cơ sở dữ liệu.")
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        
        # Upload area
        uploaded_file = st.file_uploader(
            "Tải lên tệp tài liệu mới (Hỗ trợ: PDF, TXT, DOCX, MD, CSV, XLSX):",
            type=["pdf", "txt", "docx", "md", "csv", "xlsx"]
        )
        
        if uploaded_file is not None:
            with st.spinner("Đang nạp, xử lý và trích xuất vector tài liệu..."):
                success, res = upload_document(uploaded_file)
                if success:
                    st.success(f"Nạp thành công: **{uploaded_file.name}** ({res.get('chunks_created', 0)} chunks được lưu trữ)", icon="✅")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error(f"Lỗi khi nạp tài liệu: {res.get('detail', 'Unknown error')}", icon="⚠️")
                    
        st.markdown("---")
        st.markdown("#### Danh sách tài liệu hiện có trong Database")
        
        docs = get_documents()
        if docs:
            # Render custom styled list
            for doc in docs:
                doc_name = doc.get("file_name", "")
                doc_size = format_size(doc.get("file_size", 0))
                doc_type = doc.get("file_type", "").upper()
                
                st.markdown(f"""
                <div class="file-item">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 24px;">📄</span>
                        <div>
                            <b style="color: #0f172a; font-size:14.5px;">{doc_name}</b><br/>
                            <span style="font-size: 12px; color: #64748b;">Kích thước: {doc_size} | Định dạng: {doc_type}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Delete button placed correctly below or aligned
                col_info, col_del = st.columns([6, 1])
                with col_del:
                    if st.button("🗑️ Xóa tệp", key=f"del_doc_{doc_name}", use_container_width=True, type="secondary"):
                        with st.spinner(f"Đang xóa {doc_name}..."):
                            if delete_document(doc_name):
                                st.success(f"Đã xóa {doc_name}!")
                                time.sleep(1.2)
                                st.rerun()
                            else:
                                st.error("Lỗi khi xóa tài liệu.")
        else:
            st.info("Hiện chưa có tài liệu nào trong Vector Database. Vui lòng tải tài liệu lên ở mục trên.")