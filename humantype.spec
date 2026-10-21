# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone humantype GUI executable.

Build with:
    pyinstaller --noconfirm --clean humantype.spec

The output is dist/humantype.exe (a single windowed file, no console).
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = (
    ["win32com", "win32com.client"]
    + collect_submodules("pdfminer")
    + collect_submodules("pdfplumber")
    + collect_submodules("pyautogui")
)

datas = collect_data_files("docx")

a = Analysis(
    ["humantype/app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="humantype",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
