import streamlit as st
import uuid
import json
import base64
import hashlib
import html
import urllib.parse
from datetime import datetime, timezone

import redis
from cryptography.fernet import Fernet, InvalidToken


# ============================================================
# CẤU HÌNH ỨNG DỤNG
# ============================================================

APP_TITLE = "CHAT"
BASE_URL = "https://phongchat.streamlit.app"

# Giới hạn file
MAX_FILE_SIZE_MB = 15
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Giới hạn tin nhắn
MAX_MESSAGE_LENGTH = 20_000

# Redis key prefix
REDIS_PREFIX = "one_time_secret:"

# Các thời gian cho phép
TTL_OPTIONS = {
    "5 phút": 5 * 60,
    "15 phút": 15 * 60,
    "1 giờ": 60 * 60,
    "24 giờ": 24 * 60,
}


# ============================================================
# CẤU HÌNH STREAMLIT
# ============================================================

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🔥",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    html, body, p, h1, h2, h3, h4, h5, h6,
    label, li, .stMarkdown, textarea, input,
    button {
        font-family: Arial, sans-serif !important;
    }

    .stTextArea textarea {
        border-radius: 12px !important;
        border: 1px solid #cbd5e1 !important;
        background-color: #f8fafc !important;
        font-size: 16px !important;
    }

    .stTextInput input {
        border-radius: 10px !important;
        font-size: 16px !important;
    }

    div.stButton > button {
        border-radius: 10px !important;
        font-weight: bold !important;
        font-size: 16px !important;
        padding: 12px 24px !important;
        transition: all 0.2s ease !important;
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #ef4444, #f97316) !important;
        border: none !important;
        color: white !important;
        box-shadow: 0 4px 10px rgba(239, 68, 68, 0.3) !important;
    }

    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(239, 68, 68, 0.4) !important;
    }

    .message-box {
        background-color: #f1f5f9;
        border: 2px solid #cbd5e1;
        border-radius: 14px;
        padding: 20px 24px;
        font-size: 19px !important;
        font-weight: 700 !important;
        color: #0f172a !important;
        line-height: 1.6 !important;
        white-space: pre-wrap;
        word-break: break-word;
        margin-bottom: 20px;
    }

    .file-box {
        background-color: #f0fdf4;
        border: 2px solid #86efac;
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 15px;
        font-size: 17px !important;
        font-weight: bold !important;
        color: #166534 !important;
    }

    .security-box {
        background-color: #eff6ff;
        border: 2px solid #93c5fd;
        border-radius: 14px;
        padding: 16px 20px;
        margin: 15px 0;
        color: #1e3a8a;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# KHỞI TẠO REDIS
# ============================================================

@st.cache_resource
def get_redis_connection():
    try:
        redis_url = st.secrets["REDIS_URL"]
    except Exception:
        raise RuntimeError(
            "Chưa cấu hình REDIS_URL trong Streamlit Secrets."
        )

    client = redis.from_url(
        redis_url,
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
    )

    client.ping()
    return client


try:
    rdb = get_redis_connection()
except Exception as exc:
    st.error("❌ Không thể kết nối Redis.")
    st.code(str(exc))
    st.stop()


# ============================================================
# HÀM TIỆN ÍCH
# ============================================================

def redis_key(message_id: str) -> str:
    return f"{REDIS_PREFIX}{message_id}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"

    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"

    return f"{size_bytes / (1024 * 1024):.2f} MB"


def valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except Exception:
        return False


# ============================================================
# LUA SCRIPT (NGUYÊN TỬ HÓA: KIỂM TRA HASH VÀ XÓA LUÔN)
# ============================================================

ATOMIC_CONSUME_SCRIPT = """
local stored_secret_hash = redis.call("HGET", KEYS[1], "secret_hash")

if not stored_secret_hash then
    return false
end

if stored_secret_hash ~= ARGV[1] then
    return false
end

local payload = redis.call("HGET", KEYS[1], "payload")

if not payload then
    return false
end

redis.call("DEL", KEYS[1])

return payload
"""


# ============================================================
# TẠO LINK
# ============================================================

def create_secret(
    message_text: str,
    uploaded_file,
    ttl_seconds: int,
):
    message_id = str(uuid.uuid4())
    secret_key = Fernet.generate_key()

    file_b64 = ""
    filename = ""
    mime_type = ""
    file_size = 0

    if uploaded_file is not None:
        file_size = uploaded_file.size or 0

        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File vượt quá giới hạn {MAX_FILE_SIZE_MB} MB."
            )

        raw_file = uploaded_file.getvalue()
        file_b64 = base64.b64encode(raw_file).decode("ascii")
        filename = uploaded_file.name
        mime_type = uploaded_file.type or "application/octet-stream"

    payload = {
        "version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "text": message_text.strip(),
        "filename": filename,
        "mime_type": mime_type,
        "filedata": file_b64,
        "filesize": file_size,
    }

    plaintext = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    cipher = Fernet(secret_key)
    encrypted_payload = cipher.encrypt(plaintext)
    secret_hash = sha256_hex(secret_key)

    redis_record = redis_key(message_id)

    rdb.hset(
        redis_record,
        mapping={
            b"secret_hash": secret_hash.encode("ascii"),
            b"payload": encrypted_payload,
        },
    )

    rdb.expire(redis_record, ttl_seconds)

    params = {
        "id": message_id,
        "secret": secret_key.decode("ascii"),
    }

    link = (
        BASE_URL.rstrip("/")
        + "/?"
        + urllib.parse.urlencode(params)
    )

    return {
        "message_id": message_id,
        "link": link,
        "ttl_seconds": ttl_seconds,
    }


