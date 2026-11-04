import os
import uuid
import json
import base64
import binascii
import html
import time
import threading
import urllib.parse
from typing import Dict, Any, Tuple

import streamlit as st
from cryptography.fernet import Fernet, InvalidToken

# ============================================================
# CẤU HÌNH ỨNG DỤNG
# ============================================================

APP_TITLE = "CHAT"
DEFAULT_BASE_URL = "https://filebaomat.streamlit.app"

MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
LINK_TTL_SECONDS = 24 * 60 * 60
MAX_STORE_ENTRIES = 50

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

    html, body, p, label, li, h1, h2, h3, h4, h5, h6, textarea, input, button, .message-box, .subtitle, .stAlert {
        font-family: 'Arial', sans-serif !important;
        color: #e2e8f0 !important;
    }

    [data-testid="stFileUploader"] {
        background-color: #1f2937 !important;
        border-radius: 16px !important;
        padding: 4px !important;
    }
    [data-testid="stFileUploadDropzone"] {
        background-color: transparent !important;
        border: 2px dashed #6b7280 !important;
        border-radius: 14px !important;
        padding: 30px 20px !important;
    }
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #ff2e93 !important;
        background-color: rgba(255, 46, 147, 0.05) !important;
    }

    [data-testid="stFileUploadDropzone"] button span,
    [data-testid="stFileUploadDropzone"] button svg,
    [data-testid="stFileUploadDropzone"] button i {
        display: none !important;
    }

    [data-testid="stFileUploadDropzone"] button::after {
        content: "CHỌN FILE" !important;
        display: block !important;
        font-family: 'Arial', sans-serif !important;
        font-weight: 900 !important;
        font-size: 16px !important;
        color: #111319 !important;
    }

    [data-testid="stFileUploadDropzone"] button {
        background: linear-gradient(90deg, #dcb8ff, #ff9ee0) !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 30px !important;
        box-shadow: 0 4px 10px rgba(220, 184, 255, 0.2) !important;
        margin-top: 10px !important;
    }
    [data-testid="stFileUploadDropzone"] button:hover {
        filter: brightness(1.1);
        transform: translateY(-2px);
    }

    [data-testid="stFileUploadDropzoneInstructions"] small {
        display: none !important;
    }
    [data-testid="stFileUploadDropzoneInstructions"] div,
    [data-testid="stFileUploadDropzoneInstructions"] span {
        color: #f8fafc !important;
        font-size: 15px !important;
    }

    h1, h2, h3 {
        background: linear-gradient(90deg, #ff2e93, #dcb8ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        letter-spacing: -0.5px !important;
    }

    .subtitle {
        color: #9ca3af !important;
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

    .stTextArea textarea {
        background-color: #1f2937 !important;
        border: 1px solid #4b5563 !important;
        color: #ffffff !important;
        border-radius: 12px !important;
        font-size: 16px !important;
    }
    .stTextArea textarea::placeholder {
        color: #9ca3af !important;
        opacity: 1 !important;
    }
    .stTextArea textarea:focus {
        border-color: #dcb8ff !important;
        box-shadow: 0 0 0 1px #dcb8ff !important;
    }

    div.stButton > button[kind="primary"],
    div.stDownloadButton > button {
        background: linear-gradient(90deg, #dcb8ff, #ff9ee0) !important;
        color: #111319 !important;
        border-radius: 10px !important;
        font-weight: 800 !important;
        font-size: 16px !important;
        padding: 12px 24px !important;
        border: none !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button[kind="primary"]:hover,
    div.stDownloadButton > button:hover {
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
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# BỘ NHỚ RAM TẠM THỜI & KHÓA LUỒNG (THREAD-SAFE STORE)
# ============================================================

@st.cache_resource
def get_store_and_lock() -> Tuple[Dict[str, Dict[str, Any]], threading.Lock]:
    return {}, threading.Lock()


STORE, STORE_LOCK = get_store_and_lock()


def get_share_base_url() -> str:
    configured = os.environ.get("BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")

    codespace_name = os.environ.get("CODESPACE_NAME", "").strip()
    forwarding_domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "").strip()
    if codespace_name and forwarding_domain:
        port = os.environ.get("PORT", "8501").strip()
        return f"https://{codespace_name}-{port}.{forwarding_domain}".rstrip("/")

    try:
        headers = st.context.headers
        if headers:
            host = headers.get("X-Forwarded-Host") or headers.get("Host") or ""
            proto = (headers.get("X-Forwarded-Proto") or "https").split(",", 1)[0].strip()
            if host and not host.startswith("localhost") and not host.startswith("127.0.0.1"):
                return f"{proto}://{host}".rstrip("/")
    except Exception:
        pass

    return DEFAULT_BASE_URL.rstrip("/")


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def cleanup_expired_entries():
    now = time.time()
    expired_ids = []
    for msg_id, entry in list(STORE.items()):
        if not isinstance(entry, dict) or "created" not in entry or "data" not in entry:
            expired_ids.append(msg_id)
            continue
        if now - entry["created"] > LINK_TTL_SECONDS:
            expired_ids.append(msg_id)
    for msg_id in expired_ids:
        STORE.pop(msg_id, None)


def enforce_store_capacity():
    if len(STORE) >= MAX_STORE_ENTRIES:
        oldest_id = min(STORE, key=lambda mid: STORE[mid]["created"])
        STORE.pop(oldest_id, None)


# ============================================================
# KHỞI TẠO SESSION STATE
# ============================================================

if "generated_link" not in st.session_state:
    st.session_state.generated_link = ""
if "generated_message_id" not in st.session_state:
    st.session_state.generated_message_id = ""
if "decrypted_cache" not in st.session_state:
    st.session_state.decrypted_cache = {}


# ============================================================
# ĐỌC THAM SỐ URL
# ============================================================

query_params = st.query_params
url_id = query_params.get("id", "")
url_secret = query_params.get("secret", "")


# ============================================================
# LUỒNG NGƯỜI NHẬN (AN TOÀN THREAD-LOCK & CHỈ XÓA KHI GIẢI MÃ ĐÚNG)
# ============================================================

if url_id and url_secret:
    st.title("📬 Tin nhắn tự động xóa sau khi xem!")
    st.markdown(
        '<p class="subtitle">Đường link sẽ <b>tự động hủy ngay sau khi mở</b>.</p>',
        unsafe_allow_html=True,
    )

    payload = None
    error_msg = ""

    # Nếu đã giải mã trong phiên hiện tại (khi bấm nút Tải file), lấy lại từ session_state
    if url_id in st.session_state.decrypted_cache:
        payload = st.session_state.decrypted_cache[url_id]
    else:
        with STORE_LOCK:
            cleanup_expired_entries()
            entry = STORE.get(url_id)

            if entry is None or not isinstance(entry, dict) or "data" not in entry:
                error_msg = "❌ File đã bị xóa hoặc link hết hạn."
            else:
                try:
                    decrypted_bytes = Fernet(url_secret.encode("ascii")).decrypt(entry["data"])
                    payload = json.loads(decrypted_bytes.decode("utf-8"))
                    # Chỉ xóa khỏi STORE sau khi giải mã thành công (như logic bản Flask)
                    STORE.pop(url_id, None)
                    st.session_state.decrypted_cache[url_id] = payload
                except (InvalidToken, ValueError, TypeError, UnicodeError, binascii.Error):
                    error_msg = "❌ Khóa truy cập không hợp lệ."
                except Exception:
                    error_msg = "❌ Đã có lỗi xảy ra khi xử lý dữ liệu."

    if error_msg:
        st.error(error_msg)
    elif payload is not None:
        st.success("✅ Đã giải mã thành công! Dữ liệu đã bị xóa khỏi máy chủ.")
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
                    label=f"⬇️ Tải file: {filename} ({format_size(len(raw_data))})",
                    data=raw_data,
                    file_name=filename,
                    mime=mime_type,
                    type="primary",
                    use_container_width=True,
                )
            except (binascii.Error, ValueError):
                st.error("❌ Không thể đọc tệp đính kèm.")

    st.write("---")
    if st.button("🏠 Trở về trang chủ", type="secondary", use_container_width=True):
        st.session_state.decrypted_cache.pop(url_id, None)
        st.query_params.clear()
        st.rerun()


# ============================================================
# LUỒNG NGƯỜI GỬI
# ============================================================

else:
    if not st.session_state.generated_link:
        st.title("🌌 TIN NHẮN TỰ ĐỘNG XÓA")
        st.markdown(
            '<p class="subtitle">Link sẽ tự động hủy ngay sau khi được mở và tự hết hạn sau 24 giờ nếu không ai mở.</p>',
            unsafe_allow_html=True,
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
            label_visibility="collapsed",
        )

        text_input = st.text_area(
            "Hoặc nhập tin nhắn văn bản:",
            height=120,
            placeholder="Bạn muốn gửi gì đi kèm?",
        )

        st.write("")
        if st.button("Tạo link chia sẻ", type="primary", use_container_width=True):
            message = text_input.strip()
            has_file = uploaded_file is not None and bool(uploaded_file.name)

            if not message and not has_file:
                st.warning("Vui lòng chọn file hoặc nhập tin nhắn.")
            elif has_file and (uploaded_file.size or 0) > MAX_FILE_SIZE_BYTES:
                st.error(
                    f"❌ File quá lớn ({format_size(uploaded_file.size)}). "
                    f"Giới hạn tối đa {format_size(MAX_FILE_SIZE_BYTES)}."
                )
            else:
                try:
                    message_id = str(uuid.uuid4())
                    secret_key = Fernet.generate_key()

                    file_b64 = ""
                    filename = ""
                    mime_type = "application/octet-stream"
                    file_size = 0

                    if has_file:
                        file_bytes = uploaded_file.getvalue()
                        file_b64 = base64.b64encode(file_bytes).decode("ascii")
                        filename = uploaded_file.name
                        mime_type = uploaded_file.type or "application/octet-stream"
                        file_size = len(file_bytes)

                    payload = {
                        "text": message,
                        "filename": filename,
                        "mime_type": mime_type,
                        "filedata": file_b64,
                        "filesize": file_size,
                    }

                    encrypted_payload = Fernet(secret_key).encrypt(
                        json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    )

                    with STORE_LOCK:
                        cleanup_expired_entries()
                        enforce_store_capacity()
                        STORE[message_id] = {
                            "data": encrypted_payload,
                            "created": time.time(),
                        }

                    share_base_url = get_share_base_url()
                    params = {
                        "id": message_id,
                        "secret": secret_key.decode("ascii"),
                    }
                    full_link = f"{share_base_url}/?{urllib.parse.urlencode(params)}"

                    st.session_state.generated_link = full_link
                    st.session_state.generated_message_id = message_id
                    st.rerun()
                except Exception:
                    st.error("❌ Không thể tạo link, vui lòng thử lại.")

    else:
        st.title("✅ Link đã tạo!")
        st.markdown(
            """
            <p class="subtitle">
            Copy link để chia sẻ. Dữ liệu sẽ <b>tự động hủy</b> ngay sau lần mở đầu tiên,
            hoặc tự hết hạn sau 24 giờ nếu không có ai mở.
            </p>
            """,
            unsafe_allow_html=True,
        )

        st.code(st.session_state.generated_link, language="text")
        st.write("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✏️ Tạo link mới", type="primary", use_container_width=True):
                st.session_state.generated_link = ""
                st.session_state.generated_message_id = ""
                st.rerun()
        with col2:
            if st.button("🗑️ Hủy Link Ngay Lập Tức", type="secondary", use_container_width=True):
                with STORE_LOCK:
                    STORE.pop(st.session_state.generated_message_id, None)
                st.session_state.generated_link = ""
                st.session_state.generated_message_id = ""
                st.rerun()
