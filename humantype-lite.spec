# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the slim humantype EXE (no matplotlib/numpy charts).

Build with:
    pyinstaller --noconfirm --clean humantype-lite.spec

The typing engine is identical to the full build; only the analyze charts are
dropped (analyze still prints a full text report).
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
    excludes=["tkinter.test", "pytest", "matplotlib", "numpy"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="humantype-lite",
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
