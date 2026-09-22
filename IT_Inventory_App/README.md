# Ứng Dụng Quản Lý Vật Tư & Thiết Bị Mạng IT (IT Inventory App)

Hệ thống quản lý kho vật tư thiết bị mạng, máy chủ và phụ kiện IT dành cho doanh nghiệp, hỗ trợ đa thiết bị trong cùng mạng Wi-Fi/LAN.

---

## 🌟 Tính Năng Nổi Bật

1. **Dashboard Thống Kê Trực Quan**:
   - Thống kê tổng chủng loại, tổng số lượng tồn kho.
   - Cảnh báo tự động các thiết bị sắp hết hàng (tồn kho $\le$ 2 đơn vị).
   - Đếm số lượng thiết bị gửi bảo hành.
   - Biểu đồ tỷ trọng chủng loại thiết bị và phân bổ trạng thái trực quan.
   - Nhật ký 5 giao dịch nhập/xuất kho gần nhất.

2. **Quản Lý Danh Mục Vật Tư & Thiết Bị**:
   - Tìm kiếm nhanh theo tên, Serial Number (S/N), vị trí kho, ghi chú.
   - Lọc theo phân loại (Router, Switch, Wi-Fi AP, Firewall, Cáp & Phụ kiện, SFP...) và trạng thái.
   - Thêm mới, chỉnh sửa thông tin chi tiết, xóa thiết bị.
   - Thao tác nhanh: Xuất kho / Nhập kho trực tiếp từ danh sách.

3. **Quản Lý Nhập / Xuất / Thu Hồi Kho**:
   - Phiếu xuất kho: tự động kiểm tra số lượng tồn kho và chặn xuất vượt số lượng hiện có.
   - Phiếu nhập kho: tự động cộng dồn số lượng và cập nhật trạng thái kho ("Hết hàng" $\to$ "Sẵn sàng").
   - Phiếu thu hồi: nhận lại thiết bị đã cấp phát từ các phòng ban.
   - Lưu trữ người bàn giao, người nhận, phòng ban, thời gian chính xác từng giây.

4. **Xuất Báo Cáo Excel Chuẩn (.xlsx)**:
   - Xuất danh mục tồn kho toàn bộ thiết bị.
   - Xuất toàn bộ lịch sử giao dịch Nhập/Xuất kho.
   - Tự động căn chỉnh độ rộng cột, style màu header chuyên nghiệp.

5. **Hỗ Trợ Mạng LAN (0.0.0.0:8000)**:
   - Tự động phát hiện IP LAN (`192.168.x.x`) để máy tính/điện thoại khác trong mạng truy cập mượt mà.

---

## 📁 Cấu Trúc Dự Án

```
D:\AI\IT_Inventory_App\
│
├── app.py              # Backend Flask chính (REST API & Routing)
├── models.py           # Tầng CSDL SQLite, Khởi tạo bảng & Dữ liệu mẫu
├── database.db         # File CSDL SQLite
├── requirements.txt    # Thư viện phụ thuộc (Flask, openpyxl)
├── run.bat             # File khởi động nhanh 1-click trên Windows
├── README.md           # Hướng dẫn chi tiết
│
├── templates/
│   └── index.html      # Giao diện đơn trang hiện đại (Bootstrap 5, Icons)
│
└── static/
    ├── css/
    │   └── style.css   # Tùy biến giao diện (Gradients, Badges, Cards)
    └── js/
        └── app.js      # Logic Client (Fetch REST API, Modals, UI Event)
```

---

## 🚀 Hướng Dẫn Khởi Chạy

### Cách 1: Chạy bằng file `run.bat`
Click đúp chuột vào file `run.bat` tại thư mục `D:\AI\IT_Inventory_App`.

### Cách 2: Chạy qua Terminal / Command Prompt
```bash
cd D:\AI\IT_Inventory_App
"C:\Python314\python.exe" app.py
```

Sau khi server khởi động:
- **Truy cập từ máy chủ**: `http://127.0.0.1:8000` hoặc `http://localhost:8000`
- **Truy cập từ các máy khác trong cùng Wi-Fi/LAN**: `http://<IP_MAY_CHU>:8000` (ví dụ: `http://192.168.1.8:8000`)
