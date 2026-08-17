import streamlit as st
import uuid
import json
import base64
from cryptography.fernet import Fernet
import urllib.parse

# ============================================================
# TẠO KHÔNG GIAN BỘ NHỚ TẠM (RAM)
# ============================================================
@st.cache_resource
def get_memory_store():
    return {}

store = get_memory_store()

# ============================================================
# CẤU HÌNH GIAO DIỆN & PHÔNG CHỮ ARIAL
# ============================================================
st.set_page_config(page_title="Mật Thư Tự Hủy", page_icon="🔥", layout="centered")

st.markdown(
    """
    <style>
        /* Toàn bộ văn bản dùng Arial */
        html, body, p, h1, h2, h3, h4, h5, h6, label, li, .stMarkdown, textarea, input {
            font-family: 'Arial', sans-serif !important;
        }
        
        /* Hiệu ứng ô nhập dữ liệu */
        .stTextArea textarea {
            border-radius: 12px !important;
            border: 1px solid #cbd5e1 !important;
            background-color: #f8fafc !important;
            font-size: 16px !important;
        }
        
        /* Nút bấm cỡ lớn & hiệu ứng chuyển màu */
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
        
        /* Khung hiển thị nội dung tin nhắn cho người nhận */
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
            margin-bottom: 20px;
        }

        /* Khung chứa thông tin file đính kèm */
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
    </style>
    """,
    unsafe_allow_html=True
)

# Lấy các tham số (ID và KEY) từ thanh địa chỉ URL
query_params = st.query_params
url_id = query_params.get("id")
url_key = query_params.get("key")

# ============================================================
# LUỒNG 1: GIAO DIỆN NGƯỜI NHẬN (ĐÃ NÂNG CẤP CHỮ TO & NÚT TẢI LỚN)
# ============================================================
if url_id and url_key:
    st.title("🔓 TIN NHẮN CỦA BẠN")
    
    if url_id not in store:
        st.error("❌ Tin nhắn đã bị tiêu hủy, vui lòng mở mục download để xem file !!!")
    else:
        encrypted_data = store.pop(url_id)
        
        try:
            cipher_suite = Fernet(url_key.encode('utf-8'))
            decrypted_json = cipher_suite.decrypt(encrypted_data)
            
            payload_dict = json.loads(decrypted_json.decode('utf-8'))
            msg_text = payload_dict.get("text", "")
            filename = payload_dict.get("filename", "")
            filedata_b64 = payload_dict.get("filedata", "")
            
            st.success("✅ Tin nhắn đã mở thành công và bị xóa vĩnh viễn khỏi máy chủ!")
            st.warning("⚠️ Vui lòng đọc nội dung và tải file ngay bây giờ. Nếu tải lại trang dữ liệu sẽ mất hoàn toàn!")
            
            st.write("---")
            
            # Hiển thị Tin nhắn (Chữ to, đậm, rõ nét)
            if msg_text:
                st.markdown("### 📝 Nội dung tin nhắn:")
                st.markdown(f'<div class="message-box">{msg_text}</div>', unsafe_allow_html=True)
            
            # Hiển thị File và Nút tải về lớn
            if filedata_b64 and filename:
                st.markdown("### 📁 Tệp đính kèm:")
                st.markdown(f'<div class="file-box">📎 Tệp: {filename}</div>', unsafe_allow_html=True)
                
                raw_data = base64.b64decode(filedata_b64)
                st.download_button(
                    label=f"⬇️ BẤM VÀO ĐÂY ĐỂ TẢI FILE ({filename})",
                    data=raw_data,
                    file_name=filename,
                    mime="application/octet-stream",
                    type="primary",
                    use_container_width=True
                )
                
        except Exception as e:
            st.error("❌ Đường link bị hỏng hoặc thuật toán giải mã thất bại!")
            store[url_id] = encrypted_data
            
    st.write("---")
    if st.button("Về trang chủ", use_container_width=True):
        st.query_params.clear()
        st.rerun()

# ============================================================
# LUỒNG 2: GIAO DIỆN NGƯỜI GỬI (TRANG CHỦ)
# ============================================================
else:
    st.title("🔥 HỆ THỐNG TỰ HỦY DỮ LIỆU")
    st.markdown("Chia sẻ File & Tin nhắn dùng **1 lần duy nhất**. Tự động xóa vĩnh viễn ngay khi người nhận truy cập.")
    
    st.write("---")
    st.markdown("### 📦 Gửi dữ liệu")
    
    text_input = st.text_area("Nhập nội dung tin nhắn):", height=150)
    uploaded_file = st.file_uploader("Đính kèm File:")

    if st.button("🚀 Tạo Link gửi", type="primary", use_container_width=True):
        if not text_input.strip() and not uploaded_file:
            st.warning("Vui lòng nhập ít nhất một tin nhắn hoặc chọn một file!")
        else:
            key = Fernet.generate_key()
            msg_id = str(uuid.uuid4())
            
            file_b64 = ""
            filename = ""
            if uploaded_file:
                file_b64 = base64.b64encode(uploaded_file.read()).decode('utf-8')
                filename = uploaded_file.name
            
            payload_dict = {
                "text": text_input.strip(),
                "filename": filename,
                "filedata": file_b64
            }
            
            cipher_suite = Fernet(key)
            encrypted_data = cipher_suite.encrypt(json.dumps(payload_dict).encode('utf-8'))
            store[msg_id] = encrypted_data
            
            base_url = "https://phongchat.streamlit.app"
            clean_base_url = base_url.strip().rstrip('/')
            params = {"id": msg_id, "key": key.decode('utf-8')}
            full_link = f"{clean_base_url}/?{urllib.parse.urlencode(params)}"
            
            st.success("✅ Mã hóa thành công!")
            st.info("💡 COPY đường link và gửi đi.")
            
            st.code(full_link, language="text")
            st.caption("Khi có người bấm vào link này, tin nhắn sẽ xóa vĩnh viễn.")
