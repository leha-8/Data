@echo off
title Phan Mem Kiem Tra & Chuan Hoa Du Lieu Hoc Sinh - So GD&DT
chcp 65001 >nul
cd /d "%~dp0"

echo ======================================================================
echo   PHAN MEM KIEM TRA & CHUAN HOA DU LIEU HOC SINH - SO GD&DT
echo ======================================================================
echo Dang khoi dong phan mem...

if exist "%~dp0PhanMem_KiemTra_HocSinh.exe" (
    start "" "%~dp0PhanMem_KiemTra_HocSinh.exe"
) else (
    py -X utf8 app.py
)
exit