# ============================================================
# LẤY VÀ XÓA SECRET
# ============================================================

def consume_secret(message_id: str, secret: str):
    if not valid_uuid(message_id):
        return None, "ID không hợp lệ."

    try:
        secret_bytes = secret.encode("ascii")
    except Exception:
        return None, "Secret không hợp lệ."

    try:
        Fernet(secret_bytes)
    except Exception:
        return None, "Secret không hợp lệ."

    calculated_secret_hash = sha256_hex(secret_bytes)
    key = redis_key(message_id)

    try:
        encrypted_payload = rdb.eval(
            ATOMIC_CONSUME_SCRIPT,
            1,
            key,
            calculated_secret_hash,
        )
    except Exception:
        return None, "Lỗi kết nối máy chủ."

    if not encrypted_payload:
        return None, "Link không tồn tại, đã hết hạn hoặc đã được mở trước đó."

    try:
        cipher = Fernet(secret_bytes)
        decrypted = cipher.decrypt(encrypted_payload)
        payload = json.loads(decrypted.decode("utf-8"))
    except InvalidToken:
        return None, "Không thể xác thực dữ liệu."
    except Exception:
        return None, "Dữ liệu không hợp lệ."

    return payload, None


# ============================================================
# HỦY LINK
# ============================================================

def revoke_secret(message_id: str) -> bool:
    if not valid_uuid(message_id):
        return False

    try:
        result = rdb.delete(redis_key(message_id))
        return result == 1
    except Exception:
        return False


# ============================================================
# SESSION STATE
# ============================================================

if "generated_link" not in st.session_state:
    st.session_state.generated_link = ""

if "generated_message_id" not in st.session_state:
    st.session_state.generated_message_id = ""

