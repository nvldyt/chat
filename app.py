import streamlit as st
import uuid
import json
import base64
import hashlib
import hmac
import secrets
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

    .warning-box {
        background-color: #fff7ed;
        border: 2px solid #fdba74;
        border-radius: 14px;
        padding: 16px 20px;
        margin: 15px 0;
        color: #9a3412;
    }

    .pin-box {
        background-color: #fefce8;
        border: 2px solid #fde047;
        border-radius: 14px;
        padding: 18px 20px;
        margin: 15px 0;
        text-align: center;
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
    """
    st.cache_resource chỉ dùng để cache CONNECTION.
    Không dùng nó để lưu dữ liệu tin nhắn.
    """
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


def pin_hash(pin: str) -> str:
    """
    Dùng PEPPER nằm trong Streamlit Secrets.
    Không lưu PIN dạng plaintext.
    """
    try:
        pepper = st.secrets["PIN_PEPPER"]
    except Exception:
        # Trường hợp không sử dụng PIN thì hàm này không được gọi.
        raise RuntimeError("Thiếu PIN_PEPPER trong Streamlit Secrets.")

    return hmac.new(
        pepper.encode("utf-8"),
        pin.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_pin() -> str:
    """
    PIN 6 chữ số ngẫu nhiên.
    """
    return f"{secrets.randbelow(1_000_000):06d}"


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
# LUA SCRIPT
#
# Kiểm tra secret_hash + pin_hash rồi mới:
#   1. lấy payload
#   2. xóa record
#
# Điều này giúp thao tác "mở 1 lần" mang tính nguyên tử.
# ============================================================

ATOMIC_CONSUME_SCRIPT = """
local stored_secret_hash = redis.call("HGET", KEYS[1], "secret_hash")

if not stored_secret_hash then
    return false
end

if stored_secret_hash ~= ARGV[1] then
    return false
end

local stored_pin_hash = redis.call("HGET", KEYS[1], "pin_hash")
local supplied_pin_hash = ARGV[2]

if stored_pin_hash ~= "" then

    if supplied_pin_hash == "" then
        return false
    end

    if stored_pin_hash ~= supplied_pin_hash then
        return false
    end
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
    use_pin: bool,
):
    # --------------------------------------------------------
    # ID
    # --------------------------------------------------------

    message_id = str(uuid.uuid4())

    # --------------------------------------------------------
    # SECRET KEY
    # --------------------------------------------------------

    secret_key = Fernet.generate_key()

    # --------------------------------------------------------
    # PIN
    # --------------------------------------------------------

    generated_pin = None

    if use_pin:
        generated_pin = generate_pin()

    # --------------------------------------------------------
    # FILE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # PAYLOAD
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # ENCRYPT
    # --------------------------------------------------------

    cipher = Fernet(secret_key)
    encrypted_payload = cipher.encrypt(plaintext)

    # --------------------------------------------------------
    # HASH SECRET
    # --------------------------------------------------------

    secret_hash = sha256_hex(secret_key)

    if use_pin:
        stored_pin_hash = pin_hash(generated_pin)
    else:
        stored_pin_hash = ""

    # --------------------------------------------------------
    # LƯU REDIS
    # --------------------------------------------------------

    redis_record = redis_key(message_id)

    rdb.hset(
        redis_record,
        mapping={
            b"secret_hash": secret_hash.encode("ascii"),
            b"pin_hash": stored_pin_hash.encode("ascii"),
            b"payload": encrypted_payload,
        },
    )

    # TTL
    rdb.expire(redis_record, ttl_seconds)

    # --------------------------------------------------------
    # TẠO URL
    # --------------------------------------------------------

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
        "pin": generated_pin,
        "ttl_seconds": ttl_seconds,
    }


# ============================================================
# LẤY VÀ XÓA SECRET
# ============================================================

def consume_secret(
    message_id: str,
    secret: str,
    supplied_pin: str = "",
):

    if not valid_uuid(message_id):
        return None, "ID không hợp lệ."

    try:
        secret_bytes = secret.encode("ascii")
    except Exception:
        return None, "Secret không hợp lệ."

    # Fernet key phải hợp lệ
    try:
        Fernet(secret_bytes)
    except Exception:
        return None, "Secret không hợp lệ."

    calculated_secret_hash = sha256_hex(secret_bytes)

    if supplied_pin:
        supplied_pin = supplied_pin.strip()

        if not (
            supplied_pin.isdigit()
            and len(supplied_pin) == 6
        ):
            return None, "PIN phải gồm đúng 6 chữ số."

        supplied_pin_hash = pin_hash(supplied_pin)
    else:
        supplied_pin_hash = ""

    key = redis_key(message_id)

    try:
        encrypted_payload = rdb.eval(
            ATOMIC_CONSUME_SCRIPT,
            1,
            key,
            calculated_secret_hash,
            supplied_pin_hash,
        )

    except Exception:
        return None, "Lỗi kết nối máy chủ."

    if not encrypted_payload:
        return None, "Link không tồn tại, đã hết hạn, đã được mở hoặc PIN không đúng."

    # --------------------------------------------------------
    # GIẢI MÃ
    # --------------------------------------------------------

    try:
        cipher = Fernet(secret_bytes)

        decrypted = cipher.decrypt(
            encrypted_payload
        )

        payload = json.loads(
            decrypted.decode("utf-8")
        )

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

if "generated_pin" not in st.session_state:
    st.session_state.generated_pin = ""

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
        🗑️ Link chỉ có thể được sử dụng một lần.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Cho phép nhập PIN nếu link yêu cầu.
    #
    # Vì server chỉ lưu hash PIN nên không thể biết trước
    # link có PIN hay không chỉ từ URL.
    # Người dùng nhập PIN nếu link người gửi có đặt PIN.
    # --------------------------------------------------------

    supplied_pin = ""

    with st.expander("🔐 Link có PIN? Nhập PIN tại đây"):

        supplied_pin = st.text_input(
            "PIN 6 chữ số:",
            type="password",
            max_chars=6,
            placeholder="Nhập PIN nếu người gửi cung cấp",
        )

    # --------------------------------------------------------
    # Mở tin nhắn
    # --------------------------------------------------------

    if st.button(
        "🔓 MỞ TIN NHẮN",
        type="primary",
        use_container_width=True,
    ):

        payload, error_message = consume_secret(
            url_id,
            url_secret,
            supplied_pin,
        )

        if error_message:

            st.error(f"❌ {error_message}")

        else:

            st.success(
                "✅ Tin nhắn đã được mở thành công."
            )

            st.warning(
                "⚠️ Tin nhắn đã được xóa khỏi máy chủ "
                "ngay sau khi được mở. Không tải lại trang "
                "nếu bạn chưa lưu tệp."
            )

            st.write("---")

            # ------------------------------------------------
            # MESSAGE
            # ------------------------------------------------

            msg_text = payload.get("text", "")

            if msg_text:

                st.markdown(
                    "### 📝 Nội dung tin nhắn:"
                )

                # QUAN TRỌNG:
                # Escape dữ liệu người dùng để tránh XSS.
                safe_text = html.escape(
                    msg_text
                )

                st.markdown(
                    f"""
                    <div class="message-box">
                    {safe_text}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # ------------------------------------------------
            # FILE
            # ------------------------------------------------

            filename = payload.get(
                "filename",
                "",
            )

            filedata_b64 = payload.get(
                "filedata",
                "",
            )

            mime_type = payload.get(
                "mime_type",
                "application/octet-stream",
            )

            file_size = payload.get(
                "filesize",
                0,
            )

            if filename and filedata_b64:

                st.markdown(
                    "### 📁 Tệp đính kèm:"
                )

                safe_filename = html.escape(
                    filename
                )

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

                    raw_data = base64.b64decode(
                        filedata_b64,
                        validate=True,
                    )

                    st.download_button(
                        label=f"📥 TẢI XUỐNG: {filename}",
                        data=raw_data,
                        file_name=filename,
                        mime=mime_type,
                        type="primary",
                        use_container_width=True,
                    )

                except Exception:

                    st.error(
                        "❌ Không thể đọc tệp đính kèm."
                    )

    st.write("---")

    if st.button(
        "🏠 Về trang chủ",
        use_container_width=True,
    ):

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
        Dữ liệu được mã hóa trước khi lưu vào Redis
        và tự động hết hạn sau thời gian bạn chọn.
        """
    )

    st.write("---")

    st.markdown("### 📦 Tạo tin nhắn")

    # --------------------------------------------------------
    # MESSAGE
    # --------------------------------------------------------

    text_input = st.text_area(
        "📝 Nội dung tin nhắn:",
        height=180,
        max_chars=MAX_MESSAGE_LENGTH,
        placeholder="Nhập nội dung cần gửi...",
    )

    # --------------------------------------------------------
    # FILE
    # --------------------------------------------------------

    uploaded_file = st.file_uploader(
        f"📎 Đính kèm File (tối đa {MAX_FILE_SIZE_MB} MB):",
    )

    if uploaded_file:

        if uploaded_file.size > MAX_FILE_SIZE_BYTES:

            st.error(
                f"❌ File vượt quá "
                f"{MAX_FILE_SIZE_MB} MB."
            )

            uploaded_file = None

        else:

            st.info(
                f"📁 {uploaded_file.name} — "
                f"{format_size(uploaded_file.size)}"
            )

    # --------------------------------------------------------
    # TTL
    # --------------------------------------------------------

    st.markdown("### ⏱ Thời hạn link")

    ttl_label = st.selectbox(
        "Link tự động hết hạn sau:",
        list(TTL_OPTIONS.keys()),
        index=1,
    )

    ttl_seconds = TTL_OPTIONS[ttl_label]

    # --------------------------------------------------------
    # PIN
    # --------------------------------------------------------

    st.markdown("### 🔐 Bảo vệ bằng PIN")

    use_pin = st.checkbox(
        "Yêu cầu PIN khi mở link",
        value=False,
    )

    if use_pin:

        st.info(
            "PIN sẽ không nằm trong đường link. "
            "Bạn cần gửi PIN riêng cho người nhận."
        )

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------

    if st.button(
        "🚀 TẠO LINK BẢO MẬT",
        type="primary",
        use_container_width=True,
    ):

        # Kiểm tra nội dung
        if (
            not text_input.strip()
            and uploaded_file is None
        ):

            st.warning(
                "Vui lòng nhập tin nhắn hoặc chọn một file."
            )

        elif len(text_input) > MAX_MESSAGE_LENGTH:

            st.error(
                f"Nội dung vượt quá "
                f"{MAX_MESSAGE_LENGTH:,} ký tự."
            )

        else:

            try:

                result = create_secret(
                    message_text=text_input,
                    uploaded_file=uploaded_file,
                    ttl_seconds=ttl_seconds,
                    use_pin=use_pin,
                )

                # Lưu thông tin giao diện vào session
                st.session_state.generated_link = (
                    result["link"]
                )

                st.session_state.generated_pin = (
                    result["pin"] or ""
                )

                st.session_state.generated_message_id = (
                    result["message_id"]
                )

                st.session_state.generated_ttl = (
                    result["ttl_seconds"]
                )

                st.success(
                    "✅ Đã mã hóa và lưu an toàn."
                )

            except Exception as exc:

                st.error(
                    "❌ Không thể tạo link."
                )

                st.code(
                    str(exc)
                )

    # --------------------------------------------------------
    # HIỂN THỊ LINK
    # --------------------------------------------------------

    if st.session_state.generated_link:

        st.write("---")

        st.markdown(
            "### 🔗 LINK CỦA BẠN"
        )

        st.success(
            "✅ Link đã được tạo thành công."
        )

        st.code(
            st.session_state.generated_link,
            language="text",
        )

        st.info(
            "💡 Copy toàn bộ link và gửi cho người nhận."
        )

        # ----------------------------------------------------
        # PIN
        # ----------------------------------------------------

        if st.session_state.generated_pin:

            st.markdown(
                f"""
                <div class="pin-box">
                    <div style="font-size:16px;">
                        🔐 PIN mở tin nhắn
                    </div>
                    <div style="
                        font-size:34px;
                        font-weight:800;
                        letter-spacing:8px;
                        margin-top:8px;
                    ">
                        {st.session_state.generated_pin}
                    </div>
                    <div style="
                        font-size:14px;
                        margin-top:8px;
                    ">
                        Không gửi PIN cùng với link nếu
                        cần tăng mức bảo mật.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------
        # THỜI GIAN
        # ----------------------------------------------------

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
            🔐 Mã hóa: Fernet
            <br>
            ⏱ Thời hạn: {ttl_display}
            <br>
            👤 Số lần mở tối đa: 1
            <br>
            🗑️ Sau khi mở: xóa khỏi Redis
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # REVOKE
        # ----------------------------------------------------

        if st.button(
            "🗑️ HỦY LINK NGAY",
            use_container_width=True,
        ):

            deleted = revoke_secret(
                st.session_state.generated_message_id
            )

            if deleted:

                st.success(
                    "✅ Link đã bị hủy."
                )

            else:

                st.info(
                    "Link không còn tồn tại "
                    "hoặc đã được mở."
                )

            # Reset
            st.session_state.generated_link = ""
            st.session_state.generated_pin = ""
            st.session_state.generated_message_id = ""
            st.session_state.generated_ttl = 0

            st.rerun()

        st.caption(
            "⚠️ Không gửi lại PIN trong cùng một kênh "
            "với link nếu tài liệu nhạy cảm."
        )
