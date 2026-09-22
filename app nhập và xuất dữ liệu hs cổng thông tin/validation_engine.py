# -*- coding: utf-8 -*-
"""
================================================================================
MODULE: validation_engine.py
DỰ ÁN: HỆ THỐNG XỬ LÝ VÀ CHUẨN HÓA DỮ LIỆU HỌC SINH - SỞ GD&ĐT
================================================================================
Chức năng chính:
1. Đọc dữ liệu Excel học sinh (Sheet chính, XUAT_FILE_SO, Sheet1, ...) và tự động
   nhận diện hàng tiêu đề (header), tự động lọc bỏ các hàng ghi chú/chữ ký cuối trang.
2. Nạp và đối chiếu các Sheet danh mục chuẩn từ file mẫu Sở GD&ĐT:
   - GIOI_TINH (Nam, Nữ)
   - DAN_TOC (54 dân tộc chuẩn quốc gia + tên khác/bí danh)
   - TON_GIAO (Không, Phật giáo, Công giáo, Tin lành, Cao đài, Hòa hảo, v.v.)
   - TINH / XA_PHUONG (Danh mục chuẩn Tỉnh/TP, Xã/Phường hành chính quốc gia)
   - MA_LOI (Bảng định nghĩa mã lỗi từ mẫu hoặc bộ mã chuẩn quốc tế)
3. Tự động Chuẩn hóa Dữ liệu (Auto-Fix):
   - Họ và tên: .upper() và chuẩn hóa khoảng trắng (" nguyễn  văn a " -> "NGUYỄN VĂN A").
   - Ngày sinh / Ngày cấp: Ép kiểu chuẩn về dd/MM/yyyy (VD: 2020-05-15 -> 15/05/2020).
   - Mã Định danh 12 số / CCCD / SĐT: Giữ lại ký tự số, bù số 0 ở đầu nếu bị Excel cắt,
     thêm dấu nháy đơn ' ở đầu để bảo toàn định dạng text trong Excel (VD: 79123456789 -> '079123456789).
   - Trạng thái học sinh: Map chuẩn hóa Học kỳ 1 -> "Chuyển đến kỳ 1", Học kỳ 2 -> "Chuyển đến kỳ 2",
     Trong hè -> "Chuyển đến trong hè".
4. Bộ Quy tắc Kiểm tra Lỗi (Validation Rules):
   - R1 (Bắt buộc): Họ tên, Ngày sinh, Giới tính, Mã định danh 12 số không được để trống.
   - R2 (Số định danh / CCCD): Đúng 12 chữ số. Nếu sai độ dài hoặc chứa chữ cái -> Lỗi ERR_01.
   - R3 (Số điện thoại): Bắt đầu bằng số 0 và đúng 10 chữ số -> Lỗi ERR_04.
   - R4 (Đối chiếu Danh mục): Dân tộc thuộc DAN_TOC, Tỉnh/TP và Phường/Xã khớp danh mục TINH/XA_PHUONG -> Lỗi ERR_03.
   - R5 (Kiểm tra trùng lặp): Cảnh báo trùng Số định danh cá nhân 12 số giữa các dòng -> Lỗi ERR_05.
5. Xuất Báo cáo Kết quả (Output Report):
   - Trả về danh sách dữ liệu đã làm sạch (list of dicts / DataFrame) sẵn sàng đẩy lên Web/API.
   - Xuất file Excel báo cáo lỗi Bao_Cao_Loi_Du_Lieu.xlsx được định dạng chuyên nghiệp.
================================================================================
"""

import os
import re
import sys
import glob
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ==============================================================================
# 1. BẢNG MÃ LỖI VÀ MÔ TẢ CHUẨN
# ==============================================================================
DEFAULT_ERROR_CATALOG: Dict[str, str] = {
    "ERR_REQUIRED": "Trường dữ liệu bắt buộc không được để trống (R1)",
    "ERR_01": "Số định danh/CCCD sai độ dài hoặc chứa ký tự không hợp lệ (R2: Yêu cầu đúng 12 chữ số)",
    "ERR_02": "Ngày sinh/Ngày cấp sai định dạng (Yêu cầu định dạng chuẩn dd/MM/yyyy)",
    "ERR_03": "Tên Tỉnh/Thành phố hoặc Phường/Xã không khớp danh mục chuẩn quốc gia (R4)",
    "ERR_04": "Số điện thoại không hợp lệ (R3: Phải bắt đầu bằng số 0 và đúng 10 chữ số)",
    "ERR_05": "Trùng lặp Số định danh cá nhân 12 số giữa các dòng trong cùng file (R5)",
    "ERR_GIOI_TINH": "Giới tính không hợp lệ (Chỉ chấp nhận 'Nam' hoặc 'Nữ' theo Sheet GIOI_TINH)",
    "ERR_DAN_TOC": "Dân tộc không có trong danh mục chuẩn quốc gia (Sheet DAN_TOC)",
    "ERR_TON_GIAO": "Tôn giáo không có trong danh mục chuẩn quốc gia (Sheet TON_GIAO)",
    "ERR_TRANG_THAI": "Trạng thái học sinh không hợp lệ (Sheet TRANG_THAI)",
}

# Danh mục 54 dân tộc Việt Nam chuẩn (fallback khi không có sheet danh mục)
DEFAULT_ETHNIC_GROUPS: Set[str] = {
    "kinh", "việt", "tày", "thái", "hoa", "khơ-me", "khơ me", "khmer", "mường", "nùng",
    "hmông", "h'mông", "h mông", "mông", "dao", "gia-rai", "gia rai", "ngái", "ê-đê", "ê đê",
    "ba-na", "ba na", "xơ-đăng", "xơ đăng", "sán chay", "cơ-ho", "cơ ho", "chăm", "chàm",
    "sán dìu", "hrê", "mnông", "m'nông", "ra-glai", "ra glai", "xinh-mun", "xinh mun",
    "thổ", "x-tiêng", "xtiêng", "x tiêng", "bru - vân kiều", "bru-vân kiều", "bru vân kiều",
    "cơ-tu", "cơ tu", "giáy", "giẻ-triêng", "giẻ triêng", "mạ", "lô lô", "lô-lô", "chơ-ro",
    "chơ ro", "hà nhì", "la chí", "la-chí", "la ha", "la-ha", "phù lá", "phù-lá", "la hủ",
    "la-hủ", "lự", "lự", "chứt", "lào", "mảng", "pà thẻn", "pà-thẻn", "co", "cống",
    "bố y", "bố-y", "si la", "si-la", "pu péo", "pu-péo", "brâu", "rơ-măm", "rơ măm",
    "ơ đu", "ơ-đu"
}

# Danh mục Tôn giáo chuẩn theo Ban Tôn giáo Chính phủ (fallback)
DEFAULT_RELIGIONS: Set[str] = {
    "không", "khong", "phật giáo", "công giáo", "tin lành", "cao đài", "hòa hảo", "phật giáo hòa hảo",
    "hồi giáo", "bà-la-môn", "bà la môn", "tứ ân hiếu nghĩa", "bửu sơn kỳ hương",
    "minh sư đạo", "minh lý đạo", "baha'i", "bahai", "tịnh độ cư sĩ phật hội"
}


