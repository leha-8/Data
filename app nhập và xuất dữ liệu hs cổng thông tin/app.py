# -*- coding: utf-8 -*-
"""
================================================================================
GIAO DIỆN DESKTOP APP - KIỂM TRA & CHUẨN HÓA DỮ LIỆU HỌC SINH SỞ GD&ĐT
================================================================================
Framework: CustomTkinter
Kết nối trực tiếp: validation_engine.py
Tính năng:
1. Nút "Chọn file Excel học sinh" (Hỗ trợ .xlsx, .xls, .xlsm, tự động quét sheet).
2. Tự động nhận diện hoặc chọn "File danh mục mẫu Sở GD&ĐT".
3. Nút "Kiểm tra & Chuẩn hóa" (Chạy background thread, không đơ lag UI).
4. Thống kê KPI trực quan: Tổng số, Hợp lệ, Có lỗi, Tổng số lỗi.
5. Ô hiển thị kết quả báo lỗi chi tiết với bộ lọc theo mã lỗi, tìm kiếm thời gian thực.
6. Nút "Xuất file Excel chuẩn" (Lưu dữ liệu đã qua Auto-Fix).
7. Nút "Xuất Báo cáo lỗi (Excel)" và "Mở thư mục chứa file".
================================================================================
"""

import os
import re
import sys
import glob
import threading
import subprocess
import time
from typing import Optional, List, Dict, Any

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import pandas as pd

# Import bộ xử lý nghiệp vụ từ module validation_engine
try:
    from validation_engine import ValidationEngine, ValidationReport, ValidationError, DataNormalizer
except ImportError:
    # Nếu chạy từ thư mục khác
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from validation_engine import ValidationEngine, ValidationReport, ValidationError, DataNormalizer


# Cấu hình giao diện CustomTkinter
ctk.set_appearance_mode("System")  # "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"


