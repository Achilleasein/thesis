# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Rhythm Detector CLI.
#
# Builds a single self-contained executable from rhythm_detection.py. Run from
# the repository root (the paths below are relative to this spec file):
#
#     pyinstaller rhythm_detection.spec
#
# Output: dist/rhythm_detection  (dist/rhythm_detection.exe on Windows)
#
# Cross-platform note: PyInstaller does NOT cross-compile. A given OS's binary
# can only be built on that OS, which is why the CI workflow builds the macOS,
# Windows and Linux versions on their respective runners.

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

# soundfile bundles the libsndfile shared library; audioread discovers its
# decoder backends dynamically. Collect both so the frozen binary can read
# audio without any system-level audio packages installed.
for _pkg in ("soundfile", "audioread"):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

a = Analysis(
    ['code/python_implementation/rhythm_detection.py'],
    pathex=['code/python_implementation'],  # so the sibling *_module imports resolve
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],  # CLI build: the GUI toolkit is not needed
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='rhythm_detection',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,           # CLI app: keep a console/stdout
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,       # build for the runner's native architecture
    codesign_identity=None,
    entitlements_file=None,
)