# ==============================================================================
# 2. DATA CLASSES QUẢN LÝ LỖI VÀ BÁO CÁO
# ==============================================================================
@dataclass
class ValidationError:
    """Đại diện cho một lỗi phát hiện trên một ô dữ liệu của học sinh."""
    row_index: int          # Số dòng trên file Excel (1-based index)
    student_name: str       # Họ và tên học sinh (đã chuẩn hóa hoặc giá trị hiện có)
    column_name: str        # Tên cột bị lỗi
    error_code: str         # Mã lỗi (ERR_01, ERR_02, ERR_03, ...)
    error_message: str      # Chi tiết lỗi và hướng dẫn khắc phục
    raw_value: Any = None   # Giá trị gốc trước khi xử lý

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Dòng số": self.row_index,
            "Họ tên học sinh": self.student_name,
            "Cột bị lỗi": self.column_name,
            "Mã lỗi": self.error_code,
            "Chi tiết lỗi": self.error_message,
            "Giá trị gốc": str(self.raw_value) if self.raw_value is not None else ""
        }


@dataclass
class ValidationReport:
    """Báo cáo tổng hợp sau khi làm sạch và kiểm tra dữ liệu."""
    is_valid: bool
    total_records: int
    valid_records: int
    error_records: int
    errors: List[ValidationError] = field(default_factory=list)
    cleaned_data: List[Dict[str, Any]] = field(default_factory=list)
    raw_df: Optional[pd.DataFrame] = None
    cleaned_df: Optional[pd.DataFrame] = None
    summary_by_code: Dict[str, int] = field(default_factory=dict)

    def print_summary(self):
        """In tóm tắt kết quả kiểm tra ra màn hình console."""
        print("=" * 60)
        print("           KẾT QUẢ KIỂM TRA VÀ CHUẨN HÓA DỮ LIỆU")
        print("=" * 60)
        print(f"Tổng số bản ghi học sinh:    {self.total_records}")
        print(f"Số bản ghi hợp lệ:            {self.valid_records}")
        print(f"Số bản ghi có lỗi:            {self.error_records}")
        print(f"Tổng số lỗi phát hiện:        {len(self.errors)}")
        print(f"Trạng thái tổng thể:          {'HỢP LỆ (SẴN SÀNG)' if self.is_valid else 'CẦN CHỈNH SỬA'}")
        if self.summary_by_code:
            print("\nThống kê theo mã lỗi:")
            for code, count in self.summary_by_code.items():
                desc = DEFAULT_ERROR_CATALOG.get(code, "Lỗi nghiệp vụ")
                print(f"  - [{code}] {desc}: {count} lỗi")
        print("=" * 60)

    def to_excel_report(self, output_path: str = "Bao_Cao_Loi_Du_Lieu.xlsx") -> str:
        """Xuất file Excel báo cáo lỗi theo định dạng chuyên nghiệp chuẩn Sở GD&ĐT."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Bao_Cao_Loi"

        # Định dạng styles
        title_font = Font(name="Calibri", size=14, bold=True, color="1F4E78")
        meta_font = Font(name="Calibri", size=11, italic=True)
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        cell_font = Font(name="Calibri", size=11)
        err_code_font = Font(name="Calibri", size=11, bold=True, color="C00000")

        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

        thin_border_side = Side(style="thin", color="D3D3D3")
        grid_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

        # Tiêu đề báo cáo
        ws.merge_cells("A1:F1")
        ws["A1"] = "BÁO CÁO KẾT QUẢ KIỂM TRA LỖI DỮ LIỆU HỌC SINH"
        ws["A1"].font = title_font
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 30

        # Thông tin tổng quan
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        ws["A2"] = f"Thời gian kiểm tra: {now_str} | Tổng số bản ghi: {self.total_records} | Bản ghi hợp lệ: {self.valid_records} | Số lỗi: {len(self.errors)}"
        ws["A2"].font = meta_font
        ws.row_dimensions[2].height = 20

        # Tiêu đề bảng
        headers = ["STT", "Dòng số (Excel)", "Họ tên học sinh", "Cột bị lỗi", "Mã lỗi", "Chi tiết lỗi", "Giá trị gốc"]
        header_row = 4
        ws.row_dimensions[header_row].height = 25

        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=header_row, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = grid_border

        # Điền dữ liệu lỗi
        if not self.errors:
            ws.cell(row=5, column=1, value=1)
            ws.cell(row=5, column=2, value="-")
            ws.cell(row=5, column=3, value="TẤT CẢ DỮ LIỆU ĐÃ HỢP LỆ")
            ws.cell(row=5, column=4, value="-")
            ws.cell(row=5, column=5, value="OK")
            ws.cell(row=5, column=6, value="Không phát hiện lỗi vi phạm nào. Dữ liệu đã sạch và sẵn sàng tải lên hệ thống.")
            ws.cell(row=5, column=7, value="")
            for c in range(1, 8):
                ws.cell(row=5, column=c).border = grid_border
        else:
            for idx, err in enumerate(self.errors, 1):
                cur_row = header_row + idx
                ws.row_dimensions[cur_row].height = 22

                c1 = ws.cell(row=cur_row, column=1, value=idx)
                c2 = ws.cell(row=cur_row, column=2, value=err.row_index)
                c3 = ws.cell(row=cur_row, column=3, value=err.student_name)
                c4 = ws.cell(row=cur_row, column=4, value=err.column_name)
                c5 = ws.cell(row=cur_row, column=5, value=err.error_code)
                c6 = ws.cell(row=cur_row, column=6, value=err.error_message)
                c7 = ws.cell(row=cur_row, column=7, value=str(err.raw_value) if err.raw_value is not None else "")

                c1.alignment = Alignment(horizontal="center", vertical="center")
                c2.alignment = Alignment(horizontal="center", vertical="center")
                c3.alignment = Alignment(horizontal="left", vertical="center")
                c4.alignment = Alignment(horizontal="left", vertical="center")
                c5.alignment = Alignment(horizontal="center", vertical="center")
                c6.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                c7.alignment = Alignment(horizontal="left", vertical="center")

                c1.font = cell_font
                c2.font = cell_font
                c3.font = Font(name="Calibri", size=11, bold=True)
                c4.font = cell_font
                c5.font = err_code_font
                c6.font = cell_font
                c7.font = cell_font

                fill_to_apply = zebra_fill if idx % 2 == 0 else None
                for c in [c1, c2, c3, c4, c5, c6, c7]:
                    c.border = grid_border
                    if fill_to_apply:
                        c.fill = fill_to_apply

        # Tự căn chỉnh độ rộng cột
        col_widths = {1: 8, 2: 16, 3: 26, 4: 24, 5: 14, 6: 48, 7: 20}
        for col_idx, width in col_widths.items():
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = width

        wb.save(output_path)
        return os.path.abspath(output_path)

    def to_excel_cleaned(self, output_path: str = "Du_Lieu_Da_Chuan_Hoa.xlsx") -> str:
        """Xuất toàn bộ bảng dữ liệu đã qua chuẩn hóa (Auto-Fix) sang file Excel."""
        if self.cleaned_df is not None and not self.cleaned_df.empty:
            df_export = self.cleaned_df.copy()
        elif self.cleaned_data:
            df_export = pd.DataFrame(self.cleaned_data)
        else:
            df_export = pd.DataFrame()

        df_export.to_excel(output_path, index=False)
        return os.path.abspath(output_path)


# ==============================================================================
# 3. CLASS NẠP VÀ ĐỐI CHIẾU DANH MỤC (CatalogManager)
# ==============================================================================
class CatalogManager:
    """Quản lý các Sheet danh mục đối chiếu chuẩn từ Sở GD&ĐT."""

    def __init__(self, catalog_file_path: Optional[str] = None):
        self.catalog_file_path = catalog_file_path
        self.genders: Set[str] = {"Nam", "Nữ"}
        self.ethnic_groups: Set[str] = set(DEFAULT_ETHNIC_GROUPS)
        self.religions: Set[str] = set(DEFAULT_RELIGIONS)
        self.provinces: Set[str] = set()
        self.province_codes: Dict[str, str] = {}
        self.wards: Set[str] = set()
        self.wards_by_province: Dict[str, Set[str]] = {}
        self.error_codes: Dict[str, str] = dict(DEFAULT_ERROR_CATALOG)
        self.student_statuses: Set[str] = {
            "đang học", "chuyển đến kỳ 1", "chuyển đến kỳ 2", "chuyển đến trong hè",
            "thôi học", "nghỉ học", "chuyển đi"
        }

        # Luôn nạp danh mục nền mặc định
        self._load_default_provinces()

        if catalog_file_path and os.path.exists(catalog_file_path):
            self.load_from_file(catalog_file_path)

    def _normalize_text(self, text: Any) -> str:
        """Làm sạch khoảng trắng thừa và đưa về chữ thường để so sánh."""
        if text is None or pd.isna(text):
            return ""
        s = str(text).strip()
        s = re.sub(r"\s+", " ", s)
        return s.lower()

    def _load_default_provinces(self):
        """Khởi tạo danh sách 63 Tỉnh/TP mặc định của Việt Nam."""
        vn_provinces = [
            "Thành phố Hà Nội", "Thành phố Hồ Chí Minh", "Thành phố Hải Phòng", "Thành phố Đà Nẵng",
            "Thành phố Cần Thơ", "Thành phố Huế", "Tỉnh Hà Giang", "Tỉnh Cao Bằng", "Tỉnh Bắc Kạn",
            "Tỉnh Tuyên Quang", "Tỉnh Lào Cai", "Tỉnh Điện Biên", "Tỉnh Lai Châu", "Tỉnh Sơn La",
            "Tỉnh Yên Bái", "Tỉnh Hoà Bình", "Tỉnh Thái Nguyên", "Tỉnh Lạng Sơn", "Tỉnh Quảng Ninh",
            "Tỉnh Bắc Giang", "Tỉnh Phú Thọ", "Tỉnh Vĩnh Phúc", "Tỉnh Bắc Ninh", "Tỉnh Hải Dương",
            "Tỉnh Hưng Yên", "Tỉnh Thái Bình", "Tỉnh Hà Nam", "Tỉnh Nam Định", "Tỉnh Ninh Bình",
            "Tỉnh Thanh Hóa", "Tỉnh Nghệ An", "Tỉnh Hà Tĩnh", "Tỉnh Quảng Bình", "Tỉnh Quảng Trị",
            "Tỉnh Thừa Thiên Huế", "Tỉnh Quảng Nam", "Tỉnh Quảng Ngãi", "Tỉnh Bình Định",
            "Tỉnh Phú Yên", "Tỉnh Khánh Hòa", "Tỉnh Ninh Thuận", "Tỉnh Bình Thuận", "Tỉnh Kon Tum",
            "Tỉnh Gia Lai", "Tỉnh Đắk Lắk", "Tỉnh Đắk Nông", "Tỉnh Lâm Đồng", "Tỉnh Bình Phước",
            "Tỉnh Tây Ninh", "Tỉnh Bình Dương", "Tỉnh Đồng Nai", "Tỉnh Bà Rịa - Vũng Tàu",
            "Tỉnh Long An", "Tỉnh Tiền Giang", "Tỉnh Bến Tre", "Tỉnh Trà Vinh", "Tỉnh Vĩnh Long",
            "Tỉnh Đồng Tháp", "Tỉnh An Giang", "Tỉnh Kiên Giang", "Tỉnh Hậu Giang", "Tỉnh Sóc Trăng",
            "Tỉnh Bạc Liêu", "Tỉnh Cà Mau"
        ]
        for p in vn_provinces:
            norm = self._normalize_text(p)
            self.provinces.add(norm)
            # Thêm biến thể ngắn gọn: "Hà Nội" thay cho "Thành phố Hà Nội"
            short_p = re.sub(r"^(thành phố|tỉnh)\s+", "", norm).strip()
            self.provinces.add(short_p)

    def load_from_file(self, file_path: str):
        """Đọc toàn bộ các sheet danh mục đối chiếu từ file Excel mẫu."""
        try:
            with pd.ExcelFile(file_path) as xl:
                sheet_names = xl.sheet_names

                # 1. Đọc Sheet GIOI_TINH
                if "GIOI_TINH" in sheet_names:
                    df = xl.parse("GIOI_TINH", header=None)
                    self._parse_gender_sheet(df)

                # 2. Đọc Sheet DAN_TOC
                if "DAN_TOC" in sheet_names:
                    df = xl.parse("DAN_TOC", header=None)
                    self._parse_ethnic_sheet(df)

                # 3. Đọc Sheet TON_GIAO
                if "TON_GIAO" in sheet_names:
                    df = xl.parse("TON_GIAO", header=None)
                    self._parse_religion_sheet(df)

                # 4. Đọc Sheet TINH
                if "TINH" in sheet_names:
                    df = xl.parse("TINH", header=None)
                    self._parse_province_sheet(df)

                # 5. Đọc Sheet XA_PHUONG
                if "XA_PHUONG" in sheet_names:
                    df = xl.parse("XA_PHUONG", header=None)
                    self._parse_ward_sheet(df)

                # 6. Đọc Sheet MA_LOI
                if "MA_LOI" in sheet_names:
                    df = xl.parse("MA_LOI", header=None)
                    self._parse_error_sheet(df)

                # 7. Đọc Sheet TRANG_THAI
                if "TRANG_THAI" in sheet_names:
                    df = xl.parse("TRANG_THAI", header=None)
                    self._parse_status_sheet(df)

        except Exception as e:
            print(f"[CẢNH BÁO] Không thể nạp đầy đủ danh mục từ file {file_path}: {e}")
            self._load_default_provinces()

    def _parse_gender_sheet(self, df: pd.DataFrame):
        for row_idx in range(len(df)):
            row = df.iloc[row_idx].dropna().tolist()
            for val in row:
                s = str(val).strip()
                if s in ["Nam", "Nữ"]:
                    self.genders.add(s)

    def _parse_ethnic_sheet(self, df: pd.DataFrame):
        # Tìm header hàng chứa "Tên dân tộc"
        header_row = None
        col_ten = 2
        col_khac = 3
        for r_idx in range(min(10, len(df))):
            vals = [str(x).strip() for x in df.iloc[r_idx].values if pd.notna(x)]
            for c_idx, val in enumerate(df.iloc[r_idx].values):
                if pd.notna(val) and "tên dân tộc" in str(val).lower():
                    header_row = r_idx
                    col_ten = c_idx
                elif pd.notna(val) and "tên khác" in str(val).lower():
                    col_khac = c_idx

        start_row = (header_row + 1) if header_row is not None else 2
        for r_idx in range(start_row, len(df)):
            val = df.iloc[r_idx, col_ten] if col_ten < df.shape[1] else None
            if pd.notna(val):
                norm = self._normalize_text(val)
                if norm:
                    self.ethnic_groups.add(norm)
            if col_khac < df.shape[1]:
                alias_val = df.iloc[r_idx, col_khac]
                if pd.notna(alias_val):
                    for alias in str(alias_val).split(","):
                        norm_alias = self._normalize_text(alias)
                        if norm_alias:
                            self.ethnic_groups.add(norm_alias)

    def _parse_religion_sheet(self, df: pd.DataFrame):
        for r_idx in range(len(df)):
            row = df.iloc[r_idx].dropna().tolist()
            for val in row:
                norm = self._normalize_text(val)
                if norm and not norm.isdigit() and norm not in ["stt", "mã", "tên", "tên tôn giáo"]:
                    self.religions.add(norm)

    def _parse_province_sheet(self, df: pd.DataFrame):
        header_row = None
        col_code = 1
        col_name = 2
        for r_idx in range(min(6, len(df))):
            for c_idx, val in enumerate(df.iloc[r_idx].values):
                if pd.notna(val):
                    txt = str(val).lower().strip()
                    if "tên tỉnh" in txt or "tên" in txt:
                        header_row = r_idx
                        col_name = c_idx
                    elif "mã" in txt:
                        col_code = c_idx

        start_row = (header_row + 1) if header_row is not None else 3
        for r_idx in range(start_row, len(df)):
            name_val = df.iloc[r_idx, col_name] if col_name < df.shape[1] else None
            code_val = df.iloc[r_idx, col_code] if col_code < df.shape[1] else None
            if pd.notna(name_val):
                p_name = str(name_val).strip()
                norm = self._normalize_text(p_name)
                self.provinces.add(norm)
                # Biến thể không có tiền tố Tỉnh / Thành phố
                short_p = re.sub(r"^(thành phố|tỉnh)\s+", "", norm).strip()
                self.provinces.add(short_p)
                if pd.notna(code_val):
                    code_str = str(code_val).strip().zfill(2)
                    self.province_codes[norm] = code_str
                    self.province_codes[short_p] = code_str

    def _parse_ward_sheet(self, df: pd.DataFrame):
        header_row = None
        col_name = 2
        col_prov_name = 5
        for r_idx in range(min(6, len(df))):
            for c_idx, val in enumerate(df.iloc[r_idx].values):
                if pd.notna(val):
                    txt = str(val).lower().strip()
                    if txt in ["tên", "tên xã/phường", "xã/phường"]:
                        header_row = r_idx
                        col_name = c_idx
                    elif "tỉnh / thành phố" in txt or "tỉnh" in txt:
                        col_prov_name = c_idx

        start_row = (header_row + 1) if header_row is not None else 3
        for r_idx in range(start_row, len(df)):
            w_val = df.iloc[r_idx, col_name] if col_name < df.shape[1] else None
            p_val = df.iloc[r_idx, col_prov_name] if col_prov_name < df.shape[1] else None
            if pd.notna(w_val):
                w_norm = self._normalize_text(w_val)
                if w_norm:
                    self.wards.add(w_norm)
                    # Biến thể bỏ chữ Phường / Xã / Thị trấn
                    short_w = re.sub(r"^(phường|xã|thị trấn)\s+", "", w_norm).strip()
                    self.wards.add(short_w)

                    if pd.notna(p_val):
                        p_norm = self._normalize_text(p_val)
                        if p_norm not in self.wards_by_province:
                            self.wards_by_province[p_norm] = set()
                        self.wards_by_province[p_norm].add(w_norm)
                        self.wards_by_province[p_norm].add(short_w)

    def _parse_error_sheet(self, df: pd.DataFrame):
        for r_idx in range(len(df)):
            row = df.iloc[r_idx].dropna().tolist()
            if len(row) >= 2:
                code = str(row[0]).strip()
                desc = str(row[1]).strip()
                if code.isdigit():
                    code = f"ERR_{code.zfill(2)}"
                self.error_codes[code] = desc

    def _parse_status_sheet(self, df: pd.DataFrame):
        for r_idx in range(len(df)):
            row = df.iloc[r_idx].dropna().tolist()
            for val in row:
                norm = self._normalize_text(val)
                if norm and not norm.isdigit() and norm not in ["stt", "mã", "tên"]:
                    self.student_statuses.add(norm)

    def is_valid_gender(self, gender: str) -> bool:
        if not gender:
            return False
        return gender.strip().lower() in {"nam", "nữ", "nu"}

    def is_valid_ethnic(self, ethnic: str) -> bool:
        if not ethnic:
            return False
        norm = self._normalize_text(ethnic)
        return norm in self.ethnic_groups

    def is_valid_religion(self, religion: str) -> bool:
        if not religion:
            return True  # Cho phép để trống hoặc mặc định "Không"
        norm = self._normalize_text(religion)
        return norm in self.religions or norm in ["không", "khong"]

    def is_valid_province(self, province: str) -> bool:
        if not province:
            return False
        norm = self._normalize_text(province)
        if norm in self.provinces:
            return True
        # Bỏ tiền tố
        short_p = re.sub(r"^(thành phố|tỉnh)\s+", "", norm).strip()
        return short_p in self.provinces

    def is_valid_ward(self, ward: str, province: Optional[str] = None) -> bool:
        if not ward:
            return False
        norm = self._normalize_text(ward)
        if norm in self.wards:
            return True
        short_w = re.sub(r"^(phường|xã|thị trấn)\s+", "", norm).strip()
        if short_w in self.wards:
            return True

        # Nếu có tỉnh đi kèm, kiểm tra trong phạm vi tỉnh
        if province:
            p_norm = self._normalize_text(province)
            if p_norm in self.wards_by_province:
                if norm in self.wards_by_province[p_norm] or short_w in self.wards_by_province[p_norm]:
                    return True
        return False


# ==============================================================================
# 4. BỘ CHUẨN HÓA DỮ LIỆU TỰ ĐỘNG (Auto-Fix Normalizer)
# ==============================================================================
class DataNormalizer:
    """Thực hiện các thao tác làm sạch và chuẩn hóa dữ liệu tự động (Auto-Fix)."""

    @staticmethod
    def normalize_name(name: Any) -> str:
        """Họ và tên: Tự động .upper() và xóa khoảng trắng thừa đầu/cuối/giữa."""
        if name is None or pd.isna(name):
            return ""
        s = str(name).strip()
        s = re.sub(r"\s+", " ", s)
        return s.upper()

    @staticmethod
    def normalize_date(val: Any) -> Tuple[str, bool]:
        """
        Ngày tháng năm sinh / Ngày cấp: Ép kiểu về dạng dd/MM/yyyy.
        Trả về (chuỗi_ngày, is_valid).
        """
        if val is None or pd.isna(val) or str(val).strip() == "":
            return "", False

        # Nếu đã là datetime / Timestamp / date
        if isinstance(val, (datetime, date, pd.Timestamp)):
            return val.strftime("%d/%m/%Y"), True

        # Nếu là số nguyên / số thực (Excel date serial number)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            try:
                # Excel origin: 1899-12-30
                dt = pd.to_datetime(val, unit="D", origin="1899-12-30")
                if 1900 <= dt.year <= 2100:
                    return dt.strftime("%d/%m/%Y"), True
            except Exception:
                pass

        s = str(val).strip()
        # Loại bỏ phần thời gian nếu có (VD: 2021-08-10 00:00:00)
        s = re.split(r"[\sT]", s)[0].strip()

        # Thử các định dạng ngày thông dụng
        date_patterns = [
            ("%Y-%m-%d", r"^\d{4}-\d{1,2}-\d{1,2}$"),
            ("%Y/%m/%d", r"^\d{4}/\d{1,2}/\d{1,2}$"),
            ("%d/%m/%Y", r"^\d{1,2}/\d{1,2}/\d{4}$"),
            ("%d-%m-%Y", r"^\d{1,2}-\d{1,2}-\d{4}$"),
            ("%d.%m.%Y", r"^\d{1,2}\.\d{1,2}\.\d{4}$"),
            ("%Y%m%d",   r"^\d{8}$"),
        ]

        for fmt, regex in date_patterns:
            if re.match(regex, s):
                try:
                    dt = datetime.strptime(s, fmt)
                    if 1900 <= dt.year <= 2100:
                        return dt.strftime("%d/%m/%Y"), True
                except ValueError:
                    pass

        # Parse tự do bằng dateutil/pandas nếu chuỗi phức tạp
        try:
            dt = pd.to_datetime(s, dayfirst=True)
            if pd.notna(dt) and 1900 <= dt.year <= 2100:
                return dt.strftime("%d/%m/%Y"), True
        except Exception:
            pass

        return s, False

    @staticmethod
    def normalize_id_code(val: Any) -> Tuple[str, str, bool]:
        """
        Mã Định danh 12 số / CCCD:
        - Giữ lại ký tự số.
        - Thêm '0' ở đầu nếu bị mất số 0 (VD: 79123456789 -> '079123456789).
        - Thêm dấu nháy đơn ' ở đầu để bảo vệ số 0 đầu trong Excel.
        Trả về: (excel_string, digits_only_string, had_letters)
        """
        if val is None or pd.isna(val) or str(val).strip() == "":
            return "", "", False

        raw_str = str(val).strip()
        # Loại bỏ dấu nháy đơn đầu nếu có sẵn
        if raw_str.startswith("'"):
            raw_str = raw_str[1:].strip()

        # Kiểm tra xem có chứa chữ cái hay không (để bắt lỗi ERR_01)
        had_letters = bool(re.search(r"[A-Za-z]", raw_str))

        # Xử lý số float dạng scientific notation: 7.9221E+10 -> 79221000194
        if isinstance(val, float) and not had_letters:
            raw_str = f"{int(val)}" if val.is_integer() else str(int(val))
        elif "." in raw_str and not had_letters:
            try:
                f_val = float(raw_str)
                raw_str = f"{int(f_val)}"
            except Exception:
                pass

        # Giữ lại ký tự số
        digits = re.sub(r"\D", "", raw_str)

        # Nếu bị mất số 0 đầu (11 chữ số, đầu là mã tỉnh như 79, 01, 24...)
        if len(digits) == 11:
            digits = "0" + digits
        elif len(digits) == 10 and digits.startswith("1"):
            # Ví dụ mã Hà Nội 001 bị mất 2 số 0
            digits = "00" + digits

        excel_str = f"'{digits}" if digits else ""
        return excel_str, digits, had_letters

    @staticmethod
    def normalize_phone(val: Any) -> Tuple[str, str, bool]:
        """
        Số điện thoại:
        - Giữ lại ký tự số.
        - Thay thế +84 thành 0.
        - Thêm số 0 ở đầu nếu bị Excel cắt (VD: 933441983 -> '0933441983).
        Trả về: (excel_string, digits_only_string, had_letters)
        """
        if val is None or pd.isna(val) or str(val).strip() == "":
            return "", "", False

        raw_str = str(val).strip()
        if raw_str.startswith("'"):
            raw_str = raw_str[1:].strip()

        had_letters = bool(re.search(r"[A-Za-z]", raw_str))

        if isinstance(val, float) and not had_letters:
            raw_str = f"{int(val)}"

        # Chuyển +84 thành 0
        if raw_str.startswith("+84"):
            raw_str = "0" + raw_str[3:]
        elif raw_str.startswith("84") and len(re.sub(r"\D", "", raw_str)) == 11:
            raw_str = "0" + raw_str[2:]

        digits = re.sub(r"\D", "", raw_str)

        # Nếu có 9 chữ số (bắt đầu bằng 3, 5, 7, 8, 9 - đầu số di động VN bị mất số 0 đầu)
        if len(digits) == 9 and digits[0] in "35789":
            digits = "0" + digits

        excel_str = f"'{digits}" if digits else ""
        return excel_str, digits, had_letters

    @staticmethod
    def normalize_student_status(val: Any) -> str:
        """
        Trạng thái học sinh:
        Map chuẩn hóa:
        - Học kỳ 1 -> "Chuyển đến kỳ 1"
        - Học kỳ 2 -> "Chuyển đến kỳ 2"
        - Trong hè   -> "Chuyển đến trong hè"
        """
        if val is None or pd.isna(val):
            return ""
        s = str(val).strip()
        s_lower = s.lower()

        if s_lower in ["học kỳ 1", "học kì 1", "kỳ 1", "kì 1", "hk1", "hk 1"]:
            return "Chuyển đến kỳ 1"
        if s_lower in ["học kỳ 2", "học kì 2", "kỳ 2", "kì 2", "hk2", "hk 2"]:
            return "Chuyển đến kỳ 2"
        if s_lower in ["trong hè", "trong he", "hè", "he"]:
            return "Chuyển đến trong hè"
        return s

    @staticmethod
    def normalize_gender(val: Any) -> str:
        """Chuẩn hóa Giới tính về 'Nam' hoặc 'Nữ'."""
        if val is None or pd.isna(val):
            return ""
        s = str(val).strip().lower()
        if s in ["nam", "trai"]:
            return "Nam"
        if s in ["nữ", "nu", "gái"]:
            return "Nữ"
        return str(val).strip()


# ==============================================================================
# 5. CORE VALIDATION ENGINE (Bộ máy kiểm tra và xử lý)
# ==============================================================================
class ValidationEngine:
    """Bộ máy kiểm tra, chuẩn hóa và xuất báo cáo dữ liệu học sinh."""

    def __init__(self, catalog_path: Optional[str] = None):
        """
        Khởi tạo ValidationEngine.
        Nếu catalog_path không được truyền vào, hệ thống tự động tìm kiếm file mẫu
        trong thư mục hiện tại hoặc thư mục Downloads.
        """
        self.catalog_path = catalog_path or self._auto_discover_catalog()
        self.catalog = CatalogManager(self.catalog_path)

    def _auto_discover_catalog(self) -> Optional[str]:
        """Tự động tìm kiếm file mẫu Sở GD&ĐT trong Downloads hoặc thư mục hiện tại."""
        search_dirs = [
            os.path.expanduser("~/Downloads"),
            os.getcwd(),
            os.path.join(os.path.expanduser("~"), "Desktop"),
        ]
        patterns = ["*Filemau*HocSinh*.xls*", "*Filemau*.xls*", "*DanhMuc*.xls*"]

        for d in search_dirs:
            if not os.path.exists(d):
                continue
            for pat in patterns:
                matches = glob.glob(os.path.join(d, pat))
                for m in matches:
                    fname = os.path.basename(m).lower()
                    if any(ig in fname for ig in ["bao_cao", "loi", "report", "error", "chuan_hoa", "clean"]):
                        continue
                    return m
        return None

    def read_student_excel(self, file_path: str, sheet_name: Optional[str] = None) -> Tuple[pd.DataFrame, int, str]:
        """
        Đọc file Excel dữ liệu học sinh:
        - Tự động phát hiện Sheet chính (XUAT_FILE_SO, Sheet1, hoặc sheet đầu tiên).
        - Tự động dò tìm hàng Header thực sự (bỏ qua tiêu đề Sở/Phòng/UBND).
        - Tự động loại bỏ các hàng ghi chú/chữ ký cuối bảng.
        Trả về: (DataFrame, header_excel_row_1_based, selected_sheet_name)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file Excel: {file_path}")

        with pd.ExcelFile(file_path) as xl:
            # Chọn Sheet
            target_sheet = sheet_name
            if not target_sheet:
                candidate_names = ["XUAT_FILE_SO", "Sheet1", "DANH_SACH", "Danh sách", "DATA"]
                for cand in candidate_names:
                    if cand in xl.sheet_names:
                        target_sheet = cand
                        break
                if not target_sheet:
                    target_sheet = xl.sheet_names[0]

            # Đọc thô 25 dòng đầu để dò tìm tiêu đề cột
            preview_df = xl.parse(target_sheet, header=None, nrows=25)
            header_row_idx = None

            key_columns = ["họ tên", "họ và tên", "ngày sinh", "giới tính", "định danh", "cccd", "mã học sinh", "stt"]

            for r_idx in range(len(preview_df)):
                row_vals = [str(x).strip().lower() for x in preview_df.iloc[r_idx].values if pd.notna(x)]
                row_str = " ".join(row_vals)
                matched_keys = sum(1 for k in key_columns if k in row_str)
                # Nếu dòng này khớp ít nhất 2 từ khóa cột quan trọng -> đây là Header
                if matched_keys >= 2:
                    header_row_idx = r_idx
                    break

            if header_row_idx is None:
                header_row_idx = 0

            # Đọc toàn bộ dữ liệu từ hàng header tìm được
            df = xl.parse(target_sheet, header=header_row_idx)

        # Làm sạch tên cột: strip khoảng trắng
        df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]

        # Loại bỏ các dòng trống hoàn toàn
        df = df.dropna(how="all").reset_index(drop=True)

        # Dò tìm và lọc bỏ các hàng footer như 'Người lập biểu', 'Hiệu trưởng', ...
        valid_rows = []
        name_col = self._find_column(df, ["họ tên", "họ và tên", "tên học sinh", "hoten"])

        for idx, row in df.iterrows():
            if name_col:
                name_val = row[name_col]
                if pd.isna(name_val):
                    continue
                name_str = str(name_val).strip()
                if not name_str or any(kw in name_str.lower() for kw in ["người lập", "hiệu trưởng", "giáo viên", "ghi chú", "tổng số"]):
                    continue
            valid_rows.append(idx)

        df = df.iloc[valid_rows].reset_index(drop=True)
        excel_header_row = header_row_idx + 1  # 1-based index trên Excel

        return df, excel_header_row, target_sheet

    def _find_column(self, df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
        """Tìm tên cột thực tế trong DataFrame dựa trên danh sách tên đại diện (ưu tiên theo thứ tự aliases)."""
        # Bước 1: Khớp chính xác hoàn toàn (exact match)
        for alias in aliases:
            alias_norm = re.sub(r"\s+", " ", alias.lower().strip())
            for col in df.columns:
                col_norm = re.sub(r"\s+", " ", col.lower().strip())
                if alias_norm == col_norm:
                    return col

        # Bước 2: Khớp chứa chuỗi con (substring match theo thứ tự ưu tiên của alias)
        for alias in aliases:
            alias_norm = re.sub(r"\s+", " ", alias.lower().strip())
            for col in df.columns:
                col_norm = re.sub(r"\s+", " ", col.lower().strip())
                if alias_norm in col_norm:
                    return col
        return None

    def validate_file(
        self,
        input_file: str,
        output_report_path: str = "Bao_Cao_Loi_Du_Lieu.xlsx",
        output_cleaned_path: Optional[str] = None,
        sheet_name: Optional[str] = None,
    ) -> ValidationReport:
        """
        Quy trình xử lý hoàn chỉnh (End-to-End):
        1. Đọc dữ liệu Excel đầu vào.
        2. Tự động chuẩn hóa dữ liệu (Auto-Fix).
        3. Áp dụng toàn bộ Quy tắc Kiểm tra (R1 -> R5).
        4. Xuất Báo cáo lỗi ra file Excel nếu phát hiện vi phạm.
        5. Trả về đối tượng ValidationReport chứa dữ liệu đã làm sạch.
        """
        df_raw, header_row_idx, used_sheet = self.read_student_excel(input_file, sheet_name)

        # Nếu file input chính là file mẫu hoặc có chứa sẵn các Sheet danh mục (GIOI_TINH, DAN_TOC, TINH, XA_PHUONG...)
        try:
            with pd.ExcelFile(input_file) as xl_chk:
                if any(s in xl_chk.sheet_names for s in ["XA_PHUONG", "TINH", "DAN_TOC", "GIOI_TINH"]):
                    self.catalog.load_from_file(input_file)
        except Exception:
            pass

        report = self.validate_dataframe(df_raw, header_row_idx=header_row_idx, source_name=os.path.basename(input_file))

        # Xuất file báo cáo lỗi nếu có vi phạm
        if report.errors:
            report.to_excel_report(output_report_path)
            print(f"[THÔNG BÁO] Đã xuất file Báo cáo lỗi dữ liệu: {output_report_path}")
        else:
            print("[THÀNH CÔNG] Dữ liệu hoàn toàn hợp lệ! Không có lỗi vi phạm.")

        # Xuất file dữ liệu đã làm sạch nếu được yêu cầu
        if output_cleaned_path:
            report.to_excel_cleaned(output_cleaned_path)
            print(f"[THÔNG BÁO] Đã xuất file dữ liệu đã làm sạch: {output_cleaned_path}")

        return report

    def validate_dataframe(
        self,
        df: pd.DataFrame,
        header_row_idx: int = 1,
        source_name: str = "Dữ liệu"
    ) -> ValidationReport:
        """
        Kiểm tra và chuẩn hóa một DataFrame dữ liệu học sinh.
        """
        errors: List[ValidationError] = []
        cleaned_records: List[Dict[str, Any]] = []

        # 1. Ánh xạ các cột trọng yếu
        col_name = self._find_column(df, ["họ tên", "họ và tên", "tên học sinh", "hoten"])
        col_dob = self._find_column(df, ["ngày sinh", "ngày tháng năm sinh", "ngaysinh"])
        col_gender = self._find_column(df, ["giới tính", "gioitinh", "phái"])
        col_id = self._find_column(df, [
            "số định danh cá nhân", "mã định danh cá nhân", "mã định danh 12 số",
            "số cccd", "cccd", "mã định danh bộ gd&đt", "mã định danh bộ gdđt",
            "định danh cá nhân", "mã định danh", "số định danh", "mã học sinh"
        ])
        col_phone = self._find_column(df, [
            "số điện thoại liên hệ", "sđt liên hệ", "số điện thoại",
            "sđt", "điện thoại", "dien thoai", "sdt"
        ])
        col_ethnic = self._find_column(df, ["dân tộc", "dantoc"])
        col_status = self._find_column(df, ["trạng thái hs", "trạng thái học sinh", "trạng thái", "trangthai"])
        col_religion = self._find_column(df, ["tôn giáo", "tongiao"])

        # Các cột địa chỉ Tỉnh / Xã Phường
        col_provinces = [c for c in df.columns if any(k in c.lower() for k in ["tỉnh", "thành phố", "tỉnh/thành phố"])]
        col_wards = [c for c in df.columns if any(k in c.lower() for k in ["xã/phường", "phường/xã", "xã", "phường"]) and "tỉnh" not in c.lower()]

        # Bộ nhớ theo dõi trùng lặp Mã định danh (R5)
        id_tracker: Dict[str, List[Tuple[int, str]]] = {}

        # 2. Xử lý từng dòng học sinh
        for idx, row in df.iterrows():
            excel_row = header_row_idx + 1 + idx  # Vị trí dòng thực tế trong file Excel
            row_dict = row.to_dict()
            cleaned_row = dict(row_dict)

            # Lấy họ tên trước để gán nhãn báo cáo lỗi
            raw_name = row.get(col_name) if col_name else ""
            student_name = DataNormalizer.normalize_name(raw_name) if raw_name else f"Học sinh dòng {excel_row}"

            # ------------------------------------------------------------------
            # QUY TẮC R1 & AUTO-FIX: HỌ VÀ TÊN
            # ------------------------------------------------------------------
            if not col_name or pd.isna(raw_name) or str(raw_name).strip() == "":
                errors.append(ValidationError(
                    row_index=excel_row,
                    student_name="[CHƯA CÓ TÊN]",
                    column_name=col_name or "Họ tên",
                    error_code="ERR_REQUIRED",
                    error_message="Họ và tên không được để trống (Quy tắc R1)",
                    raw_value=raw_name
                ))
            else:
                cleaned_name = DataNormalizer.normalize_name(raw_name)
                cleaned_row[col_name] = cleaned_name
                student_name = cleaned_name

            # ------------------------------------------------------------------
            # QUY TẮC R1, ERR_02 & AUTO-FIX: NGÀY SINH
            # ------------------------------------------------------------------
            raw_dob = row.get(col_dob) if col_dob else None
            if not col_dob or pd.isna(raw_dob) or str(raw_dob).strip() == "":
                errors.append(ValidationError(
                    row_index=excel_row,
                    student_name=student_name,
                    column_name=col_dob or "Ngày sinh",
                    error_code="ERR_REQUIRED",
                    error_message="Ngày sinh không được để trống (Quy tắc R1)",
                    raw_value=raw_dob
                ))
            else:
                norm_dob, is_valid_date = DataNormalizer.normalize_date(raw_dob)
                if not is_valid_date:
                    errors.append(ValidationError(
                        row_index=excel_row,
                        student_name=student_name,
                        column_name=col_dob,
                        error_code="ERR_02",
                        error_message=f"Ngày sinh sai định dạng hoặc không hợp lệ. Giá trị: '{raw_dob}', yêu cầu định dạng dd/MM/yyyy",
                        raw_value=raw_dob
                    ))
                cleaned_row[col_dob] = norm_dob

            # ------------------------------------------------------------------
            # QUY TẮC R1, R4 & AUTO-FIX: GIỚI TÍNH
            # ------------------------------------------------------------------
            raw_gender = row.get(col_gender) if col_gender else None
            if not col_gender or pd.isna(raw_gender) or str(raw_gender).strip() == "":
                errors.append(ValidationError(
                    row_index=excel_row,
                    student_name=student_name,
                    column_name=col_gender or "Giới tính",
                    error_code="ERR_REQUIRED",
                    error_message="Giới tính không được để trống (Quy tắc R1)",
                    raw_value=raw_gender
                ))
            else:
                cleaned_gender = DataNormalizer.normalize_gender(raw_gender)
                cleaned_row[col_gender] = cleaned_gender
                if not self.catalog.is_valid_gender(cleaned_gender):
                    errors.append(ValidationError(
                        row_index=excel_row,
                        student_name=student_name,
                        column_name=col_gender,
                        error_code="ERR_GIOI_TINH",
                        error_message=f"Giới tính '{raw_gender}' không hợp lệ theo Sheet GIOI_TINH (Chỉ nhận 'Nam' hoặc 'Nữ')",
                        raw_value=raw_gender
                    ))

            # ------------------------------------------------------------------
            # QUY TẮC R1, R2, R5 & AUTO-FIX: MÃ ĐỊNH DANH 12 SỐ / CCCD
            # ------------------------------------------------------------------
            raw_id = row.get(col_id) if col_id else None
            if not col_id or pd.isna(raw_id) or str(raw_id).strip() == "":
                errors.append(ValidationError(
                    row_index=excel_row,
                    student_name=student_name,
                    column_name=col_id or "Mã định danh",
                    error_code="ERR_REQUIRED",
                    error_message="Mã định danh cá nhân 12 số không được để trống (Quy tắc R1)",
                    raw_value=raw_id
                ))
            else:
                excel_id, digits_id, had_letters = DataNormalizer.normalize_id_code(raw_id)
                cleaned_row[col_id] = excel_id

                # Quy tắc R2: Phải chứa đúng 12 chữ số. Nếu sai độ dài hoặc chứa chữ cái -> Lỗi ERR_01
                if had_letters or len(digits_id) != 12:
                    reason = "chứa chữ cái/ký tự không hợp lệ" if had_letters else f"có độ dài {len(digits_id)} số (yêu cầu đúng 12 số)"
                    errors.append(ValidationError(
                        row_index=excel_row,
                        student_name=student_name,
                        column_name=col_id,
                        error_code="ERR_01",
                        error_message=f"Định danh sai: Giá trị '{raw_id}' {reason}. Cần đúng 12 chữ số CCCD/ĐDCN",
                        raw_value=raw_id
                    ))
                else:
                    # Ghi nhận để kiểm tra trùng lặp (R5)
                    if digits_id not in id_tracker:
                        id_tracker[digits_id] = []
                    id_tracker[digits_id].append((excel_row, student_name))

            # ------------------------------------------------------------------
            # QUY TẮC R3 & AUTO-FIX: SỐ ĐIỆN THOẠI
            # ------------------------------------------------------------------
            if col_phone:
                raw_phone = row.get(col_phone)
                if pd.notna(raw_phone) and str(raw_phone).strip() != "":
                    excel_phone, digits_phone, phone_had_letters = DataNormalizer.normalize_phone(raw_phone)
                    cleaned_row[col_phone] = excel_phone

                    # R3: Bắt đầu bằng số 0 và chứa đúng 10 chữ số
                    if phone_had_letters or len(digits_phone) != 10 or not digits_phone.startswith("0"):
                        errors.append(ValidationError(
                            row_index=excel_row,
                            student_name=student_name,
                            column_name=col_phone,
                            error_code="ERR_04",
                            error_message=f"Số điện thoại không hợp lệ: Giá trị '{raw_phone}' (phải bắt đầu bằng số 0 và có đúng 10 chữ số)",
                            raw_value=raw_phone
                        ))

            # ------------------------------------------------------------------
            # QUY TẮC R4 & AUTO-FIX: DÂN TỘC
            # ------------------------------------------------------------------
            if col_ethnic:
                raw_ethnic = row.get(col_ethnic)
                if pd.notna(raw_ethnic) and str(raw_ethnic).strip() != "":
                    cleaned_ethnic = re.sub(r"\s+", " ", str(raw_ethnic)).strip()
                    cleaned_row[col_ethnic] = cleaned_ethnic
                    if not self.catalog.is_valid_ethnic(cleaned_ethnic):
                        errors.append(ValidationError(
                            row_index=excel_row,
                            student_name=student_name,
                            column_name=col_ethnic,
                            error_code="ERR_DAN_TOC",
                            error_message=f"Dân tộc '{raw_ethnic}' không có trong danh mục chuẩn Sheet DAN_TOC",
                            raw_value=raw_ethnic
                        ))

            # ------------------------------------------------------------------
            # AUTO-FIX: TRẠNG THÁI HỌC SINH
            # ------------------------------------------------------------------
            if col_status:
                raw_status = row.get(col_status)
                if pd.notna(raw_status) and str(raw_status).strip() != "":
                    cleaned_status = DataNormalizer.normalize_student_status(raw_status)
                    cleaned_row[col_status] = cleaned_status

            # ------------------------------------------------------------------
            # QUY TẮC R4: TỈNH / THÀNH PHỐ VÀ PHƯỜNG / XÃ
            # ------------------------------------------------------------------
            # Kiểm tra tất cả các cột Tỉnh/Thành phố xuất hiện trong bảng
            for p_col in col_provinces:
                raw_prov = row.get(p_col)
                if pd.notna(raw_prov) and str(raw_prov).strip() != "":
                    prov_str = re.sub(r"\s+", " ", str(raw_prov)).strip()
                    cleaned_row[p_col] = prov_str
                    # Bỏ qua các giá trị ngoại lệ được phép như 'Nước ngoài', 'Khác'
                    if prov_str.lower() not in ["nước ngoài", "khác"]:
                        if not self.catalog.is_valid_province(prov_str):
                            errors.append(ValidationError(
                                row_index=excel_row,
                                student_name=student_name,
                                column_name=p_col,
                                error_code="ERR_03",
                                error_message=f"Tên Tỉnh/Thành phố '{raw_prov}' không có trong danh mục chuẩn Sheet TINH",
                                raw_value=raw_prov
                            ))

            # Kiểm tra tất cả các cột Phường/Xã xuất hiện trong bảng
            for w_col in col_wards:
                raw_ward = row.get(w_col)
                if pd.notna(raw_ward) and str(raw_ward).strip() != "":
                    ward_str = re.sub(r"\s+", " ", str(raw_ward)).strip()
                    cleaned_row[w_col] = ward_str
                    if ward_str.lower() not in ["nước ngoài", "khác"]:
                        if not self.catalog.is_valid_ward(ward_str):
                            errors.append(ValidationError(
                                row_index=excel_row,
                                student_name=student_name,
                                column_name=w_col,
                                error_code="ERR_03",
                                error_message=f"Tên Phường/Xã '{raw_ward}' không có trong danh mục chuẩn Sheet XA_PHUONG",
                                raw_value=raw_ward
                            ))

            # ------------------------------------------------------------------
            # AUTO-FIX & KIỂM TRA: CÁC CỘT NGÀY CẤP / NGÀY CẤP HỘ CHIẾU (NẾU CÓ)
            # ------------------------------------------------------------------
            for c in df.columns:
                if "ngày cấp" in c.lower() and c != col_dob:
                    raw_issue_date = row.get(c)
                    if pd.notna(raw_issue_date) and str(raw_issue_date).strip() != "":
                        norm_date, is_valid = DataNormalizer.normalize_date(raw_issue_date)
                        cleaned_row[c] = norm_date
                        if not is_valid:
                            errors.append(ValidationError(
                                row_index=excel_row,
                                student_name=student_name,
                                column_name=c,
                                error_code="ERR_02",
                                error_message=f"Ngày cấp sai định dạng dd/MM/yyyy: '{raw_issue_date}'",
                                raw_value=raw_issue_date
                            ))

            cleaned_records.append(cleaned_row)

        # ----------------------------------------------------------------------
        # QUY TẮC R5: KIỂM TRA TRÙNG LẶP MÃ ĐỊNH DANH 12 SỐ TRONG TOÀN FILE
        # ----------------------------------------------------------------------
        for code, occurrences in id_tracker.items():
            if len(occurrences) > 1:
                row_list_str = ", ".join([f"dòng {r} ({name})" for r, name in occurrences])
                for r_num, s_name in occurrences:
                    errors.append(ValidationError(
                        row_index=r_num,
                        student_name=s_name,
                        column_name=col_id or "Mã định danh",
                        error_code="ERR_05",
                        error_message=f"Trùng lặp Số định danh cá nhân '{code}' với các bản ghi khác ({row_list_str})",
                        raw_value=code
                    ))

        # Sắp xếp lỗi theo Dòng số
        errors.sort(key=lambda x: (x.row_index, x.error_code))

        # Tổng hợp thống kê
        total_records = len(df)
        error_rows = set(e.row_index for e in errors)
        valid_records = total_records - len(error_rows)
        summary_by_code: Dict[str, int] = {}
        for e in errors:
            summary_by_code[e.error_code] = summary_by_code.get(e.error_code, 0) + 1

        cleaned_df = pd.DataFrame(cleaned_records)

        return ValidationReport(
            is_valid=(len(errors) == 0),
            total_records=total_records,
            valid_records=valid_records,
            error_records=len(error_rows),
            errors=errors,
            cleaned_data=cleaned_records,
            raw_df=df,
            cleaned_df=cleaned_df,
            summary_by_code=summary_by_code
        )


# ==============================================================================
# 6. HÀM TIỆN ÍCH DÀNH CHO TÍCH HỢP WEB / API
# ==============================================================================
def get_cleaned_data_for_web(file_path: str, catalog_path: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], bool]:
    """
    Hàm API nhanh tiện lợi cho Backend Web (Flask, FastAPI, Django):
    Đọc, chuẩn hóa dữ liệu học sinh từ file tải lên.
    Trả về: (cleaned_data_list, error_list, is_all_valid)
    """
    engine = ValidationEngine(catalog_path=catalog_path)
    report = engine.validate_file(file_path, output_report_path="Bao_Cao_Loi_Du_Lieu.xlsx")
    err_dicts = [e.to_dict() for e in report.errors]
    return report.cleaned_data, err_dicts, report.is_valid


# ==============================================================================
# 7. GIAO DIỆN DÒNG LỆNH (CLI Runner)
# ==============================================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Bộ công cụ kiểm tra và chuẩn hóa dữ liệu học sinh Sở GD&ĐT (Validation Engine)"
    )
    parser.add_argument("-i", "--input", help="Đường dẫn file Excel dữ liệu học sinh cần kiểm tra", required=False)
    parser.add_argument("-c", "--catalog", help="Đường dẫn file Excel mẫu Sở GD&ĐT chứa danh mục", required=False)
    parser.add_argument("-o", "--output", default="Bao_Cao_Loi_Du_Lieu.xlsx", help="Tên file Excel báo cáo lỗi xuất ra")
    parser.add_argument("-s", "--sheet", help="Tên sheet dữ liệu học sinh (tùy chọn)", required=False)
    parser.add_argument("--clean-out", help="Tên file Excel xuất dữ liệu đã làm sạch", required=False)

    args = parser.parse_args()

    # Nếu không truyền --input, tự động tìm file học sinh trong Downloads hoặc thư mục hiện tại
    input_file = args.input
    if not input_file:
        downloads_dir = os.path.expanduser("~/Downloads")
        potential_files = [
            os.path.join(downloads_dir, "Danh_sach_hoc_sinh.xlsx"),
            os.path.join(downloads_dir, "Filemau-MN-HocSinh-DiaPhuong-ver3-data-HCM.xls"),
            os.path.join(os.getcwd(), "Danh_sach_hoc_sinh.xlsx")
        ]
        for pf in potential_files:
            if os.path.exists(pf):
                input_file = pf
                break

    if not input_file:
        print("[LỖI] Vui lòng chỉ định file Excel dữ liệu học sinh thông qua tham số: -i <duong_dan_file>")
        sys.exit(1)

    print(f"[*] Đang nạp và kiểm tra dữ liệu từ: {input_file}")
    engine = ValidationEngine(catalog_path=args.catalog)
    report = engine.validate_file(
        input_file=input_file,
        output_report_path=args.output,
        output_cleaned_path=args.clean_out,
        sheet_name=args.sheet
    )

    report.print_summary()


if __name__ == "__main__":
    main()
