import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")

def get_connection():
    """Tạo kết nối tới SQLite và trả về đối tượng kết nối với Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Khởi tạo cấu trúc bảng, thực hiện migration và nạp dữ liệu mẫu ban đầu nếu CSDL mới."""
    conn = get_connection()
    cursor = conn.cursor()

    # Bảng vật tư, thiết bị
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        serial_number TEXT UNIQUE,
        quantity INTEGER NOT NULL DEFAULT 0,
        unit TEXT DEFAULT 'Cái',
        location TEXT,
        site_name TEXT DEFAULT 'Trụ sở chính',
        status TEXT NOT NULL DEFAULT 'Sẵn sàng trong kho',
        warranty_end TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # Bảng giao dịch Nhập/Xuất kho
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        item_name TEXT NOT NULL,
        type TEXT NOT NULL, -- 'Xuất kho', 'Nhập kho', 'Thu hồi'
        quantity INTEGER NOT NULL,
        unit TEXT DEFAULT 'Cái',
        performer TEXT NOT NULL,
        recipient TEXT,
        department TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE SET NULL
    );
    """)

    conn.commit()

    # Migration: Đảm bảo bảng items luôn có cột site_name
    cursor.execute("PRAGMA table_info(items);")
    existing_cols = [col["name"] for col in cursor.fetchall()]
    if "site_name" not in existing_cols:
        cursor.execute("ALTER TABLE items ADD COLUMN site_name TEXT DEFAULT 'Trụ sở chính';")
        conn.commit()

    # Cập nhật các dòng hiện có nếu site_name bị NULL
    cursor.execute("UPDATE items SET site_name = 'Trụ sở chính' WHERE site_name IS NULL OR site_name = '';")
    conn.commit()

    # Kiểm tra xem có dữ liệu chưa, nếu chưa thì nạp dữ liệu mẫu thực tế
    cursor.execute("SELECT COUNT(*) as count FROM items;")
    row = cursor.fetchone()
    if row["count"] == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sample_items = [
            ("Router DrayTek Vigor 2927", "Router Gateway", "DT2927-VN8891", 4, "Cái", "Kệ A1 - Tầng 1", "Trụ sở chính", "Sẵn sàng trong kho", "2027-12-31", "Router cân bằng tải 2 WAN"),
            ("Switch Ruijie RG-NBS3100-24GT4SFP", "Core Switch", "RJ3100-24GT-092", 3, "Cái", "Tủ Rack T1 - Phòng Server", "Trụ sở chính", "Sẵn sàng trong kho", "2028-06-30", "Switch quản lý L2 24 port Gigabit"),
            ("Access Point Ruijie Reyee RG-RAP2260(E)", "Wi-Fi Access Point", "RAP2260E-AX011", 10, "Cái", "Kệ B2 - Kho chính", "Chi nhánh Cầu Giấy", "Sẵn sàng trong kho", "2027-08-15", "Wi-Fi 6 tốc độ cao 3200Mbps"),
            ("Firewall Fortinet FortiGate 60F", "Tường lửa (Firewall)", "FG60F-TK0981", 1, "Cái", "Tủ Server Tầng 3", "Data Center / Server Room", "Đang sử dụng", "2026-11-20", "Cổng mạng an ninh trung tâm"),
            ("Cáp mạng CommScope Cat6 UTP 305m", "Vật tư phụ / Dây cáp", "CS-CAT6-305M-04", 7, "Cuộn", "Kho Tầng 1", "Trụ sở chính", "Sẵn sàng trong kho", "", "Cáp đồng nguyên chất bấm đầu mạng"),
            ("Hạt mạng RJ45 Cat6 chống nhiễu (Hộp 100c)", "Vật tư phụ / Dây cáp", "RJ45-FTP-B100", 12, "Hộp", "Kệ C1", "Trụ sở chính", "Sẵn sàng trong kho", "", "Đầu bấm hạt mạng mạ vàng"),
            ("Module Quang Cisco SFP+ 10G SR", "Phụ kiện quang", "SFP10G-SR-CS02", 2, "Cái", "Hộp linh kiện B1", "Chi nhánh BH", "Sắp hết hàng", "2027-01-10", "Chuẩn bị đặt thêm 10 module"),
            ("Transceiver SFP Quang Gigabit Bidi 20km Single-mode", "Phụ kiện quang", "SFP-BIDI-1G-20K-88", 6, "Cái", "Hộp linh kiện B2", "Chi nhánh BH", "Sẵn sàng trong kho", "2027-05-20", "Transceiver quang SFP 1 sợi Bidi 1.25Gbps"),
            ("Thanh Patch Panel Cat6 24-Port CommScope", "Vật tư phụ / Dây cáp", "PP-CAT6-24P-AMP", 4, "Cái", "Kệ B1 - Tủ Rack", "Chi nhánh TP. Hồ Chí Minh", "Sẵn sàng trong kho", "2028-01-01", "Patch panel chuẩn rack 19 inch 1U"),
            ("Bộ lưu điện UPS APC Smart-UPS 1500VA", "Nguồn / UPS", "APC-SMT1500-77", 1, "Cái", "Phòng Kỹ thuật", "Chi nhánh TP. Hồ Chí Minh", "Đang bảo hành", "2026-10-15", "Đang gửi hãng bảo hành ắc quy")
        ]

        for item in sample_items:
            cursor.execute("""
            INSERT INTO items (name, category, serial_number, quantity, unit, location, site_name, status, warranty_end, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (*item, now, now))

        cursor.execute("SELECT id, name, unit FROM items WHERE serial_number='RAP2260E-AX011';")
        ap_item = cursor.fetchone()
        if ap_item:
            cursor.execute("""
            INSERT INTO transactions (item_id, item_name, type, quantity, unit, performer, recipient, department, notes, created_at)
            VALUES (?, ?, 'Xuất kho', 2, ?, 'Nguyễn Văn An (Admin)', 'Trần Thị Bình', 'Phòng Kinh Doanh (Tầng 2)', 'Lắp thêm Wi-Fi tầng 2', ?);
            """, (ap_item["id"], ap_item["name"], ap_item["unit"], now))

        cursor.execute("SELECT id, name, unit FROM items WHERE serial_number='CS-CAT6-305M-04';")
        cable_item = cursor.fetchone()
        if cable_item:
            cursor.execute("""
            INSERT INTO transactions (item_id, item_name, type, quantity, unit, performer, recipient, department, notes, created_at)
            VALUES (?, ?, 'Xuất kho', 1, ?, 'Nguyễn Văn An (Admin)', 'Lê Hoàng Long', 'Đội Kỹ thuật Triển khai', 'Thi công nhánh mạng tầng 4', ?);
            """, (cable_item["id"], cable_item["name"], cable_item["unit"], now))

        conn.commit()

    conn.close()

