"""Convenience script: rebuild the standalone humantype EXE.

Usage:
    python build_exe.py
"""

import PyInstaller.__main__

if __name__ == "__main__":
    PyInstaller.__main__.run(["humantype.spec", "--noconfirm", "--clean"])
