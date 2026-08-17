import streamlit as st
import uuid
import json
import base64
import html
import urllib.parse
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
# CSS GIAO DIỆN (PHÔNG ARIAL, GỌN GÀNG, HIỆN ĐẠI)
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
# BỘ NHỚ RAM TẠM THỜI (STORE)
# ============================================================

@st.cache_resource
def get_memory_store():
    return {}

store = get_memory_store()


# ============================================================
# HÀM TIỆN ÍCH
# ============================================================

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
# SESSION STATE ĐỂ GIỮ LINK KHÔNG BỊ RELOAD
# ============================================================

if "generated_link" not in st.session_state:
    st.session_state.generated_link = ""

if "generated_message_id" not in st.session_state:
    st.session_state.generated_message_id = ""


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

    if not valid_uuid(url_id) or url_id not in store:
        st.error("❌ Tin nhắn không tồn tại, đã hết hạn hoặc ĐÃ BỊ MỞ VÀ TIÊU HỦY TRƯỚC ĐÓ!")
    else:
        # Lấy dữ liệu ra và xóa sạch vĩnh viễn khỏi RAM ngay lập tức (Atomic Pop)
        encrypted_data = store.pop(url_id)

        try:
            cipher = Fernet(url_secret.encode("ascii"))
            decrypted = cipher.decrypt(encrypted_data)
            payload = json.loads(decrypted.decode("utf-8"))

            st.success("✅ Tin nhắn đã được mở thành công.")
            st.warning(
                "⚠️ Tin nhắn đã tự động bị xóa vĩnh viễn khỏi máy chủ. "
                "Vui lòng lưu lại nội dung hoặc tải tệp ngay bây giờ, không tải lại trang này!"
            )

            st.write("---")

            # Hiển thị Tin nhắn
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

            # Hiển thị File & Nút tải về
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

        except InvalidToken:
            st.error("❌ Khóa giải mã không hợp lệ hoặc dữ liệu bị hỏng.")
        except Exception:
            st.error("❌ Đã có lỗi xảy ra khi xử lý dữ liệu.")

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

    st.write("---")

    if st.button("🚀 TẠO LINK BẢO MẬT", type="primary", use_container_width=True):
        if not text_input.strip() and uploaded_file is None:
            st.warning("Vui lòng nhập tin nhắn hoặc chọn một file.")
        elif len(text_input) > MAX_MESSAGE_LENGTH:
            st.error(f"Nội dung vượt quá {MAX_MESSAGE_LENGTH:,} ký tự.")
        else:
            try:
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

                # Lưu thẳng vào RAM (store)
                store[message_id] = encrypted_payload

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

                st.success("✅ Đã mã hóa và tạo link thành công.")

            except Exception as exc:
                st.error("❌ Không thể tạo link.")
                st.code(str(exc))

    if st.session_state.generated_link:
        st.write("---")
        st.markdown("### 🔗 LINK CỦA BẠN")
        st.success("✅ Link đã được tạo thành công.")
        
        st.code(st.session_state.generated_link, language="text")
        st.info("💡 Copy toàn bộ link và gửi trực tiếp cho người nhận.")

        st.markdown(
            """
            <div class="security-box">
            🔐 Mã hóa: Fernet AES-256
            <br>
            👤 Số lần mở tối đa: 1 lần duy nhất
            <br>
            🗑️ Trạng thái: Tự hủy ngay lập tức sau khi đọc
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🗑️ HỦY LINK NGAY", use_container_width=True):
            if st.session_state.generated_message_id in store:
                del store[st.session_state.generated_message_id]
                st.success("✅ Link đã bị hủy thành công.")
            else:
                st.info("Link không còn tồn tại hoặc đã được mở trước đó.")

            st.session_state.generated_link = ""
            st.session_state.generated_message_id = ""
            st.rerun()
