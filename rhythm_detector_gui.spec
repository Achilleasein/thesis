# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Rhythm Detector GUI.
#
# Builds a single self-contained, windowed executable from the GUI entry point.
# Run from the repository root (the paths below are relative to this spec file):
#
#     pyinstaller rhythm_detector_gui.spec
#
# Output: dist/RhythmDetector       (dist/RhythmDetector.exe on Windows)
#         dist/Rhythm Detector.app  (additionally, on macOS)
#
# The same binary is also the analysis worker: the GUI re-executes itself with
# "--run-detection" because there is no rhythm_detection.py on disk to spawn
# once frozen (see GUI/code_execution.py and GUI/rhythm_detector_gui.py).
#
# Cross-platform note: PyInstaller does NOT cross-compile. A given OS's binary
# can only be built on that OS, which is why the CI workflow builds the macOS,
# Windows and Linux versions on their respective runners.

from PyInstaller.utils.hooks import collect_all

APP_NAME = 'RhythmDetector'
BUNDLE_NAME = 'Rhythm Detector.app'

datas, binaries, hiddenimports = [], [], []

# soundfile bundles the libsndfile shared library; audioread discovers its
# decoder backends dynamically. Collect both so the frozen binary can read
# audio without any system-level audio packages installed.
for _pkg in ("soundfile", "audioread"):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# Embed the sample tracks so "Default Execution" works from a bundle that has
# been moved away from the folder it was unzipped in. app_paths.bundled_tracks()
# looks here first, then for a sibling music_files/ folder.
datas += [(f'music_files/{_name}', 'music_files')
          for _name in ('pathfinder.mp3', 'celebration.mp3')]

# plot_handler is imported inside rhythm_detection.main() to keep matplotlib out
# of the import path of anything that only needs the analysis helpers; naming it
# here means the bytecode scan cannot miss it. ImageTk is the Pillow/Tk bridge
# the results gallery renders through.
hiddenimports += ['plot_handler', 'PIL.ImageTk']

a = Analysis(
    ['code/python_implementation/GUI/rhythm_detector_gui.py'],
    # Both levels: the GUI modules import each other by bare name, and they plus
    # the worker import the analysis modules (app_paths, rhythm_detection, ...)
    # by bare name from the directory above.
    pathex=['code/python_implementation', 'code/python_implementation/GUI'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # Windowed: no console window behind the GUI. The worker subprocess writes to
    # a pipe the GUI reads, so nothing depends on an attached terminal.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,       # build for the runner's native architecture
    # Ad-hoc signed in CI after the build instead (see build-executables.yml):
    # there is no Developer ID certificate to name here.
    codesign_identity=None,
    entitlements_file=None,
)

# macOS only -- ignored by PyInstaller on other platforms. Double-clicking a bare
# Mach-O executable in Finder opens a Terminal window; an .app bundle is what
# launches the GUI directly, and what `codesign` can sign as one unit.
app = BUNDLE(
    exe,
    name=BUNDLE_NAME,
    icon=None,
    bundle_identifier='com.github.achilleasein.rhythmdetector',
    info_plist={
        'CFBundleName': 'Rhythm Detector',
        'CFBundleDisplayName': 'Rhythm Detector',
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleVersion': '0.1.0',
        # Without this the window is rendered at 1x and upscaled, which on a
        # Retina display makes every plot in the results gallery look blurred.
        'NSHighResolutionCapable': True,
        # Nothing here is a document-based app, and no background agent: keep it
        # out of the "open with" lists and give it a normal Dock icon.
        'LSBackgroundOnly': False,
    },
)