if "generated_ttl" not in st.session_state:
    st.session_state.generated_ttl = 0


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

    st.title("🔓 TIN NHẮN CỦA BẠN")

    st.markdown(
        """
        <div class="security-box">
        🔐 Dữ liệu được mã hóa riêng cho link này.
        <br>
        🗑️ Link chỉ có thể được mở và xem đúng một lần duy nhất.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Tự động mở tin nhắn ngay khi người dùng click vào link (Không cần bấm nút mở hay nhập PIN)
    payload, error_message = consume_secret(url_id, url_secret)

    if error_message:
        st.error(f"❌ {error_message}")
    else:
        st.success("✅ Tin nhắn đã được mở thành công.")
        st.warning(
            "⚠️ Tin nhắn đã tự động bị xóa vĩnh viễn khỏi máy chủ. "
            "Vui lòng lưu lại nội dung hoặc tải tệp ngay bây giờ, không tải lại trang này!"
        )

        st.write("---")

        # ----------------------------------------------------
        # MESSAGE
        # ----------------------------------------------------
        msg_text = payload.get("text", "")

        if msg_text:
            st.markdown("### 📝 Nội dung tin nhắn:")
            safe_text = html.escape(msg_text)
            st.markdown(
                f"""
                <div class="message-box">
                {safe_text}
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------
        # FILE
        # ----------------------------------------------------
        filename = payload.get("filename", "")
        filedata_b64 = payload.get("filedata", "")
        mime_type = payload.get("mime_type", "application/octet-stream")
        file_size = payload.get("filesize", 0)

        if filename and filedata_b64:
            st.markdown("### 📁 Tệp đính kèm:")
            safe_filename = html.escape(filename)

            st.markdown(
                f"""
                <div class="file-box">
                📎 {safe_filename}
                <br>
                💾 {format_size(file_size)}
                </div>
                """,
                unsafe_allow_html=True,
            )

            try:
                raw_data = base64.b64decode(filedata_b64, validate=True)
                st.download_button(
                    label=f"📎 Tải xuống tệp: {filename}",
                    data=raw_data,
                    file_name=filename,
                    mime=mime_type,
                    type="primary",
                    use_container_width=True,
                )
            except Exception:
                st.error("❌ Không thể đọc tệp đính kèm.")

    st.write("---")

    if st.button("🏠 Về trang chủ", use_container_width=True):
        st.query_params.clear()
        st.rerun()


# ============================================================
# LUỒNG NGƯỜI GỬI
# ============================================================

else:

    st.title("🔥 HỆ THỐNG TỰ HỦY DỮ LIỆU")

    st.markdown(
        """
        Gửi **tin nhắn và tệp một lần**. 
        Dữ liệu được mã hóa bảo mật tuyệt đối và tự động xóa sạch ngay sau khi người nhận bấm vào link.
        """
    )

    st.write("---")

    st.markdown("### 📦 Tạo tin nhắn")

    text_input = st.text_area(
        "📝 Nội dung tin nhắn:",
        height=180,
        max_chars=MAX_MESSAGE_LENGTH,
        placeholder="Nhập nội dung cần gửi...",
    )

    uploaded_file = st.file_uploader(
        f"📎 Đính kèm File (tối đa {MAX_FILE_SIZE_MB} MB):",
    )

    if uploaded_file:
        if uploaded_file.size > MAX_FILE_SIZE_BYTES:
            st.error(f"❌ File vượt quá giới hạn {MAX_FILE_SIZE_MB} MB.")
            uploaded_file = None
        else:
            st.info(f"📁 {uploaded_file.name} — {format_size(uploaded_file.size)}")

    st.markdown("### ⏱ Thời hạn link")

    ttl_label = st.selectbox(
        "Link tự động hết hạn sau:",
        list(TTL_OPTIONS.keys()),
        index=1,
    )

    ttl_seconds = TTL_OPTIONS[ttl_label]

    st.write("---")

    if st.button("🚀 TẠO LINK BẢO MẬT", type="primary", use_container_width=True):
        if not text_input.strip() and uploaded_file is None:
            st.warning("Vui lòng nhập tin nhắn hoặc chọn một file.")
        elif len(text_input) > MAX_MESSAGE_LENGTH:
            st.error(f"Nội dung vượt quá {MAX_MESSAGE_LENGTH:,} ký tự.")
        else:
            try:
                result = create_secret(
                    message_text=text_input,
                    uploaded_file=uploaded_file,
                    ttl_seconds=ttl_seconds,
                )

                st.session_state.generated_link = result["link"]
                st.session_state.generated_message_id = result["message_id"]
                st.session_state.generated_ttl = result["ttl_seconds"]

                st.success("✅ Đã mã hóa và lưu an toàn.")

            except Exception as exc:
                st.error("❌ Không thể tạo link.")
                st.code(str(exc))

    if st.session_state.generated_link:
        st.write("---")
        st.markdown("### 🔗 LINK CỦA BẠN")
        st.success("✅ Link đã được tạo thành công.")
        
        st.code(st.session_state.generated_link, language="text")
        st.info("💡 Copy toàn bộ link và gửi trực tiếp cho người nhận.")

        ttl = st.session_state.generated_ttl

        if ttl < 3600:
            ttl_display = f"{ttl // 60} phút"
        elif ttl < 86400:
            ttl_display = f"{ttl // 3600} giờ"
        else:
            ttl_display = "24 giờ"

        st.markdown(
            f"""
            <div class="security-box">
            🔐 Mã hóa: Fernet AES-256
            <br>
            ⏱ Thời hạn link: {ttl_display}
            <br>
            👤 Số lần mở tối đa: 1 lần duy nhất
            <br>
            🗑️ Trạng thái: Tự hủy ngay lập tức sau khi đọc
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🗑️ HỦY LINK NGAY", use_container_width=True):
            deleted = revoke_secret(st.session_state.generated_message_id)

            if deleted:
                st.success("✅ Link đã bị hủy thành công.")
            else:
                st.info("Link không còn tồn tại hoặc đã được mở trước đó.")

            st.session_state.generated_link = ""
            st.session_state.generated_message_id = ""
            st.session_state.generated_ttl = 0

            st.rerun()
