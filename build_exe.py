"""Convenience script: rebuild the standalone humantype EXE.

Usage:
    python build_exe.py          # full build (with analyze charts)
    python build_exe.py --lite   # slim build (no matplotlib/numpy)
"""

import sys

import PyInstaller.__main__

if __name__ == "__main__":
    if "--lite" in sys.argv:
        spec = "humantype-lite.spec"
    else:
        spec = "humantype.spec"
    PyInstaller.__main__.run([spec, "--noconfirm", "--clean"])
