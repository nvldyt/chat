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
        /* Đổi toàn bộ phông chữ sang Arial */
        html, body, [class*="css"], p, h1, h2, h3, h4, h5, h6, span, div, label, li, .stMarkdown {
            font-family: 'Arial', sans-serif !important;
        }
        
        /* Hiệu ứng bo tròn và đổ bóng cho các hộp nội dung */
        .stTextArea textarea {
            border-radius: 12px !important;
            border: 1px solid #d1d5db !important;
            background-color: #f9fafb !important;
            font-size: 15px !important;
        }
        .stTextArea textarea:focus {
            border-color: #ef4444 !important;
            box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.2) !important;
        }
        
        /* Chỉnh nút bấm mượt mà hơn */
        div.stButton > button {
            border-radius: 8px !important;
            font-weight: bold !important;
            transition: all 0.2s ease !important;
        }
        div.stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #ef4444, #f97316) !important;
            border: none !important;
            box-shadow: 0 4px 6px rgba(239, 68, 68, 0.3) !important;
        }
        div.stButton > button[kind="primary"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 10px rgba(239, 68, 68, 0.4) !important;
        }
        
        /* Khung cảnh báo / Thông báo */
        .stAlert {
            border-radius: 10px !important;
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
# LUỒNG 1: GIAO DIỆN NGƯỜI NHẬN
# ============================================================
if url_id and url_key:
    st.title("🔓 Đang mở Mật Thư...")
    
    if url_id not in store:
        st.error("❌ Mật thư này không tồn tại, hoặc ĐÃ BỊ ĐỌC VÀ TIÊU HỦY TRƯỚC ĐÓ!")
    else:
        # Lấy dữ liệu ra và xóa sạch khỏi RAM (POP)
        encrypted_data = store.pop(url_id)
        
        try:
            # Dùng Key mở khóa
            cipher_suite = Fernet(url_key.encode('utf-8'))
            decrypted_json = cipher_suite.decrypt(encrypted_data)
            
            # Bung gói dữ liệu
            payload_dict = json.loads(decrypted_json.decode('utf-8'))
            msg_text = payload_dict.get("text", "")
            filename = payload_dict.get("filename", "")
            filedata_b64 = payload_dict.get("filedata", "")
            
            st.success("✅ Giải mã thành công! Mật thư này vừa bốc hơi vĩnh viễn khỏi máy chủ.")
            st.warning("⚠️ LƯU Ý: Hãy lưu lại thông tin ngay bây giờ. Nếu bạn tải lại trang (F5), dữ liệu sẽ mất trắng!")
            
            st.write("---")
            # Hiển thị Text nếu có
            if msg_text:
                st.markdown("### 📝 Tin nhắn:")
                st.text_area("Nội dung:", value=msg_text, height=200, disabled=True)
            
            # Hiển thị File nếu có
            if filedata_b64 and filename:
                st.markdown("### 📁 File đính kèm:")
                raw_data = base64.b64decode(filedata_b64)
                st.download_button(
                    label=f"⬇️ Tải file: {filename}",
                    data=raw_data,
                    file_name=filename,
                    mime="application/octet-stream",
                    type="primary"
                )
                
        except Exception as e:
            st.error("❌ Đường link bị hỏng hoặc thuật toán giải mã thất bại!")
            store[url_id] = encrypted_data # Trả lại file vào RAM nếu lỗi
            
    st.write("---")
    if st.button("Về trang chủ"):
        st.query_params.clear()
        st.rerun()

# ============================================================
# LUỒNG 2: GIAO DIỆN NGƯỜI GỬI (TRANG CHỦ)
# ============================================================
else:
    st.title("🔥 Bưu Cục Tự Hủy")
    st.markdown("Hệ thống chia sẻ File & Tin nhắn dùng **1 lần duy nhất**. Tự động hủy diệt vật lý trên máy chủ ngay khi người nhận truy cập.")
    
    with st.expander("⚙️ Cài đặt đường dẫn (Bấm để mở)"):
        base_url = st.text_input(
            "🔗 Đường dẫn gốc của ứng dụng:", 
            value="https://phongchat.streamlit.app"
        )
    
    st.write("---")
    st.markdown("### Đóng gói dữ liệu")
    
    # Cho phép nhập cả chữ và file
    text_input = st.text_area("Nhập nội dung bí mật (Không bắt buộc):", height=150)
    uploaded_file = st.file_uploader("Đính kèm File (Không bắt buộc, khuyên dùng < 50MB):")

    if st.button("🚀 Tạo Link Mật Thư", type="primary"):
        if not text_input.strip() and not uploaded_file:
            st.warning("Vui lòng nhập ít nhất một tin nhắn hoặc chọn một file!")
        else:
            # 1. TẠO KHÓA & ID CHO MẬT THƯ
            key = Fernet.generate_key()
            msg_id = str(uuid.uuid4())
            
            # 2. XỬ LÝ FILE (NẾU CÓ)
            file_b64 = ""
            filename = ""
            if uploaded_file:
                file_b64 = base64.b64encode(uploaded_file.read()).decode('utf-8')
                filename = uploaded_file.name
            
            # 3. ĐÓNG GÓI CẢ TEXT VÀ FILE VÀO CHUNG 1 PAYLOAD
            payload_dict = {
                "text": text_input.strip(),
                "filename": filename,
                "filedata": file_b64
            }
            
            # 4. MÃ HÓA CHUẨN AES-256 VÀ NÉM LÊN RAM
            cipher_suite = Fernet(key)
            encrypted_data = cipher_suite.encrypt(json.dumps(payload_dict).encode('utf-8'))
            store[msg_id] = encrypted_data
            
            # 5. TẠO ĐƯỜNG LINK GỬI ĐI
            clean_base_url = base_url.strip().rstrip('/')
            params = {"id": msg_id, "key": key.decode('utf-8')}
            full_link = f"{clean_base_url}/?{urllib.parse.urlencode(params)}"
            
            st.success("✅ Đã đóng gói và mã hóa thành công!")
            st.info("💡 COPY đường link dưới đây và gửi cho đối tác.")
            
            st.code(full_link, language="text")
            st.caption("Ngay khi có người bấm vào link này, khối dữ liệu sẽ bị rút cạn và xóa sạch vĩnh viễn.")
