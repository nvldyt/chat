
import streamlit as st
import uuid
import json
import base64
from cryptography.fernet import Fernet
import urllib.parse

# ============================================================
# TẠO KHÔNG GIAN BỘ NHỚ TẠM (RAM) - KHÔNG GHI VÀO Ổ CỨNG
# ============================================================
@st.cache_resource
def get_memory_store():
    # Dữ liệu chỉ tồn tại trên RAM của máy chủ
    return {}

store = get_memory_store()

# ============================================================
# CẤU HÌNH GIAO DIỆN
# ============================================================
st.set_page_config(page_title="Mật Thư Tự Hủy", page_icon="🔥", layout="centered")

# Lấy các tham số (ID và KEY) từ trên thanh địa chỉ URL (Nếu có)
query_params = st.query_params
url_id = query_params.get("id")
url_key = query_params.get("key")

# ============================================================
# LUỒNG 1: GIAO DIỆN NGƯỜI NHẬN (KHI HỌ BẤM VÀO LINK CÓ CHỨA ID VÀ KEY)
# ============================================================
if url_id and url_key:
    st.title("🔓 Đang mở Mật Thư...")
    
    # Kiểm tra xem bưu kiện còn trên RAM không
    if url_id not in store:
        st.error("❌ Mật thư này không tồn tại, hoặc ĐÃ BỊ AI ĐÓ ĐỌC VÀ TIÊU HỦY TRƯỚC ĐÓ!")
    else:
        # ==========================================
        # LÕI BẢO MẬT: LẤY DỮ LIỆU RA VÀ XÓA SẠCH LUÔN KHỎI RAM (POP)
        # ==========================================
        encrypted_data = store.pop(url_id)
        
        try:
            # Dùng Key từ URL để mở khóa
            cipher_suite = Fernet(url_key.encode('utf-8'))
            decrypted_json = cipher_suite.decrypt(encrypted_data)
            
            # Bung gói dữ liệu
            payload_dict = json.loads(decrypted_json.decode('utf-8'))
            msg_type = payload_dict["type"]
            raw_data = base64.b64decode(payload_dict["data"])
            
            st.success("✅ Giải mã thành công! Mật thư này vừa bị bốc hơi vĩnh viễn khỏi máy chủ.")
            st.warning("⚠️ LƯU Ý: Hãy đọc hoặc tải file ngay bây giờ. Nếu bạn F5 (Tải lại trang), dữ liệu sẽ mất trắng!")
            
            if msg_type == "text":
                st.text_area("Nội dung bí mật của bạn:", value=raw_data.decode('utf-8'), height=300)
            elif msg_type == "file":
                filename = payload_dict["filename"]
                st.write(f"📁 **Tên file:** `{filename}`")
                st.download_button(
                    label="⬇️ Bấm để tải File xuống máy",
                    data=raw_data,
                    file_name=filename,
                    mime="application/octet-stream",
                    type="primary"
                )
                
        except Exception as e:
            st.error("❌ Đường link bị hỏng hoặc thuật toán giải mã thất bại!")
            # Trả lại file vào RAM nếu lỗi thuật toán để không mất oan dữ liệu
            store[url_id] = encrypted_data
            
    st.write("---")
    if st.button("Về trang chủ tạo mật thư mới"):
        # Xóa ID và KEY trên thanh URL để quay về giao diện gốc
        st.query_params.clear()
        st.rerun()

# ============================================================
# LUỒNG 2: GIAO DIỆN NGƯỜI GỬI (TRANG CHỦ BÌNH THƯỜNG)
# ============================================================
else:
    st.title("🔥 Bưu Cục Tự Hủy")
    st.markdown("Hệ thống chia sẻ File/Tin nhắn dùng **1 lần duy nhất**. Tự động hủy diệt vật lý trên máy chủ ngay khi người nhận truy cập.")
    
    # Để tạo được link chuẩn xác, app cần biết link gốc của chính nó
    base_url = st.text_input(
        "🔗 Đường dẫn gốc của ứng dụng (Anh hãy Copy link web hiện tại trên thanh địa chỉ dán vào đây):", 
        value="https://ten-app-cua-anh.streamlit.app"
    )
    
    st.write("---")
    msg_type = st.radio("Loại dữ liệu muốn gửi:", ["Văn bản (Text)", "File / Tài liệu đính kèm"])
    
    data_payload = None
    filename = None
    
    if msg_type == "Văn bản (Text)":
        text_input = st.text_area("Nhập nội dung bí mật:")
        if text_input:
            data_payload = text_input.encode('utf-8')
    else:
        uploaded_file = st.file_uploader("Chọn file cần gửi (Khuyên dùng < 50MB)")
        if uploaded_file:
            data_payload = uploaded_file.read()
            filename = uploaded_file.name

    if st.button("🚀 Tạo Link Mật Thư", type="primary"):
        if not data_payload:
            st.warning("Vui lòng nhập nội dung hoặc chọn file.")
        elif "ten-app-cua-anh" in base_url:
            st.warning("⚠️ Anh hãy sửa ô 'Đường dẫn gốc của ứng dụng' thành link web thật của anh nhé!")
        else:
            # 1. TẠO KHÓA & ID CHO MẬT THƯ
            key = Fernet.generate_key()
            msg_id = str(uuid.uuid4())
            
            # 2. ĐÓNG GÓI DỮ LIỆU
            payload_dict = {
                "type": "text" if msg_type == "Văn bản (Text)" else "file",
                "filename": filename,
                "data": base64.b64encode(data_payload).decode('utf-8')
            }
            
            # 3. MÃ HÓA CHUẨN AES-256 VÀ NÉM LÊN RAM
            cipher_suite = Fernet(key)
            encrypted_data = cipher_suite.encrypt(json.dumps(payload_dict).encode('utf-8'))
            store[msg_id] = encrypted_data
            
            # 4. TẠO ĐƯỜNG LINK GỬI ĐI (Chứa cả ID và KEY)
            clean_base_url = base_url.strip().rstrip('/')
            params = {"id": msg_id, "key": key.decode('utf-8')}
            full_link = f"{clean_base_url}/?{urllib.parse.urlencode(params)}"
            
            st.success("✅ Đã đóng gói và mã hóa thành công!")
            st.info("💡 COPY đường link dưới đây và gửi qua Zalo cho đối tác. Họ chỉ việc click vào là đọc được!")
            
            # Hiển thị Link để copy
            st.code(full_link, language="text")
            st.caption("Ngay khi có người bấm vào link này, khối dữ liệu lơ lửng trên RAM máy chủ sẽ bị rút cạn và xóa sạch vĩnh viễn.")
    
