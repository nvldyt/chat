import streamlit as st
import uuid
import json
import base64
import html
import time
import urllib.parse
from cryptography.fernet import Fernet, InvalidToken

# ============================================================
# CẤU HÌNH ỨNG DỤNG
# ============================================================

APP_TITLE = "Chia Sẻ Bảo Mật"
BASE_URL = "https://phongchat.streamlit.app"

MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024      # 15 MB — giới hạn thật, có kiểm tra
LINK_TTL_SECONDS = 24 * 60 * 60             # Link tự hết hạn sau 24h nếu không ai mở
MAX_STORE_ENTRIES = 200                     # Chặn spam làm đầy RAM server

# ============================================================
# CẤU HÌNH STREAMLIT
# ============================================================

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🌌",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ============================================================
# CSS GIAO DIỆN
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at 20% 0%, #1b1030 0%, #111319 45%, #0b0c10 100%) !important;
    }

    html, body, p, div, span, label, li {
        font-family: 'Arial', sans-serif !important;
        color: #e2e8f0 !important;
    }

    /* Không được ép font lên icon (Material Symbols) của Streamlit,
       nếu không icon "upload" sẽ vỡ ra thành chữ thường chồng chữ */
    [data-testid="stIconMaterial"] {
        font-family: 'Material Symbols Outlined' !important;
        color: #dcb8ff !important;
    }

    /* Chữ "Drag and drop file here / Limit ... per file" trong khung upload */
    [data-testid="stFileUploadDropzoneInstructions"] div,
    [data-testid="stFileUploadDropzoneInstructions"] span {
        color: #cbd5e1 !important;
    }
    [data-testid="stFileUploadDropzoneInstructions"] small {
        color: #9ca3af !important;
    }

    /* Nút "Browse files" bên trong khung upload */
    [data-testid="stFileUploadDropzone"] button {
        background-color: #374151 !important;
        color: #e2e8f0 !important;
        border: 1px solid #4b5563 !important;
        border-radius: 8px !important;
    }
    [data-testid="stFileUploadDropzone"] button:hover {
        border-color: #dcb8ff !important;
        color: #dcb8ff !important;
    }

    h1, h2, h3 {
        background: linear-gradient(90deg, #ff2e93, #dcb8ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        letter-spacing: -0.5px !important;
    }

    .subtitle {
        color: #9ca3af;
        font-size: 16px;
        margin-bottom: 26px;
        line-height: 1.55;
    }

    .badge-row {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 22px;
    }
    .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(220, 184, 255, 0.08);
        border: 1px solid rgba(220, 184, 255, 0.25);
        color: #dcb8ff !important;
        border-radius: 999px;
        padding: 6px 14px;
        font-size: 13px !important;
        font-weight: 600;
    }

    [data-testid="stFileUploadDropzone"] {
        background-color: rgba(255,255,255,0.02) !important;
        border: 2px dashed #4b5563 !important;
        border-radius: 16px !important;
        padding: 40px 20px !important;
        transition: all 0.3s ease !important;
    }
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #ff2e93 !important;
        background-color: rgba(255, 46, 147, 0.05) !important;
    }

    .stTextArea textarea {
        background-color: #1f2937 !important;
        border: 1px solid #374151 !important;
        color: white !important;
        border-radius: 12px !important;
        font-size: 16px !important;
    }
    .stTextArea textarea:focus {
        border-color: #dcb8ff !important;
        box-shadow: 0 0 0 1px #dcb8ff !important;
    }

    div.stButton > button {
        background: linear-gradient(90deg, #dcb8ff, #ff9ee0) !important;
        color: #111319 !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        padding: 12px 24px !important;
        border: none !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button:hover {
        filter: brightness(1.08);
        transform: translateY(-2px);
    }

    div.stButton > button[kind="secondary"] {
        background: transparent !important;
        color: #9ca3af !important;
        border: 1px solid #4b5563 !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        color: #ef4444 !important;
        border-color: #ef4444 !important;
    }

    .stCodeBlock {
        background-color: #1f2937 !important;
        border: 1px solid #374151 !important;
        border-radius: 8px !important;
    }

    .stAlert {
        background-color: rgba(31, 41, 55, 0.85) !important;
        color: #e2e8f0 !important;
        border: 1px solid #374151 !important;
        border-radius: 12px !important;
    }

    .message-box {
        background-color: #1f2937;
        border: 1px solid #374151;
        border-radius: 14px;
        padding: 26px;
        font-size: 18px !important;
        color: #f8fafc !important;
        line-height: 1.6 !important;
        white-space: pre-wrap;
        word-break: break-word;
        margin-bottom: 20px;
        text-align: center !important;
        box-shadow: 0 8px 30px rgba(255, 46, 147, 0.08);
    }

    .reveal-card {
        background: rgba(31, 41, 55, 0.6);
        border: 1px solid #374151;
        border-radius: 16px;
        padding: 32px 24px;
        text-align: center;
        margin-bottom: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# BỘ NHỚ RAM TẠM THỜI (STORE)
# Mỗi entry: message_id -> {"data": bytes_mahoa, "created": timestamp}
# ============================================================

@st.cache_resource
def get_memory_store():
    return {}

store = get_memory_store()


def cleanup_expired_entries():
    """Dọn các link đã quá hạn (không ai mở) để tránh rò rỉ bộ nhớ.

    Cũng dọn luôn các entry ở định dạng cũ (từ trước khi TTL được thêm vào),
    vì st.cache_resource giữ nguyên dữ liệu qua các lần deploy code mới.
    """
    now = time.time()
    expired_ids = []
    for mid, entry in store.items():
        if not isinstance(entry, dict) or "created" not in entry or "data" not in entry:
            expired_ids.append(mid)
            continue
        if now - entry["created"] > LINK_TTL_SECONDS:
            expired_ids.append(mid)
    for mid in expired_ids:
        store.pop(mid, None)


def enforce_store_capacity():
    """Chặn spam tạo link vô hạn: nếu đầy, xoá entry cũ nhất trước."""
    if len(store) >= MAX_STORE_ENTRIES:
        oldest_id = min(store, key=lambda mid: store[mid]["created"])
        store.pop(oldest_id, None)


cleanup_expired_entries()


# ============================================================
# HÀM TIỆN ÍCH & SESSION
# ============================================================

def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"

if "generated_link" not in st.session_state:
    st.session_state.generated_link = ""
if "generated_message_id" not in st.session_state:
    st.session_state.generated_message_id = ""
if "confirmed_reveal" not in st.session_state:
    st.session_state.confirmed_reveal = False


# ============================================================
# ĐỌC URL
# ============================================================

query_params = st.query_params
url_id = query_params.get("id", "")
url_secret = query_params.get("secret", "")


# ============================================================
# LUỒNG NGƯỜI NHẬN
# ============================================================

if url_id and url_secret:

    st.title("📬 Bạn có một tin nhắn bảo mật!")

    st.markdown(
        """
        <p class="subtitle">
        Hệ thống chia sẻ dữ liệu với <b>mã hóa đầu cuối (end-to-end encryption)</b>
        và đường link sẽ <b>tự động hủy ngay sau khi được mở</b>.
        </p>
        """,
        unsafe_allow_html=True
    )

    # Bước xác nhận thủ công trước khi giải mã / tiêu huỷ dữ liệu.
    # Mục đích: chặn các bot quét link (preview link của Zalo/Messenger/Slack...)
    # vô tình mở trang và "đốt" mất nội dung trước khi người nhận thật sự bấm vào.
    if url_id not in store:
        st.error("❌ Dữ liệu không tồn tại, đã hết hạn (sau 24h) hoặc ĐÃ ĐƯỢC XEM trước đó.")

    elif not st.session_state.confirmed_reveal:
        st.markdown(
            """
            <div class="reveal-card">
                <div style="font-size:40px; margin-bottom:10px;">🔒</div>
                <div style="font-size:16px; color:#9ca3af;">
                    Nội dung đang được mã hóa an toàn.<br>
                    Nhấn nút bên dưới để giải mã và xem — dữ liệu sẽ bị xóa vĩnh viễn ngay sau đó.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("🔓 Giải mã & Xem nội dung", type="primary", use_container_width=True):
            st.session_state.confirmed_reveal = True
            st.rerun()

    else:
        encrypted_entry = store.pop(url_id, None)

        if not isinstance(encrypted_entry, dict) or "data" not in encrypted_entry:
            st.error("❌ Dữ liệu vừa bị lấy đi, đã hết hạn hoặc không hợp lệ.")
        else:
            try:
                cipher = Fernet(url_secret.encode("ascii"))
                decrypted = cipher.decrypt(encrypted_entry["data"])
                payload = json.loads(decrypted.decode("utf-8"))

                st.success("✅ Đã giải mã thành công! Dữ liệu vừa bị xóa vĩnh viễn khỏi máy chủ.")
                st.write("---")

                msg_text = payload.get("text", "")
                if msg_text:
                    safe_text = html.escape(msg_text)
                    st.markdown(f'<div class="message-box">{safe_text}</div>', unsafe_allow_html=True)

                filename = payload.get("filename", "")
                filedata_b64 = payload.get("filedata", "")
                mime_type = payload.get("mime_type", "application/octet-stream")

                if filename and filedata_b64:
                    try:
                        raw_data = base64.b64decode(filedata_b64, validate=True)
                        st.download_button(
                            label=f"⬇️ Tải file: {filename}",
                            data=raw_data,
                            file_name=filename,
                            mime=mime_type,
                            type="primary",
                            use_container_width=True,
                        )
                    except Exception:
                        st.error("❌ Không thể đọc tệp đính kèm.")

            except InvalidToken:
                st.error("❌ Khóa giải mã không hợp lệ hoặc dữ liệu bị hỏng.")
            except Exception:
                st.error("❌ Đã có lỗi xảy ra khi xử lý dữ liệu.")

    st.write("---")
    if st.button("🏠 Trở về trang chủ", type="secondary", use_container_width=True):
        st.session_state.confirmed_reveal = False
        st.query_params.clear()
        st.rerun()


# ============================================================
# LUỒNG NGƯỜI GỬI
# ============================================================

else:
    if not st.session_state.generated_link:
        st.title("🌌 Simple, private file sharing")

        st.markdown(
            """
            <p class="subtitle">
            Chia sẻ file và tin nhắn với <b>mã hóa đầu cuối</b>. Link sẽ tự động hủy ngay sau khi được mở
            và tự hết hạn sau 24 giờ nếu không ai mở.
            </p>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div class="badge-row">
                <span class="badge">🔐 Mã hóa Fernet (AES-128)</span>
                <span class="badge">🔥 Xem 1 lần rồi tự hủy</span>
                <span class="badge">⏱️ Hết hạn sau 24h</span>
                <span class="badge">📦 Tối đa {format_size(MAX_FILE_SIZE_BYTES)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            f"Kéo thả hoặc chọn file để gửi (tối đa {format_size(MAX_FILE_SIZE_BYTES)})",
            label_visibility="collapsed"
        )

        text_input = st.text_area(
            "Hoặc nhập tin nhắn văn bản:",
            height=120,
            placeholder="Ghi chú bí mật của bạn...",
        )

        st.write("")
        if st.button("Tạo link chia sẻ", type="primary", use_container_width=True):
            cleanup_expired_entries()

            if not text_input.strip() and uploaded_file is None:
                st.warning("Vui lòng đính kèm file hoặc nhập tin nhắn.")
            elif uploaded_file is not None and (uploaded_file.size or 0) > MAX_FILE_SIZE_BYTES:
                st.error(
                    f"❌ File quá lớn ({format_size(uploaded_file.size)}). "
                    f"Giới hạn tối đa là {format_size(MAX_FILE_SIZE_BYTES)}."
                )
            else:
                try:
                    enforce_store_capacity()

                    message_id = str(uuid.uuid4())
                    secret_key = Fernet.generate_key()

                    file_b64 = ""
                    filename = ""
                    mime_type = ""
                    file_size = 0

                    if uploaded_file is not None:
                        file_size = uploaded_file.size or 0
                        raw_file = uploaded_file.getvalue()
                        file_b64 = base64.b64encode(raw_file).decode("ascii")
                        filename = uploaded_file.name
                        mime_type = uploaded_file.type or "application/octet-stream"

                    payload = {
                        "text": text_input.strip(),
                        "filename": filename,
                        "mime_type": mime_type,
                        "filedata": file_b64,
                        "filesize": file_size,
                    }

                    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    cipher = Fernet(secret_key)
                    encrypted_payload = cipher.encrypt(plaintext)

                    store[message_id] = {
                        "data": encrypted_payload,
                        "created": time.time(),
                    }

                    params = {
                        "id": message_id,
                        "secret": secret_key.decode("ascii"),
                    }

                    full_link = (
                        BASE_URL.rstrip("/")
                        + "/?"
                        + urllib.parse.urlencode(params)
                    )

                    st.session_state.generated_link = full_link
                    st.session_state.generated_message_id = message_id
                    st.rerun()

                except Exception:
                    st.error("❌ Không thể tạo link.")

    else:
        st.title("✅ Your file is ready to share!")

        st.markdown(
            """
            <p class="subtitle">
            Copy link để chia sẻ. Dữ liệu sẽ <b>tự động hủy</b> ngay sau lần tải đầu tiên,
            hoặc tự hết hạn sau 24 giờ nếu không có ai mở.
            </p>
            """,
            unsafe_allow_html=True
        )

        st.code(st.session_state.generated_link, language="text")

        st.info(
            "⚠️ Lưu ý: đường link chứa khóa giải mã. Chỉ gửi link qua kênh riêng tư "
            "(tin nhắn trực tiếp), tránh dán vào nơi công khai hoặc kênh có bot tự động quét link."
        )

        st.write("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✏️ Tạo mật thư mới", type="primary", use_container_width=True):
                st.session_state.generated_link = ""
                st.session_state.generated_message_id = ""
                st.rerun()
        with col2:
            if st.button("🗑️ Hủy Link Ngay Lập Tức", type="secondary", use_container_width=True):
                store.pop(st.session_state.generated_message_id, None)
                st.session_state.generated_link = ""
                st.session_state.generated_message_id = ""
                st.rerun()
