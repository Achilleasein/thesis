"""Where the application's files live, running from source or frozen.

Four callers need to answer "where is X?" and each has to cope with two very
different layouts: a checked-out repository, and a PyInstaller bundle where the
Python modules have been extracted to a temporary directory that is deleted on
exit. Keeping the answers here means the frozen/source distinction is made once
instead of in every caller.

Deliberately imports nothing beyond the standard library: the GUI process
imports this module to find the sample tracks, and must not pull in numpy,
scipy or matplotlib to do it.
"""
import os
import sys
from pathlib import Path

# The two sample tracks shipped with the project, in the order the GUI's
# "Default Execution" button assigns them to Track 1 and Track 2.
SAMPLE_TRACK_NAMES = ("pathfinder.mp3", "celebration.mp3")

# Written to the user's home directory when frozen -- see results_dir().
FROZEN_OUTPUT_DIRNAME = "RhythmDetector"

_MUSIC_DIRNAME = "music_files"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle rather than the source tree."""
    return getattr(sys, "frozen", False)


def repo_root() -> Path:
    """The repository root, i.e. two levels above code/python_implementation/."""
    return Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    """Directory holding read-only files bundled *inside* the application.

    PyInstaller unpacks ``datas`` into ``sys._MEIPASS`` at startup, so that is
    where embedded assets are found. From source the repository serves the same
    purpose.
    """
    if is_frozen():
        # _MEIPASS is absent for a --onedir build, where the bundled files sit
        # next to the executable instead.
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return repo_root()


def app_dir() -> Path:
    """The directory the *user* sees the application in.

    This is where a sibling ``music_files/`` folder shipped alongside the
    download would be. On macOS ``sys.executable`` points inside the bundle
    (``Rhythm Detector.app/Contents/MacOS/Rhythm Detector``), so climb back out
    to the folder that contains the ``.app`` -- that is the level the user
    unzipped, and the level the sibling folder is at.
    """
    if not is_frozen():
        return repo_root()

    exe_dir = Path(sys.executable).resolve().parent
    for parent in exe_dir.parents:
        if parent.suffix == ".app":
            return parent.parent
    return exe_dir


def _music_dir_candidates() -> list[Path]:
    """Places to look for the sample audio, most-specific first.

    The embedded copy is preferred so that a bundle moved out of its download
    folder keeps working; a sibling ``music_files/`` still wins over nothing,
    which is what makes the visible folder in the zip usable.
    """
    seen: list[Path] = []
    for base in (resource_root(), app_dir(), repo_root()):
        candidate = base / _MUSIC_DIRNAME
        if candidate not in seen:
            seen.append(candidate)
    return seen


def bundled_tracks() -> list[str]:
    """Absolute paths of the sample tracks that actually exist on this machine.

    Each name is resolved independently against the candidate folders, so a
    partial install yields the tracks it does have rather than nothing. Callers
    are expected to check the length: returning only what exists lets the GUI
    disable its button with a useful message instead of launching a run that
    fails on the first read.
    """
    found: list[str] = []
    candidates = _music_dir_candidates()
    for name in SAMPLE_TRACK_NAMES:
        for directory in candidates:
            path = directory / name
            if path.is_file():
                found.append(str(path))
                break
    return found


def music_dir_hint() -> str:
    """Human-readable list of the folders bundled_tracks() searched.

    Used verbatim in the GUI's "tracks not found" dialog: without it the error
    is unactionable, because where the app looked depends on how it was built.
    """
    return "\n".join(f"  {p}" for p in _music_dir_candidates())


def results_dir() -> Path:
    """Directory the analysis plots are written to.

    Frozen builds must not write next to the executable. Inside a macOS ``.app``
    that means writing into ``Contents/MacOS/``, which invalidates the code
    signature and is read-only once the app is in ``/Applications``; on Windows
    the same applies under ``Program Files``. A folder in the user's home
    directory is always writable and easy to find again.
    """
    if is_frozen():
        return Path.home() / FROZEN_OUTPUT_DIRNAME / "results"
    return Path(__file__).resolve().parent / "results"


def ensure_results_dir() -> str:
    """Create results_dir() if needed and return it as a string."""
    path = results_dir()
    os.makedirs(path, exist_ok=True)
    return str(path)
