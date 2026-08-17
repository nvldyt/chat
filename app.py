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

APP_TITLE = "Chia Sẻ Bảo Mật"
BASE_URL = "https://phongchat.streamlit.app"

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
# CSS GIAO DIỆN CHUẨN "WORMHOLE STYLE"
# ============================================================

st.markdown(
    """
    <style>
    /* Bắt buộc giao diện Dark Mode toàn nền */
    .stApp {
        background-color: #111319 !important;
    }
    
    /* Phông chữ tổng thể màu sáng */
    html, body, p, div, span, label, li {
        font-family: 'Arial', sans-serif !important;
        color: #e2e8f0 !important;
    }

    /* Tiêu đề hồng tím nổi bật đặc trưng của Wormhole */
    h1, h2, h3 {
        color: #ff2e93 !important;
        font-weight: 800 !important;
        letter-spacing: -0.5px !important;
    }

    /* Tùy chỉnh khung Upload file nét đứt giống giao diện kéo thả */
    [data-testid="stFileUploadDropzone"] {
        background-color: transparent !important;
        border: 2px dashed #4b5563 !important;
        border-radius: 16px !important;
        padding: 40px 20px !important;
        transition: all 0.3s ease !important;
    }
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #ff2e93 !important;
        background-color: rgba(255, 46, 147, 0.05) !important;
    }
    
    /* Ô nhập tin nhắn */
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

    /* Nút bấm (Màu tím nhạt chữ đen giống nút Select files to send) */
    div.stButton > button {
        background-color: #dcb8ff !important;
        color: #111319 !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        padding: 12px 24px !important;
        border: none !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button:hover {
        background-color: #e9d5ff !important;
        transform: translateY(-2px);
    }
    
    /* Nút bấm phụ (Hủy link) */
    div.stButton > button[kind="secondary"] {
        background-color: transparent !important;
        color: #9ca3af !important;
        border: 1px solid #4b5563 !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        color: #ef4444 !important;
        border-color: #ef4444 !important;
    }

    /* Khung code hiển thị Link */
    .stCodeBlock {
        background-color: #1f2937 !important;
        border: 1px solid #374151 !important;
        border-radius: 8px !important;
    }

    /* Khung cảnh báo */
    .stAlert {
        background-color: rgba(31, 41, 55, 0.8) !important;
        color: #e2e8f0 !important;
        border: 1px solid #374151 !important;
        border-radius: 12px !important;
    }

    /* Căn giữa chữ trong khung hiển thị tin nhắn */
    .message-box {
        background-color: #1f2937;
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 24px;
        font-size: 18px !important;
        color: #f8fafc !important;
        line-height: 1.6 !important;
        white-space: pre-wrap;
        word-break: break-word;
        margin-bottom: 20px;
        text-align: center !important; 
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

    st.title("You've got a file!")
    
    st.markdown(
        """
        <p style='color: #9ca3af; font-size: 16px;'>
        Hệ thống cho phép bạn chia sẻ dữ liệu với <b>mã hóa đầu cuối (end-to-end encryption)</b> 
        và đường link sẽ <b>tự động hủy</b>. Đảm bảo dữ liệu của bạn không tồn tại vĩnh viễn trên Internet.
        </p>
        """, 
        unsafe_allow_html=True
    )

    if url_id not in store:
        st.error("❌ Dữ liệu không tồn tại, đã hết hạn hoặc ĐÃ BỊ XÓA trước đó.")
    else:
        encrypted_data = store.pop(url_id)

        try:
            cipher = Fernet(url_secret.encode("ascii"))
            decrypted = cipher.decrypt(encrypted_data)
            payload = json.loads(decrypted.decode("utf-8"))

            st.success("✅ Đã giải mã thành công! Dữ liệu vừa bị xóa vĩnh viễn khỏi máy chủ.")

            st.write("---")

            # Hiển thị Tin nhắn (Đã căn giữa)
            msg_text = payload.get("text", "")
            if msg_text:
                safe_text = html.escape(msg_text)
                st.markdown(
                    f"""
                    <div class="message-box">
                    {safe_text}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Hiển thị Tệp đính kèm (Nút tải duy nhất)
            filename = payload.get("filename", "")
            filedata_b64 = payload.get("filedata", "")
            mime_type = payload.get("mime_type", "application/octet-stream")

            if filename and filedata_b64:
                try:
                    raw_data = base64.b64decode(filedata_b64, validate=True)
                    st.download_button(
                        label=f"⬇️ Download file: {filename}",
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
    if st.button("Trở về trang chủ", kind="secondary", use_container_width=True):
        st.query_params.clear()
        st.rerun()


# ============================================================
# LUỒNG NGƯỜI GỬI
# ============================================================

else:
    # Nếu CHƯA tạo link
    if not st.session_state.generated_link:
        st.title("Simple, private file sharing")
        
        st.markdown(
            """
            <p style='color: #9ca3af; font-size: 16px; margin-bottom: 30px;'>
            Chia sẻ file và tin nhắn với <b>mã hóa đầu cuối</b>. Link sẽ tự động hủy ngay sau khi được mở. 
            Đảm bảo quyền riêng tư tuyệt đối cho dữ liệu của bạn.
            </p>
            """, 
            unsafe_allow_html=True
        )

        uploaded_file = st.file_uploader(
            "Kéo thả hoặc chọn file để gửi (Tối đa 15MB)", 
            label_visibility="collapsed"
        )

        text_input = st.text_area(
            "Hoặc nhập tin nhắn văn bản:",
            height=120,
            placeholder="Ghi chú bí mật của bạn...",
        )

        st.write("") # Spacer
        if st.button("Tạo link chia sẻ", type="primary", use_container_width=True):
            if not text_input.strip() and uploaded_file is None:
                st.warning("Vui lòng đính kèm file hoặc nhập tin nhắn.")
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

                    # Lưu vào RAM
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
                    st.rerun()

                except Exception as exc:
                    st.error("❌ Không thể tạo link.")

    # Nếu ĐÃ tạo link (Giao diện Success giống Wormhole)
    else:
        st.title("Your file is ready to share!")
        
        st.markdown(
            """
            <p style='color: #9ca3af; font-size: 16px; margin-bottom: 20px;'>
            Copy the link to share your file. Dữ liệu sẽ <b>tự động hủy</b> ngay sau lần tải đầu tiên.
            </p>
            """, 
            unsafe_allow_html=True
        )

        # Hiển thị ô Copy link đặc trưng của Streamlit
        st.code(st.session_state.generated_link, language="text")

        st.write("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Tạo mật thư mới", type="primary", use_container_width=True):
                st.session_state.generated_link = ""
                st.session_state.generated_message_id = ""
                st.rerun()
        with col2:
            if st.button("Hủy Link Ngay Lập Tức", kind="secondary", use_container_width=True):
                if st.session_state.generated_message_id in store:
                    del store[st.session_state.generated_message_id]
                st.session_state.generated_link = ""
                st.session_state.generated_message_id = ""
                st.rerun()