class StudentDataValidatorApp(ctk.CTk):
    """Lớp chính quản lý giao diện Desktop Application."""

    def __init__(self):
        super().__init__()

        # 1. Thiết lập cửa sổ chính
        self.title("Hệ thống Kiểm tra & Chuẩn hóa Dữ liệu Học sinh - Sở GD&ĐT")
        self.geometry("1180x760")
        self.minsize(980, 680)

        # Biến lưu trữ trạng thái dữ liệu
        self.input_file_path: Optional[str] = None
        self.catalog_file_path: Optional[str] = None
        self.validation_engine: Optional[ValidationEngine] = None
        self.current_report: Optional[ValidationReport] = None
        self.is_processing: bool = False

        # Tự động dò tìm file học sinh và file danh mục mẫu khi khởi động
        self._auto_detect_initial_files()

        # 2. Xây dựng các thành phần giao diện
        self._setup_ui()

        # 3. Đồng bộ giao diện ban đầu
        self._update_ui_state()

    def _auto_detect_initial_files(self):
        """Tự động tìm kiếm file mẫu Sở GD&ĐT và file dữ liệu học sinh trong thư mục chạy, thư mục exe và Downloads."""
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        downloads_dir = os.path.expanduser("~/Downloads")
        current_dir = os.getcwd()

        search_dirs = []
        for d in [exe_dir, current_dir, downloads_dir]:
            if d and os.path.exists(d) and d not in search_dirs:
                search_dirs.append(d)

        # Tìm file mẫu
        search_patterns = ["*Filemau*HocSinh*.xls*", "*Filemau*.xls*", "*DanhMuc*.xls*"]
        for d in search_dirs:
            for pat in search_patterns:
                matches = glob.glob(os.path.join(d, pat))
                for m in matches:
                    fname = os.path.basename(m).lower()
                    if not any(x in fname for x in ["bao_cao", "loi", "report", "error"]):
                        self.catalog_file_path = os.path.abspath(m)
                        break
                if self.catalog_file_path:
                    break
            if self.catalog_file_path:
                break

        # Tìm file dữ liệu học sinh nếu có sẵn
        for d in search_dirs:
            cand = os.path.join(d, "Danh_sach_hoc_sinh.xlsx")
            if os.path.exists(cand):
                self.input_file_path = os.path.abspath(cand)
                break

    def _setup_ui(self):
        """Khởi tạo toàn bộ bố cục (Layout) của ứng dụng."""
        # Chia bố cục lưới chính: 0: Header, 1: Controls, 2: Action Bar, 3: Stats, 4: Content Tabs, 5: Status Bar
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ----------------------------------------------------------------------
        # HEADER BAR
        # ----------------------------------------------------------------------
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray90", "#181824"))
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.header_frame.grid_columnconfigure(1, weight=1)

        # Icon & Title
        title_icon = ctk.CTkLabel(self.header_frame, text="🎓", font=ctk.CTkFont(size=28))
        title_icon.grid(row=0, column=0, rowspan=2, padx=(20, 10), pady=10)

        title_label = ctk.CTkLabel(
            self.header_frame,
            text="HỆ THỐNG KIỂM TRA & CHUẨN HÓA DỮ LIỆU HỌC SINH",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.grid(row=0, column=1, sticky="w", padx=0, pady=(10, 0))

        subtitle_label = ctk.CTkLabel(
            self.header_frame,
            text="Theo chuẩn CSDL Sở Giáo dục & Đào tạo | Tự động Auto-Fix định dạng | Kiểm tra quy tắc R1 - R5",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70")
        )
        subtitle_label.grid(row=1, column=1, sticky="w", padx=0, pady=(0, 10))

        # Nút đổi giao diện Tối / Sáng
        self.theme_switch = ctk.CTkSwitch(
            self.header_frame,
            text="Giao diện Tối",
            command=self._toggle_theme,
            font=ctk.CTkFont(size=12)
        )
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()
        else:
            self.theme_switch.deselect()
        self.theme_switch.grid(row=0, column=2, rowspan=2, padx=20, pady=10, sticky="e")

        # ----------------------------------------------------------------------
        # FILE CONTROLS SECTION (Khu vực chọn tệp)
        # ----------------------------------------------------------------------
        self.file_card = ctk.CTkFrame(self, corner_radius=10)
        self.file_card.grid(row=1, column=0, sticky="ew", padx=20, pady=(12, 6))
        self.file_card.grid_columnconfigure(1, weight=1)

        # Hàng 1: Chọn file học sinh
        lbl_student = ctk.CTkLabel(self.file_card, text="File Excel học sinh:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_student.grid(row=0, column=0, sticky="w", padx=(16, 10), pady=(12, 6))

        self.entry_student_file = ctk.CTkEntry(
            self.file_card,
            placeholder_text="Nhấp 'Chọn file Excel học sinh' để tải tệp (.xlsx, .xls)...",
            font=ctk.CTkFont(size=12)
        )
        self.entry_student_file.grid(row=0, column=1, sticky="ew", padx=5, pady=(12, 6))
        if self.input_file_path:
            self.entry_student_file.insert(0, self.input_file_path)

        self.btn_browse_student = ctk.CTkButton(
            self.file_card,
            text="📂 Chọn file Excel học sinh",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._browse_student_file,
            width=190,
            height=34
        )
        self.btn_browse_student.grid(row=0, column=2, padx=(6, 16), pady=(12, 6))

        # Dropdown Sheet
        lbl_sheet = ctk.CTkLabel(self.file_card, text="Sheet dữ liệu:", font=ctk.CTkFont(size=12))
        lbl_sheet.grid(row=0, column=3, sticky="w", padx=(6, 6), pady=(12, 6))

        self.combo_sheets = ctk.CTkOptionMenu(
            self.file_card,
            values=["(Tự động nhận diện)"],
            width=160,
            height=34,
            font=ctk.CTkFont(size=12)
        )
        self.combo_sheets.grid(row=0, column=4, padx=(0, 16), pady=(12, 6))

        # Hàng 2: Chọn file mẫu danh mục Sở GD&ĐT
        lbl_catalog = ctk.CTkLabel(self.file_card, text="Danh mục mẫu Sở GD&ĐT:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_catalog.grid(row=1, column=0, sticky="w", padx=(16, 10), pady=(0, 12))

        self.entry_catalog_file = ctk.CTkEntry(
            self.file_card,
            placeholder_text="Mặc định: Sử dụng danh mục chuẩn quốc gia & tự động tìm kiếm...",
            font=ctk.CTkFont(size=12)
        )
        self.entry_catalog_file.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 12))
        if self.catalog_file_path:
            self.entry_catalog_file.insert(0, self.catalog_file_path)

        self.btn_browse_catalog = ctk.CTkButton(
            self.file_card,
            text="📚 Chọn file danh mục mẫu...",
            font=ctk.CTkFont(size=12),
            command=self._browse_catalog_file,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            width=190,
            height=34
        )
        self.btn_browse_catalog.grid(row=1, column=2, padx=(6, 16), pady=(0, 12))

        # Nút xóa/reset catalog
        self.btn_reset_catalog = ctk.CTkButton(
            self.file_card,
            text="🔄 Mặc định",
            font=ctk.CTkFont(size=11),
            width=80,
            height=34,
            command=self._reset_catalog_to_default
        )
        self.btn_reset_catalog.grid(row=1, column=3, columnspan=2, sticky="w", padx=(0, 16), pady=(0, 12))

        # Nếu đã có file học sinh ban đầu, cập nhật danh sách sheet
        if self.input_file_path and os.path.exists(self.input_file_path):
            self._populate_sheet_names(self.input_file_path)

        # ----------------------------------------------------------------------
        # ACTION BUTTONS & PROGRESS BAR
        # ----------------------------------------------------------------------
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 6))
        self.action_frame.grid_columnconfigure(5, weight=1)

        # Nút Kiểm tra & Chuẩn hóa (Nổi bật nhất)
        self.btn_validate = ctk.CTkButton(
            self.action_frame,
            text="🔍 Kiểm tra & Chuẩn hóa",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            width=210,
            fg_color="#1F6AA5",
            hover_color="#144A75",
            command=self._on_start_validation
        )
        self.btn_validate.grid(row=0, column=0, padx=(0, 10), pady=4)

        # Nút Xuất file Excel chuẩn
        self.btn_export_clean = ctk.CTkButton(
            self.action_frame,
            text="📥 Xuất file Excel chuẩn",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            width=190,
            fg_color="#27AE60",
            hover_color="#1E8449",
            state="disabled",
            command=self._on_export_cleaned_excel
        )
        self.btn_export_clean.grid(row=0, column=1, padx=(0, 10), pady=4)

        # Nút Xuất Báo cáo lỗi (Excel)
        self.btn_export_report = ctk.CTkButton(
            self.action_frame,
            text="📊 Xuất Báo cáo lỗi (Excel)",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            width=200,
            fg_color="#C0392B",
            hover_color="#922B21",
            state="disabled",
            command=self._on_export_error_report
        )
        self.btn_export_report.grid(row=0, column=2, padx=(0, 10), pady=4)

        # Nút Mở thư mục kết quả
        self.btn_open_folder = ctk.CTkButton(
            self.action_frame,
            text="📁 Mở thư mục chứa file",
            font=ctk.CTkFont(size=12),
            height=40,
            width=170,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self._on_open_output_folder
        )
        self.btn_open_folder.grid(row=0, column=3, padx=(0, 10), pady=4)

        # Thanh tiến độ Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self.action_frame, height=8)
        self.progress_bar.grid(row=1, column=0, columnspan=6, sticky="ew", padx=0, pady=(6, 0))
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()  # Ẩn khi chưa chạy

        # ----------------------------------------------------------------------
        # STATS DASHBOARD (4 THẺ KPI TRỰC QUAN)
        # ----------------------------------------------------------------------
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 6))
        for col_i in range(4):
            self.stats_frame.grid_columnconfigure(col_i, weight=1)

        # Thẻ 1: Tổng học sinh
        self.card_total = self._create_kpi_card(
            parent=self.stats_frame,
            title="TỔNG HỌC SINH",
            value="0",
            icon="👥",
            col=0,
            accent_color=("#3498DB", "#2980B9")
        )

        # Thẻ 2: Bản ghi Hợp lệ
        self.card_valid = self._create_kpi_card(
            parent=self.stats_frame,
            title="HỢP LỆ (SẴN SÀNG)",
            value="0",
            icon="✅",
            col=1,
            accent_color=("#2ECC71", "#27AE60")
        )

        # Thẻ 3: Bản ghi Có lỗi
        self.card_invalid = self._create_kpi_card(
            parent=self.stats_frame,
            title="BẢN GHI CÓ LỖI",
            value="0",
            icon="⚠️",
            col=2,
            accent_color=("#F39C12", "#D68910")
        )

        # Thẻ 4: Tổng số lỗi
        self.card_errors = self._create_kpi_card(
            parent=self.stats_frame,
            title="TỔNG SỐ LỖI",
            value="0",
            icon="❌",
            col=3,
            accent_color=("#E74C3C", "#C0392B")
        )

        # ----------------------------------------------------------------------
        # TABVIEW HIỂN THỊ KẾT QUẢ VÀ DỮ LIỆU
        # ----------------------------------------------------------------------
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.grid(row=4, column=0, sticky="nsew", padx=20, pady=(4, 6))

        self.tab_errors = self.tabview.add("🚨 Báo cáo lỗi chi tiết")
        self.tab_preview = self.tabview.add("📋 Dữ liệu đã chuẩn hóa (Preview)")
        self.tab_rules = self.tabview.add("ℹ️ Hướng dẫn & Quy tắc (R1-R5)")

        self._setup_errors_tab()
        self._setup_preview_tab()
        self._setup_rules_tab()

        # ----------------------------------------------------------------------
        # STATUS BAR (CHÂN TRANG)
        # ----------------------------------------------------------------------
        self.status_frame = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=("gray85", "#14141E"))
        self.status_frame.grid(row=5, column=0, sticky="ew", padx=0, pady=0)
        self.status_frame.grid_columnconfigure(0, weight=1)

        self.lbl_status = ctk.CTkLabel(
            self.status_frame,
            text="Sẵn sàng kiểm tra. Hãy chọn file Excel học sinh để bắt đầu.",
            font=ctk.CTkFont(size=11),
            text_color=("gray20", "gray80")
        )
        self.lbl_status.grid(row=0, column=0, sticky="w", padx=16, pady=4)

        self.lbl_timer = ctk.CTkLabel(
            self.status_frame,
            text="Validation Engine v1.0",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60")
        )
        self.lbl_timer.grid(row=0, column=1, sticky="e", padx=16, pady=4)

    def _create_kpi_card(self, parent, title: str, value: str, icon: str, col: int, accent_color) -> Dict[str, Any]:
        """Tạo thẻ hiển thị chỉ số KPI."""
        card = ctk.CTkFrame(parent, corner_radius=10, height=76)
        card.grid(row=0, column=col, sticky="ew", padx=5, pady=0)
        card.grid_propagate(False)
        card.grid_columnconfigure(1, weight=1)

        lbl_icon = ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=26))
        lbl_icon.grid(row=0, column=0, rowspan=2, padx=(14, 8), pady=10)

        lbl_title = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray40", "gray70")
        )
        lbl_title.grid(row=0, column=1, sticky="w", padx=0, pady=(10, 0))

        lbl_val = ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=accent_color
        )
        lbl_val.grid(row=1, column=1, sticky="w", padx=0, pady=(0, 10))

        return {"card": card, "val_label": lbl_val}

    # ==========================================================================
    # CẤU HÌNH TAB 1: BÁO CÁO LỖI CHI TIẾT
    # ==========================================================================
    def _setup_errors_tab(self):
        """Thiết lập Tab 1: Danh sách lỗi với bộ lọc, tìm kiếm và bảng dữ liệu."""
        self.tab_errors.grid_rowconfigure(1, weight=1)
        self.tab_errors.grid_columnconfigure(0, weight=1)

        # Thanh công cụ: Tìm kiếm & Lọc lỗi
        filter_bar = ctk.CTkFrame(self.tab_errors, fg_color="transparent")
        filter_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=(4, 8))
        filter_bar.grid_columnconfigure(1, weight=1)

        lbl_search = ctk.CTkLabel(filter_bar, text="🔎 Tìm kiếm:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_search.grid(row=0, column=0, padx=(0, 6), pady=0)

        self.entry_search_err = ctk.CTkEntry(
            filter_bar,
            placeholder_text="Tìm theo tên học sinh, số dòng, cột lỗi...",
            font=ctk.CTkFont(size=12),
            height=32
        )
        self.entry_search_err.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=0)
        self.entry_search_err.bind("<KeyRelease>", lambda e: self._apply_error_filter())

        lbl_filter_code = ctk.CTkLabel(filter_bar, text="Mã lỗi:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_filter_code.grid(row=0, column=2, padx=(0, 6), pady=0)

        self.combo_error_code = ctk.CTkOptionMenu(
            filter_bar,
            values=["Tất cả mã lỗi"],
            width=160,
            height=32,
            command=lambda v: self._apply_error_filter()
        )
        self.combo_error_code.grid(row=0, column=3, padx=(0, 10), pady=0)

        self.lbl_error_count_badge = ctk.CTkLabel(
            filter_bar,
            text="Hiển thị: 0 lỗi",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray40", "gray70")
        )
        self.lbl_error_count_badge.grid(row=0, column=4, padx=(0, 5), pady=0)

        # Bảng hiển thị lỗi dùng ttk.Treeview
        tree_container = ctk.CTkFrame(self.tab_errors)
        tree_container.grid(row=1, column=0, sticky="nsew", padx=5, pady=0)
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        columns = ("stt", "row", "name", "col", "code", "msg", "val")
        self.tree_errors = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            selectmode="browse"
        )

        # Tiêu đề cột
        self.tree_errors.heading("stt", text="STT")
        self.tree_errors.heading("row", text="Dòng (Excel)")
        self.tree_errors.heading("name", text="Họ tên học sinh")
        self.tree_errors.heading("col", text="Cột bị lỗi")
        self.tree_errors.heading("code", text="Mã lỗi")
        self.tree_errors.heading("msg", text="Chi tiết lỗi & Hướng dẫn khắc phục")
        self.tree_errors.heading("val", text="Giá trị gốc")

        # Độ rộng cột
        self.tree_errors.column("stt", width=50, minwidth=40, anchor="center")
        self.tree_errors.column("row", width=95, minwidth=80, anchor="center")
        self.tree_errors.column("name", width=190, minwidth=150, anchor="w")
        self.tree_errors.column("col", width=170, minwidth=130, anchor="w")
        self.tree_errors.column("code", width=100, minwidth=90, anchor="center")
        self.tree_errors.column("msg", width=420, minwidth=250, anchor="w")
        self.tree_errors.column("val", width=140, minwidth=100, anchor="w")

        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_errors.yview)
        h_scroll = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree_errors.xview)
        self.tree_errors.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree_errors.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        # Khung xem chi tiết lỗi khi chọn dòng
        self.detail_card = ctk.CTkFrame(self.tab_errors, height=65, corner_radius=8, fg_color=("gray95", "#1F1F2E"))
        self.detail_card.grid(row=2, column=0, sticky="ew", padx=5, pady=(8, 4))
        self.detail_card.grid_propagate(False)
        self.detail_card.grid_columnconfigure(0, weight=1)

        self.lbl_selected_detail = ctk.CTkLabel(
            self.detail_card,
            text="💡 Chọn một dòng lỗi trong bảng trên để xem chi tiết đầy đủ và hướng dẫn xử lý.",
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray70"),
            anchor="w",
            justify="left"
        )
        self.lbl_selected_detail.grid(row=0, column=0, sticky="nsew", padx=14, pady=8)

        self.tree_errors.bind("<<TreeviewSelect>>", self._on_select_error_row)

        # Style Treeview
        self._apply_treeview_styles()

    # ==========================================================================
    # CẤU HÌNH TAB 2: DỮ LIỆU ĐÃ CHUẨN HÓA (PREVIEW)
    # ==========================================================================
    def _setup_preview_tab(self):
        """Thiết lập Tab 2: Xem trước dữ liệu học sinh sau khi chuẩn hóa."""
        self.tab_preview.grid_rowconfigure(1, weight=1)
        self.tab_preview.grid_columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(self.tab_preview, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=(4, 8))
        top_bar.grid_columnconfigure(0, weight=1)

        lbl_info = ctk.CTkLabel(
            top_bar,
            text="Dữ liệu đã được Auto-Fix: Họ tên VIẾT HOA, ngày sinh dd/MM/yyyy, SĐT/CCCD đủ số.",
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color=("gray40", "gray70")
        )
        lbl_info.grid(row=0, column=0, sticky="w")

        btn_save_from_tab = ctk.CTkButton(
            top_bar,
            text="💾 Lưu dữ liệu này thành Excel",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            fg_color="#27AE60",
            hover_color="#1E8449",
            command=self._on_export_cleaned_excel
        )
        btn_save_from_tab.grid(row=0, column=1, sticky="e")

        # Treeview cho Cleaned Data
        preview_container = ctk.CTkFrame(self.tab_preview)
        preview_container.grid(row=1, column=0, sticky="nsew", padx=5, pady=0)
        preview_container.grid_rowconfigure(0, weight=1)
        preview_container.grid_columnconfigure(0, weight=1)

        self.tree_preview = ttk.Treeview(preview_container, show="headings", selectmode="browse")
        v_scroll_p = ttk.Scrollbar(preview_container, orient="vertical", command=self.tree_preview.yview)
        h_scroll_p = ttk.Scrollbar(preview_container, orient="horizontal", command=self.tree_preview.xview)
        self.tree_preview.configure(yscrollcommand=v_scroll_p.set, xscrollcommand=h_scroll_p.set)

        self.tree_preview.grid(row=0, column=0, sticky="nsew")
        v_scroll_p.grid(row=0, column=1, sticky="ns")
        h_scroll_p.grid(row=1, column=0, sticky="ew")

    # ==========================================================================
    # CẤU HÌNH TAB 3: HƯỚNG DẪN & QUY TẮC
    # ==========================================================================
    def _setup_rules_tab(self):
        """Thiết lập Tab 3: Tra cứu quy tắc kiểm tra R1-R5 và mã lỗi."""
        self.tab_rules.grid_rowconfigure(0, weight=1)
        self.tab_rules.grid_columnconfigure(0, weight=1)

        scroll_rules = ctk.CTkScrollableFrame(self.tab_rules)
        scroll_rules.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        rules_text = """
📌 BỘ QUY TẮC KIỂM TRA LỖI DỮ LIỆU HỌC SINH (SỞ GD&ĐT)

1. Quy tắc R1 (Trường bắt buộc):
   - Họ và tên, Ngày tháng năm sinh, Giới tính, Mã định danh 12 số không được để trống.
   - Mã lỗi phát sinh: ERR_REQUIRED nếu để trống bất kỳ trường bắt buộc nào.

2. Quy tắc R2 (Số định danh cá nhân / CCCD 12 số):
   - Phải chứa đúng 12 chữ số. Hệ thống tự động bù số 0 ở đầu nếu bị Excel cắt (11 số -> 12 số).
   - Nếu sai độ dài hoặc chứa chữ cái/ký tự đặc biệt -> Đánh dấu lỗi ERR_01.

3. Quy tắc R3 (Số điện thoại liên hệ):
   - Phải bắt đầu bằng số 0 và chứa đúng 10 chữ số. Hệ thống tự động bù số 0 ở đầu nếu có 9 số.
   - Nếu không khớp chuẩn số di động Việt Nam -> Đánh dấu lỗi ERR_04.

4. Quy tắc R4 (Đối chiếu Danh mục chuẩn Sở GD&ĐT):
   - Dân tộc: Phải thuộc danh mục Sheet DAN_TOC (hoặc 54 dân tộc Việt Nam) -> ERR_DAN_TOC.
   - Giới tính: Chỉ chấp nhận 'Nam' hoặc 'Nữ' theo Sheet GIOI_TINH -> ERR_GIOI_TINH.
   - Tỉnh/Thành phố & Phường/Xã: Phải khớp chính xác danh mục Sheet TINH và XA_PHUONG -> ERR_03.

5. Quy tắc R5 (Kiểm tra trùng lặp mã định danh):
   - Cảnh báo nếu phát hiện trùng Số định danh cá nhân 12 số giữa các dòng trong cùng file -> ERR_05.

🛠️ CƠ CHẾ TỰ ĐỘNG CHUẨN HÓA (AUTO-FIX):
   - Họ và tên: Tự động chuyển thành chữ hoa (.upper()) và xóa toàn bộ khoảng trắng thừa.
   - Ngày sinh / Ngày cấp: Ép kiểu về dạng dd/MM/yyyy.
   - CCCD / SĐT: Tự động thêm dấu nháy đơn ' ở đầu để Excel không tự động cắt mất số 0 đầu.
   - Trạng thái học sinh: Map 'Học kỳ 1' -> 'Chuyển đến kỳ 1', 'Học kỳ 2' -> 'Chuyển đến kỳ 2', 'Trong hè' -> 'Chuyển đến trong hè'.
"""
        lbl_rules = ctk.CTkLabel(
            scroll_rules,
            text=rules_text.strip(),
            font=ctk.CTkFont(family="Consolas", size=13),
            justify="left",
            anchor="w"
        )
        lbl_rules.pack(padx=16, pady=16, fill="both", expand=True)

    def _apply_treeview_styles(self):
        """Định dạng màu sắc và font chữ cho Treeview phù hợp Dark / Light theme."""
        style = ttk.Style()
        style.theme_use("clam")

        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#1E1E2E" if is_dark else "#FFFFFF"
        fg_color = "#E0E0E0" if is_dark else "#222222"
        heading_bg = "#1F4E78" if is_dark else "#1F4E78"
        heading_fg = "#FFFFFF"
        selected_bg = "#2980B9" if is_dark else "#3498DB"

        style.configure(
            "Treeview",
            background=bg_color,
            foreground=fg_color,
            fieldbackground=bg_color,
            rowheight=26,
            font=("Segoe UI", 10)
        )
        style.map("Treeview", background=[("selected", selected_bg)], foreground=[("selected", "#FFFFFF")])

        style.configure(
            "Treeview.Heading",
            background=heading_bg,
            foreground=heading_fg,
            relief="flat",
            font=("Segoe UI", 10, "bold")
        )
        style.map("Treeview.Heading", background=[("active", "#144A75")])

        # Tag màu xen kẽ zebra
        even_color = "#252538" if is_dark else "#F8F9FA"
        self.tree_errors.tag_configure("even", background=even_color)
        self.tree_errors.tag_configure("odd", background=bg_color)
        self.tree_errors.tag_configure("err_high", foreground="#E74C3C")

    def _toggle_theme(self):
        """Chuyển đổi giao diện Tối / Sáng."""
        if self.theme_switch.get():
            ctk.set_appearance_mode("Dark")
            self.theme_switch.configure(text="Giao diện Tối")
        else:
            ctk.set_appearance_mode("Light")
            self.theme_switch.configure(text="Giao diện Sáng")
        self._apply_treeview_styles()

    # ==========================================================================
    # LOGIC CHỌN FILE VÀ QUẢN LÝ DỮ LIỆU
    # ==========================================================================
    def _browse_student_file(self):
        """Mở hộp thoại chọn file Excel học sinh."""
        filetypes = [
            ("File Excel (*.xlsx; *.xls; *.xlsm)", "*.xlsx *.xls *.xlsm"),
            ("Tất cả tệp (*.*)", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Chọn file Excel dữ liệu học sinh", filetypes=filetypes)
        if chosen:
            self.input_file_path = chosen
            self.entry_student_file.delete(0, "end")
            self.entry_student_file.insert(0, chosen)
            self._populate_sheet_names(chosen)
            self._update_status(f"Đã chọn file: {os.path.basename(chosen)}")

    def _populate_sheet_names(self, file_path: str):
        """Đọc danh sách các sheet trong file Excel để nạp vào combobox."""
        try:
            with pd.ExcelFile(file_path) as xl:
                sheet_names = xl.sheet_names
                options = ["(Tự động nhận diện)"] + sheet_names
                self.combo_sheets.configure(values=options)

                # Ưu tiên chọn XUAT_FILE_SO hoặc Sheet1 nếu có
                if "XUAT_FILE_SO" in sheet_names:
                    self.combo_sheets.set("XUAT_FILE_SO")
                elif "Sheet1" in sheet_names:
                    self.combo_sheets.set("Sheet1")
                else:
                    self.combo_sheets.set("(Tự động nhận diện)")
        except Exception as e:
            print(f"Lỗi đọc sheet: {e}")

    def _browse_catalog_file(self):
        """Mở hộp thoại chọn file mẫu danh mục Sở GD&ĐT."""
        filetypes = [
            ("File Excel (*.xlsx; *.xls; *.xlsm)", "*.xlsx *.xls *.xlsm"),
            ("Tất cả tệp (*.*)", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Chọn file Excel mẫu danh mục Sở GD&ĐT", filetypes=filetypes)
        if chosen:
            self.catalog_file_path = chosen
            self.entry_catalog_file.delete(0, "end")
            self.entry_catalog_file.insert(0, chosen)
            self._update_status(f"Đã nạp file danh mục: {os.path.basename(chosen)}")

    def _reset_catalog_to_default(self):
        """Đặt lại danh mục về chế độ tự động/mặc định."""
        self.catalog_file_path = None
        self.entry_catalog_file.delete(0, "end")
        self._auto_detect_initial_files()
        if self.catalog_file_path:
            self.entry_catalog_file.insert(0, self.catalog_file_path)
            self._update_status("Đã khôi phục file danh mục mẫu tìm thấy trong Downloads.")
        else:
            self._update_status("Sử dụng bộ danh mục chuẩn quốc gia tích hợp.")

    # ==========================================================================
    # LOGIC CHẠY KIỂM TRA & CHUẨN HÓA (VALIDATION THREAD)
    # ==========================================================================
    def _on_start_validation(self):
        """Kích hoạt tiến trình kiểm tra và chuẩn hóa trong background thread."""
        file_path = self.entry_student_file.get().strip()
        if not file_path or not os.path.exists(file_path):
            messagebox.showwarning("Chưa chọn file", "Vui lòng chọn file Excel dữ liệu học sinh hợp lệ trước!")
            return

        if self.is_processing:
            return

        self.is_processing = True
        self.btn_validate.configure(state="disabled", text="⏳ Đang xử lý...")
        self.progress_bar.grid()
        self.progress_bar.start()
        self._update_status("Đang đọc file và đối chiếu danh mục...")

        # Chạy trong luồng phụ để không treo UI
        thread = threading.Thread(target=self._run_validation_process, args=(file_path,), daemon=True)
        thread.start()

    def _run_validation_process(self, file_path: str):
        """Tiến trình chạy ngầm."""
        start_time = time.time()
        try:
            catalog_p = self.entry_catalog_file.get().strip()
            if not catalog_p or not os.path.exists(catalog_p):
                catalog_p = None

            selected_sheet = self.combo_sheets.get()
            sheet_arg = None if selected_sheet == "(Tự động nhận diện)" else selected_sheet

            engine = ValidationEngine(catalog_path=catalog_p)
            report = engine.validate_file(
                input_file=file_path,
                output_report_path="Bao_Cao_Loi_Du_Lieu.xlsx",
                sheet_name=sheet_arg
            )
            elapsed = time.time() - start_time

            # Cập nhật kết quả lên UI từ main thread
            self.after(0, self._on_validation_complete, report, elapsed)

        except Exception as e:
            elapsed = time.time() - start_time
            self.after(0, self._on_validation_error, str(e))

    def _on_validation_complete(self, report: ValidationReport, elapsed: float):
        """Xử lý sau khi kiểm tra hoàn tất."""
        self.current_report = report
        self.is_processing = False
        self.progress_bar.stop()
        self.progress_bar.grid_remove()
        self.btn_validate.configure(state="normal", text="🔍 Kiểm tra & Chuẩn hóa")

        # Cập nhật thẻ KPI
        self.card_total["val_label"].configure(text=str(report.total_records))
        self.card_valid["val_label"].configure(text=str(report.valid_records))
        self.card_invalid["val_label"].configure(text=str(report.error_records))
        self.card_errors["val_label"].configure(text=str(len(report.errors)))

        # Bật/tắt các nút xuất
        self.btn_export_clean.configure(state="normal" if report.total_records > 0 else "disabled")
        self.btn_export_report.configure(state="normal" if len(report.errors) > 0 else "disabled")

        # Cập nhật combobox bộ lọc mã lỗi
        error_codes = sorted(list(set(e.error_code for e in report.errors)))
        filter_options = ["Tất cả mã lỗi"] + error_codes
        self.combo_error_code.configure(values=filter_options)
        self.combo_error_code.set("Tất cả mã lỗi")

        # Hiển thị dữ liệu lên bảng lỗi
        self._populate_error_tree(report.errors)

        # Hiển thị dữ liệu lên bảng Preview
        self._populate_preview_tree(report.cleaned_data)

        # Cập nhật trạng thái
        status_msg = f"Đã kiểm tra {report.total_records} học sinh. Hợp lệ: {report.valid_records}, Có lỗi: {report.error_records} ({len(report.errors)} lỗi vi phạm)."
        self._update_status(status_msg, timer_text=f"Hoàn thành trong {elapsed:.2f}s")

        if report.is_valid:
            messagebox.showinfo(
                "Kiểm tra thành công!",
                f"Tuyệt vời! Toàn bộ {report.total_records} bản ghi học sinh đều HỢP LỆ và đã được chuẩn hóa.\nBạn có thể xuất file Excel sạch để nạp lên CSDL ngành."
            )
        else:
            messagebox.showwarning(
                "Phát hiện lỗi dữ liệu",
                f"Đã phát hiện {len(report.errors)} lỗi vi phạm trên {report.error_records} học sinh.\nVui lòng xem chi tiết lỗi trong bảng bên dưới hoặc xuất Báo cáo lỗi."
            )

    def _on_validation_error(self, err_msg: str):
        """Xử lý ngoại lệ nếu xảy ra lỗi trong quá trình đọc/xử lý file."""
        self.is_processing = False
        self.progress_bar.stop()
        self.progress_bar.grid_remove()
        self.btn_validate.configure(state="normal", text="🔍 Kiểm tra & Chuẩn hóa")
        self._update_status(f"Lỗi: {err_msg}")
        messagebox.showerror("Lỗi xử lý file", f"Không thể xử lý file Excel:\n{err_msg}")

    # ==========================================================================
    # HIỂN THỊ VÀ LỌC DỮ LIỆU TRÊN CÁC BẢNG
    # ==========================================================================
    def _populate_error_tree(self, error_list: List[ValidationError]):
        """Nạp danh sách lỗi vào bảng Treeview."""
        # Xóa các dòng cũ
        for item in self.tree_errors.get_children():
            self.tree_errors.delete(item)

        for idx, err in enumerate(error_list, 1):
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree_errors.insert(
                "",
                "end",
                values=(
                    idx,
                    err.row_index,
                    err.student_name,
                    err.column_name,
                    err.error_code,
                    err.error_message,
                    str(err.raw_value) if err.raw_value is not None else ""
                ),
                tags=(tag,)
            )

        self.lbl_error_count_badge.configure(text=f"Hiển thị: {len(error_list)} lỗi")
        self.lbl_selected_detail.configure(text="💡 Nhấp chuột vào một dòng lỗi trong bảng để xem chi tiết đầy đủ.")

    def _apply_error_filter(self):
        """Lọc danh sách lỗi theo từ khóa tìm kiếm và mã lỗi."""
        if not self.current_report:
            return

        keyword = self.entry_search_err.get().strip().lower()
        selected_code = self.combo_error_code.get()

        filtered_list = []
        for err in self.current_report.errors:
            # Lọc theo mã lỗi
            if selected_code != "Tất cả mã lỗi" and err.error_code != selected_code:
                continue
            # Lọc theo từ khóa tìm kiếm
            if keyword:
                match_name = keyword in err.student_name.lower()
                match_col = keyword in err.column_name.lower()
                match_row = keyword in str(err.row_index)
                match_msg = keyword in err.error_message.lower()
                match_code = keyword in err.error_code.lower()
                if not (match_name or match_col or match_row or match_msg or match_code):
                    continue
            filtered_list.append(err)

        self._populate_error_tree(filtered_list)

    def _on_select_error_row(self, event):
        """Xử lý khi người dùng chọn một dòng lỗi trong bảng."""
        selected_items = self.tree_errors.selection()
        if not selected_items:
            return
        item_vals = self.tree_errors.item(selected_items[0], "values")
        if item_vals and len(item_vals) >= 7:
            stt, row, name, col, code, msg, val = item_vals
            detail_str = f"📍 [Dòng {row}] {name}  |  Cột: {col}  |  Mã lỗi: [{code}]\n⚠️ Chi tiết: {msg}\n🔍 Giá trị hiện tại: '{val}'"
            self.lbl_selected_detail.configure(text=detail_str)

    def _populate_preview_tree(self, cleaned_data: List[Dict[str, Any]]):
        """Nạp dữ liệu đã chuẩn hóa vào Tab Preview."""
        for item in self.tree_preview.get_children():
            self.tree_preview.delete(item)

        if not cleaned_data:
            return

        # Lấy tối đa 12 cột quan trọng nhất để hiển thị gọn gàng
        sample = cleaned_data[0]
        important_cols = [
            "STT", "Họ tên", "Ngày sinh", "Giới tính", "Số định danh cá nhân",
            "Số CCCD", "Mã định danh Bộ GD&ĐT", "Dân tộc", "Trạng thái HS",
            "Trạng thái", "Số điện thoại liên hệ", "SĐT liên hệ"
        ]
        display_cols = [c for c in important_cols if c in sample]
        if not display_cols:
            display_cols = list(sample.keys())[:10]

        self.tree_preview["columns"] = display_cols
        for c in display_cols:
            self.tree_preview.heading(c, text=c)
            self.tree_preview.column(c, width=130, minwidth=80, anchor="w")

        # Nạp tối đa 150 dòng để preview mượt mà
        for idx, row in enumerate(cleaned_data[:150], 1):
            vals = [row.get(c, "") for c in display_cols]
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree_preview.insert("", "end", values=vals, tags=(tag,))

    # ==========================================================================
    # CÁC THAO TÁC XUẤT FILE EXCEL
    # ==========================================================================
    def _on_export_cleaned_excel(self):
        """Nút 'Xuất file Excel chuẩn'."""
        if not self.current_report or not self.current_report.cleaned_data:
            messagebox.showwarning("Chưa có dữ liệu", "Vui lòng chạy 'Kiểm tra & Chuẩn hóa' trước khi xuất file!")
            return

        base_name = "Du_Lieu_Da_Chuan_Hoa.xlsx"
        if self.input_file_path:
            raw_base = os.path.splitext(os.path.basename(self.input_file_path))[0]
            base_name = f"Chuan_Hoa_{raw_base}.xlsx"

        target_file = filedialog.asksaveasfilename(
            title="Lưu file Excel chuẩn hóa",
            initialfile=base_name,
            defaultextension=".xlsx",
            filetypes=[("File Excel (*.xlsx)", "*.xlsx")]
        )
        if target_file:
            try:
                saved_path = self.current_report.to_excel_cleaned(target_file)
                self._update_status(f"Đã lưu file chuẩn hóa: {os.path.basename(saved_path)}")
                ret = messagebox.askyesno(
                    "Xuất file thành công!",
                    f"Đã xuất file Excel dữ liệu sạch tại:\n{saved_path}\n\nBạn có muốn mở file này ngay không?"
                )
                if ret:
                    self._open_file_system(saved_path)
            except Exception as e:
                messagebox.showerror("Lỗi khi lưu file", f"Không thể lưu file Excel: {e}")

    def _on_export_error_report(self):
        """Nút 'Xuất Báo cáo lỗi (Excel)'."""
        if not self.current_report or not self.current_report.errors:
            messagebox.showinfo("Không có lỗi", "Dữ liệu hiện tại hoàn toàn hợp lệ, không có lỗi vi phạm nào cần xuất báo cáo.")
            return

        base_name = "Bao_Cao_Loi_Du_Lieu.xlsx"
        if self.input_file_path:
            raw_base = os.path.splitext(os.path.basename(self.input_file_path))[0]
            base_name = f"Bao_Cao_Loi_{raw_base}.xlsx"

        target_file = filedialog.asksaveasfilename(
            title="Lưu file Báo cáo lỗi",
            initialfile=base_name,
            defaultextension=".xlsx",
            filetypes=[("File Excel (*.xlsx)", "*.xlsx")]
        )
        if target_file:
            try:
                saved_path = self.current_report.to_excel_report(target_file)
                self._update_status(f"Đã lưu báo cáo lỗi: {os.path.basename(saved_path)}")
                ret = messagebox.askyesno(
                    "Xuất báo cáo thành công!",
                    f"Đã xuất Báo cáo lỗi Excel tại:\n{saved_path}\n\nBạn có muốn mở file báo cáo ngay không?"
                )
                if ret:
                    self._open_file_system(saved_path)
            except Exception as e:
                messagebox.showerror("Lỗi khi lưu file", f"Không thể lưu file Báo cáo lỗi: {e}")

    def _on_open_output_folder(self):
        """Mở thư mục chứa file trong File Explorer."""
        folder_to_open = os.getcwd()
        if self.input_file_path and os.path.exists(os.path.dirname(self.input_file_path)):
            folder_to_open = os.path.dirname(self.input_file_path)

        if sys.platform == "win32":
            os.startfile(folder_to_open)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder_to_open])
        else:
            subprocess.Popen(["xdg-open", folder_to_open])

    def _open_file_system(self, file_path: str):
        """Mở trực tiếp file bằng ứng dụng mặc định (Excel)."""
        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
        except Exception as e:
            print(f"Lỗi mở file: {e}")

    def _update_ui_state(self):
        """Cập nhật trạng thái các nút và hiển thị."""
        has_file = bool(self.input_file_path and os.path.exists(self.input_file_path))
        self.btn_validate.configure(state="normal" if has_file else "disabled")

    def _update_status(self, text: str, timer_text: Optional[str] = None):
        """Cập nhật thanh trạng thái chân trang."""
        self.lbl_status.configure(text=text)
        if timer_text:
            self.lbl_timer.configure(text=timer_text)


# ==============================================================================
# HÀM KHỞI CHẠY ỨNG DỤNG
# ==============================================================================
def main():
    app = StudentDataValidatorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
