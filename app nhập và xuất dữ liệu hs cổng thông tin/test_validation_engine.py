# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động toàn diện cho module validation_engine.py
Kiểm tra tất cả các yêu cầu kỹ thuật:
1. Đọc dữ liệu Excel & nạp danh mục
2. Tự động chuẩn hóa dữ liệu (Auto-Fix)
3. Bộ quy tắc kiểm tra lỗi R1 -> R5
4. Xuất báo cáo Excel Bao_Cao_Loi_Du_Lieu.xlsx
"""

import os
import unittest
import pandas as pd
from validation_engine import (
    ValidationEngine,
    DataNormalizer,
    CatalogManager,
    ValidationError,
    get_cleaned_data_for_web
)


class TestDataNormalizer(unittest.TestCase):
    """Kiểm tra chức năng Auto-Fix dữ liệu."""

    def test_normalize_name(self):
        # Yêu cầu: Họ và tên tự động .upper() và xóa khoảng trắng thừa đầu/cuối/giữa
        raw = " nguyễn  văn a "
        expected = "NGUYỄN VĂN A"
        self.assertEqual(DataNormalizer.normalize_name(raw), expected)

        # Nhiều khoảng trắng và tab
        self.assertEqual(DataNormalizer.normalize_name("  trần   thị   mai   lan  "), "TRẦN THỊ MAI LAN")

    def test_normalize_date(self):
        # Yêu cầu: Ngày tháng năm sinh ép kiểu về dd/MM/yyyy (VD: 2020-05-15 -> 15/05/2020)
        norm, ok = DataNormalizer.normalize_date("2020-05-15")
        self.assertTrue(ok)
        self.assertEqual(norm, "15/05/2020")

        # Định dạng yyyy/MM/dd
        norm, ok = DataNormalizer.normalize_date("2021/10/08")
        self.assertTrue(ok)
        self.assertEqual(norm, "08/10/2021")

        # Định dạng d/m/yyyy
        norm, ok = DataNormalizer.normalize_date("5/8/2021")
        self.assertTrue(ok)
        self.assertEqual(norm, "05/08/2021")

        # Định dạng dd-mm-yyyy
        norm, ok = DataNormalizer.normalize_date("14-04-2021")
        self.assertTrue(ok)
        self.assertEqual(norm, "14/04/2021")

        # Ngày sai định dạng / không hợp lệ
        norm, ok = DataNormalizer.normalize_date("32/13/2021")
        self.assertFalse(ok)

    def test_normalize_id_code(self):
        # Yêu cầu: Giữ lại ký tự số, thêm '0' ở đầu nếu bị mất số 0 ở đầu (VD: 79123456789 -> '079123456789)
        excel_str, digits, had_letters = DataNormalizer.normalize_id_code("79123456789")
        self.assertFalse(had_letters)
        self.assertEqual(digits, "079123456789")
        self.assertEqual(excel_str, "'079123456789")
        self.assertEqual(len(digits), 12)

        # Định dạng float từ Excel: 79221000194.0
        excel_str, digits, had_letters = DataNormalizer.normalize_id_code(79221000194.0)
        self.assertFalse(had_letters)
        self.assertEqual(digits, "079221000194")
        self.assertEqual(len(digits), 12)

        # Chứa chữ cái
        excel_str, digits, had_letters = DataNormalizer.normalize_id_code("079ABC123456")
        self.assertTrue(had_letters)

    def test_normalize_phone(self):
        # Yêu cầu: Giữ lại số, thêm 0 nếu thiếu số 0 ở đầu (VD: 933441983 -> '0933441983)
        excel_str, digits, had_letters = DataNormalizer.normalize_phone(933441983.0)
        self.assertFalse(had_letters)
        self.assertEqual(digits, "0933441983")
        self.assertEqual(excel_str, "'0933441983")
        self.assertEqual(len(digits), 10)

        # Chuyển +84
        excel_str, digits, had_letters = DataNormalizer.normalize_phone("+84937179810")
        self.assertFalse(had_letters)
        self.assertEqual(digits, "0937179810")
        self.assertEqual(len(digits), 10)

    def test_normalize_student_status(self):
        # Yêu cầu: Map chuẩn hóa
        # Học kỳ 1 -> "Chuyển đến kỳ 1"
        # Học kỳ 2 -> "Chuyển đến kỳ 2"
        # Trong hè   -> "Chuyển đến trong hè"
        self.assertEqual(DataNormalizer.normalize_student_status("Học kỳ 1"), "Chuyển đến kỳ 1")
        self.assertEqual(DataNormalizer.normalize_student_status("học kỳ 1"), "Chuyển đến kỳ 1")
        self.assertEqual(DataNormalizer.normalize_student_status("HK1"), "Chuyển đến kỳ 1")
        self.assertEqual(DataNormalizer.normalize_student_status("Học kỳ 2"), "Chuyển đến kỳ 2")
        self.assertEqual(DataNormalizer.normalize_student_status("HK2"), "Chuyển đến kỳ 2")
        self.assertEqual(DataNormalizer.normalize_student_status("Trong hè"), "Chuyển đến trong hè")
        self.assertEqual(DataNormalizer.normalize_student_status("Đang học"), "Đang học")


class TestValidationRules(unittest.TestCase):
    """Kiểm tra toàn diện 5 quy tắc R1 -> R5."""

    def setUp(self):
        # Khởi tạo engine với file mẫu nếu có, hoặc catalog mặc định
        ref_file = "C:/Users/Admin/Downloads/Filemau-MN-HocSinh-DiaPhuong-ver3-data-HCM.xls"
        catalog_path = ref_file if os.path.exists(ref_file) else None
        self.engine = ValidationEngine(catalog_path=catalog_path)

    def test_rule_r1_required_fields(self):
        # R1: Họ tên, Ngày sinh, Giới tính, Mã định danh 12 số không được để trống
        test_df = pd.DataFrame([{
            "Họ tên": "",  # Lỗi R1
            "Ngày sinh": "10/05/2021",
            "Giới tính": "Nam",
            "Số định danh cá nhân": "079221000123"
        }, {
            "Họ tên": "Trần Văn A",
            "Ngày sinh": "",  # Lỗi R1
            "Giới tính": "Nam",
            "Số định danh cá nhân": "079221000124"
        }, {
            "Họ tên": "Trần Văn B",
            "Ngày sinh": "10/05/2021",
            "Giới tính": "",  # Lỗi R1
            "Số định danh cá nhân": "079221000125"
        }, {
            "Họ tên": "Trần Văn C",
            "Ngày sinh": "10/05/2021",
            "Giới tính": "Nam",
            "Số định danh cá nhân": ""  # Lỗi R1
        }])

        report = self.engine.validate_dataframe(test_df)
        self.assertFalse(report.is_valid)
        err_codes = [e.error_code for e in report.errors]
        self.assertEqual(err_codes.count("ERR_REQUIRED"), 4)

    def test_rule_r2_id_12_digits(self):
        # R2: Phải chứa đúng 12 chữ số. Nếu sai độ dài hoặc chứa chữ cái -> Đánh dấu lỗi ERR_01
        test_df = pd.DataFrame([{
            "Họ tên": "Nguyễn Văn A",
            "Ngày sinh": "01/01/2021",
            "Giới tính": "Nam",
            "Số định danh cá nhân": "12345"  # Sai độ dài (5 số)
        }, {
            "Họ tên": "Nguyễn Văn B",
            "Ngày sinh": "01/01/2021",
            "Giới tính": "Nam",
            "Số định danh cá nhân": "079221A00123"  # Chứa chữ cái
        }, {
            "Họ tên": "Nguyễn Văn C",
            "Ngày sinh": "01/01/2021",
            "Giới tính": "Nam",
            "Số định danh cá nhân": "79221000194"  # 11 số -> Auto-fix thành 079221000194 (Hợp lệ!)
        }])

        report = self.engine.validate_dataframe(test_df)
        err_01_list = [e for e in report.errors if e.error_code == "ERR_01"]
        self.assertEqual(len(err_01_list), 2)
        # Học sinh C phải hợp lệ sau auto-fix
        self.assertEqual(report.cleaned_data[2]["Số định danh cá nhân"], "'079221000194")

    def test_rule_r3_phone_number(self):
        # R3: Số điện thoại bắt đầu bằng số 0 và đúng 10 chữ số
        test_df = pd.DataFrame([{
            "Họ tên": "Nguyễn Văn A",
            "Ngày sinh": "01/01/2021",
            "Giới tính": "Nam",
            "Số định danh cá nhân": "079221000123",
            "Số điện thoại liên hệ": "0912345678"  # Hợp lệ (10 số, bắt đầu bằng 0)
        }, {
            "Họ tên": "Nguyễn Văn B",
            "Ngày sinh": "01/01/2021",
            "Giới tính": "Nam",
            "Số định danh cá nhân": "079221000124",
            "Số điện thoại liên hệ": "1912345678"  # Lỗi: không bắt đầu bằng số 0
        }, {
            "Họ tên": "Nguyễn Văn C",
            "Ngày sinh": "01/01/2021",
            "Giới tính": "Nam",
            "Số định danh cá nhân": "079221000125",
            "Số điện thoại liên hệ": "091234567"  # Lỗi: chỉ có 9 số
        }])

        report = self.engine.validate_dataframe(test_df)
        phone_errors = [e for e in report.errors if e.error_code == "ERR_04"]
        self.assertEqual(len(phone_errors), 2)

    def test_rule_r4_catalog_matching(self):
        # R4: Dân tộc thuộc DAN_TOC, Tỉnh/Xã Phường khớp Sheet TINH/XA_PHUONG (ERR_03)
        test_df = pd.DataFrame([{
            "Họ tên": "Học Sinh A",
            "Ngày sinh": "01/01/2021",
            "Giới tính": "Nam",
            "Số định danh cá nhân": "079221000123",
            "Dân tộc": "Dân tộc không tồn tại 123",  # Lỗi danh mục Dân tộc
            "Tỉnh/Thành phố": "Thành phố Hồ Chí Minh",
            "Xã/Phường": "Phường An Khánh"
        }, {
            "Họ tên": "Học Sinh B",
            "Ngày sinh": "01/01/2021",
            "Giới tính": "Nữ",
            "Số định danh cá nhân": "079221000124",
            "Dân tộc": "Kinh",
            "Tỉnh/Thành phố": "Tỉnh Không Hợp Lệ XYZ",  # Lỗi ERR_03 Tỉnh
            "Xã/Phường": "Xã Không Tồn Tại ABC"         # Lỗi ERR_03 Xã
        }])

        report = self.engine.validate_dataframe(test_df)
        err_codes = [e.error_code for e in report.errors]
        self.assertIn("ERR_DAN_TOC", err_codes)
        self.assertIn("ERR_03", err_codes)

    def test_rule_r5_duplicate_id(self):
        # R5: Cảnh báo nếu phát hiện trùng Số định danh cá nhân 12 số giữa các dòng
        test_df = pd.DataFrame([{
            "Họ tên": "Nguyễn Văn A",
            "Ngày sinh": "01/01/2021",
            "Giới tính": "Nam",
            "Số định danh cá nhân": "079221000194"
        }, {
            "Họ tên": "Trần Thị B",
            "Ngày sinh": "02/02/2021",
            "Giới tính": "Nữ",
            "Số định danh cá nhân": "079221000194"  # Trùng lặp với học sinh A!
        }])

        report = self.engine.validate_dataframe(test_df)
        dup_errors = [e for e in report.errors if e.error_code == "ERR_05"]
        self.assertEqual(len(dup_errors), 2)

    def test_output_report_generation(self):
        # Xuất file Excel báo cáo lỗi
        test_df = pd.DataFrame([{
            "Họ tên": " nguyễn văn a ",
            "Ngày sinh": "2020-05-15",
            "Giới tính": "Nam",
            "Số định danh cá nhân": "12345"  # Vi phạm ERR_01
        }])

        report = self.engine.validate_dataframe(test_df)
        report_file = "test_bao_cao_loi.xlsx"
        saved_path = report.to_excel_report(report_file)
        self.assertTrue(os.path.exists(saved_path))
        if os.path.exists(report_file):
            os.remove(report_file)


if __name__ == "__main__":
    unittest.main()