# Các hàm thao tác CSDL cho Items
def get_all_items(search="", category="", status="", site_name=""):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM items WHERE 1=1"
    params = []

    if search:
        query += " AND (name LIKE ? OR serial_number LIKE ? OR location LIKE ? OR notes LIKE ? OR site_name LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s])

    if category:
        query += " AND category = ?"
        params.append(category)

    if status:
        query += " AND status = ?"
        params.append(status)

    if site_name:
        query += " AND site_name = ?"
        params.append(site_name)

    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items

def get_item_by_id(item_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_item(data):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO items (name, category, serial_number, quantity, unit, location, site_name, status, warranty_end, notes, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("name", "").strip(),
        data.get("category", "").strip(),
        data.get("serial_number", "").strip() or None,
        int(data.get("quantity", 0)),
        data.get("unit", "Cái").strip() or "Cái",
        data.get("location", "").strip(),
        data.get("site_name", "Trụ sở chính").strip() or "Trụ sở chính",
        data.get("status", "Sẵn sàng trong kho").strip() or "Sẵn sàng trong kho",
        data.get("warranty_end", "").strip() or None,
        data.get("notes", "").strip(),
        now,
        now
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def update_item(item_id, data):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    UPDATE items
    SET name = ?, category = ?, serial_number = ?, quantity = ?, unit = ?, location = ?,
        site_name = ?, status = ?, warranty_end = ?, notes = ?, updated_at = ?
    WHERE id = ?
    """, (
        data.get("name", "").strip(),
        data.get("category", "").strip(),
        data.get("serial_number", "").strip() or None,
        int(data.get("quantity", 0)),
        data.get("unit", "Cái").strip() or "Cái",
        data.get("location", "").strip(),
        data.get("site_name", "Trụ sở chính").strip() or "Trụ sở chính",
        data.get("status", "Sẵn sàng trong kho").strip() or "Sẵn sàng trong kho",
        data.get("warranty_end", "").strip() or None,
        data.get("notes", "").strip(),
        now,
        item_id
    ))
    conn.commit()
    conn.close()
    return True

def delete_item(item_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return True

# Các hàm thao tác Transactions
def get_all_transactions(search="", tx_type=""):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []

    if search:
        query += " AND (item_name LIKE ? OR performer LIKE ? OR recipient LIKE ? OR department LIKE ? OR notes LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s])

    if tx_type:
        query += " AND type = ?"
        params.append(tx_type)

    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    txs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return txs

def create_transaction(data):
    """
    Tạo một giao dịch Nhập/Xuất/Thu hồi kho.
    Đồng thời cập nhật tự động số lượng trong bảng items.
    """
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    item_id = data.get("item_id")
    tx_type = data.get("type", "Xuất kho").strip()
    qty = int(data.get("quantity", 1))

    # Kiểm tra tồn tại item
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        raise ValueError(f"Không tìm thấy vật tư có ID {item_id}")

    current_qty = item["quantity"]

    if tx_type == "Xuất kho":
        if current_qty < qty:
            conn.close()
            raise ValueError(f"Số lượng trong kho không đủ (Hiện còn: {current_qty} {item['unit']}, yêu cầu xuất: {qty} {item['unit']})")
        new_qty = current_qty - qty
    else:  # 'Nhập kho' hoặc 'Thu hồi'
        new_qty = current_qty + qty

    # Tự động cập nhật status nếu số lượng về 0 hoặc ít hơn 3
    new_status = item["status"]
    if new_qty == 0:
        new_status = "Hết hàng"
    elif new_qty <= 2 and item["status"] == "Sẵn sàng trong kho":
        new_status = "Sắp hết hàng"
    elif new_qty > 2 and item["status"] in ["Hết hàng", "Sắp hết hàng"]:
        new_status = "Sẵn sàng trong kho"

    # Cập nhật số lượng item
    cursor.execute("""
    UPDATE items SET quantity = ?, status = ?, updated_at = ? WHERE id = ?
    """, (new_qty, new_status, now, item_id))

    # Thêm bản ghi giao dịch
    cursor.execute("""
    INSERT INTO transactions (item_id, item_name, type, quantity, unit, performer, recipient, department, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item_id,
        item["name"],
        tx_type,
        qty,
        item["unit"],
        data.get("performer", "").strip() or "Quản trị viên",
        data.get("recipient", "").strip() or "",
        data.get("department", "").strip() or "",
        data.get("notes", "").strip() or "",
        now
    ))

    conn.commit()
    new_tx_id = cursor.lastrowid
    conn.close()
    return new_tx_id

def get_dashboard_stats():
    """Lấy các số liệu tổng quan thống kê cho Dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total_types, COALESCE(SUM(quantity), 0) as total_quantity FROM items;")
    row_totals = cursor.fetchone()
    total_types = row_totals["total_types"]
    total_quantity = row_totals["total_quantity"]

    # Số thiết bị sắp hết hàng
    cursor.execute("SELECT COUNT(*) as low_stock FROM items WHERE quantity <= 2 OR status IN ('Sắp hết hàng', 'Hết hàng');")
    low_stock = cursor.fetchone()["low_stock"]

    # Số thiết bị đang bảo hành
    cursor.execute("SELECT COUNT(*) as warranty_count FROM items WHERE status = 'Đang bảo hành';")
    warranty_count = cursor.fetchone()["warranty_count"]

    # Danh sách thiết bị sắp hết hàng
    cursor.execute("SELECT * FROM items WHERE quantity <= 2 OR status IN ('Sắp hết hàng', 'Hết hàng') ORDER BY quantity ASC LIMIT 6;")
    low_stock_items = [dict(r) for r in cursor.fetchall()]

    # Thống kê theo Loại (Category)
    cursor.execute("SELECT category, COUNT(*) as count, SUM(quantity) as total_qty FROM items GROUP BY category ORDER BY count DESC;")
    by_category = [dict(r) for r in cursor.fetchall()]

    # Thống kê theo Cơ sở / Chi nhánh (Site)
    cursor.execute("SELECT COALESCE(site_name, 'Trụ sở chính') as site_name, COUNT(*) as count, SUM(quantity) as total_qty FROM items GROUP BY site_name ORDER BY total_qty DESC;")
    by_site = [dict(r) for r in cursor.fetchall()]

    # Thống kê theo Trạng thái (Status)
    cursor.execute("SELECT status, COUNT(*) as count FROM items GROUP BY status;")
    by_status = [dict(r) for r in cursor.fetchall()]

    # 5 giao dịch gần nhất
    cursor.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 5;")
    recent_txs = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "total_types": total_types,
        "total_quantity": total_quantity,
        "low_stock": low_stock,
        "warranty_count": warranty_count,
        "low_stock_items": low_stock_items,
        "by_category": by_category,
        "by_site": by_site,
        "by_status": by_status,
        "recent_txs": recent_txs
    }

def get_all_sites():
    """Lấy danh sách các cơ sở / chi nhánh đang có trong hệ thống."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT COALESCE(site_name, 'Trụ sở chính') as site_name FROM items WHERE site_name IS NOT NULL AND site_name != '' ORDER BY site_name ASC;")
    rows = [r["site_name"] for r in cursor.fetchall()]
    conn.close()

    default_sites = [
        "HBC", "HBC-BH", "Q12", "Q12-DHT02", "Q12-HHG", "Q12-LTR",
        "Q12-TTN17", "Q12-TTN6", "Q2", "Q2-111LDC", "Q2-BAQ2-LDC", "Q2-PC",
        "Q7-ECOGREEN", "Q9-FNL", "QGV-LDT", "QTB-NSS", "TDTT", "TPTD-DK",
        "TPTD-DXH", "TPTD-NTD", "TPTD-TML"
    ]
    # Gộp danh sách không trùng lặp
    all_sites = list(dict.fromkeys(rows + default_sites))
    return all_sites
