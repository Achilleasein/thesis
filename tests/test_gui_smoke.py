"""Headless checks for the GUI layer.

Nothing else in the suite touches the GUI, which makes it the easiest place for
breakage to go unnoticed: a bad relative import, a Pillow constant that moved,
or a PEP 604 annotation on an unsupported Python only fail when someone actually
launches the window.

No Tk root is created here, so these run without a display. That does bound what
they can catch -- annotations inside a function body are evaluated when the
function runs, not at import -- but it covers module-level and signature-level
breakage, plus the one piece of image logic that is reachable without a window.
"""
# The GUI modules are imported inside the tests, after tkinter has been checked
# for, so that a runner whose Python lacks Tk skips rather than fails.
# pylint: disable=import-outside-toplevel
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
IMPL_DIR = REPO_ROOT / "code" / "python_implementation"
GUI_DIR = IMPL_DIR / "GUI"

# run.py launches GUI/rhythm_detector_gui.py as a script, so the GUI folder is
# sys.path[0] at runtime and the modules import each other by bare name. Mirror
# that here rather than the (also supported) 'GUI.<module>' package form.
# The implementation directory above it holds app_paths and rhythm_detection,
# which the GUI imports by bare name too.
sys.path.insert(0, str(IMPL_DIR))
sys.path.insert(0, str(GUI_DIR))

# Skip the whole module where Tk is unavailable: these tests exist to catch our
# own breakage, not to assert that the runner's Python was built with Tk.
pytest.importorskip("tkinter")


@pytest.fixture(name="hidden_root")
def _hidden_root():
    """A real but never-displayed Tk root, skipped where no display exists."""
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError as exc:  # e.g. headless Linux CI with no X server
        pytest.skip(f"no display available: {exc}")
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


def _label_texts(widget):
    """Every Label caption under `widget`, in layout order."""
    import tkinter as tk

    found = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Label):
            found.append(child.cget("text"))
        else:
            found.extend(_label_texts(child))
    return found


def _buttons(widget):
    """Every Button under `widget`, keyed by its caption."""
    import tkinter as tk

    found = {}
    for child in widget.winfo_children():
        if isinstance(child, tk.Button):
            found[child.cget("text")] = child
        else:
            found.update(_buttons(child))
    return found


# Driving the controller means going through its queue and drain, which are
# internal by design -- there is no public seam for "pretend the worker spoke".
# pylint: disable=protected-access
def _pump(controller, lines):
    """Feed worker output through the real queue, then finalise as a run end would."""
    import GUI_functionality

    for line in lines:
        controller._enqueue_log(line, "stdout")
    controller._log_queue.put((GUI_functionality._RUN_FINISHED, "status"))
    controller._drain_log_queue()
    controller.root.update()
    if controller._log_after_id:
        controller.root.after_cancel(controller._log_after_id)


def test_tempo_panel_shows_one_row_per_result(hidden_root):
    """A TEMPO: line per track becomes a labelled BPM row, ignoring log noise."""
    import GUI_functionality
    from rhythm_detection import format_tempo_line

    controller = GUI_functionality.GUIController(hidden_root)
    controller.build_ui()
    assert "Run Detection" in _label_texts(controller.tempo_frame)[0]

    _pump(controller, [
        format_tempo_line("/music/pathfinder.mp3", 120.0) + "\n",
        "2026-01-01 [INFO] unrelated log line\n",
        format_tempo_line("/music/celebration.mp3", 80.0) + "\n",
    ])

    assert _label_texts(controller.tempo_frame) == [
        "pathfinder.mp3", "120 BPM", "celebration.mp3", "80 BPM",
    ]
    assert controller._tempo_results == [
        ("/music/pathfinder.mp3", 120.0), ("/music/celebration.mp3", 80.0),
    ]
    # The status bar echoes the most recent result.
    assert "80 BPM" in controller.status_var.get()


def test_tempo_panel_says_so_when_nothing_was_detected(hidden_root):
    """An empty panel is ambiguous with 'still running', so say it explicitly."""
    import GUI_functionality

    controller = GUI_functionality.GUIController(hidden_root)
    controller.build_ui()

    _pump(controller, ["2026-01-01 [ERROR] Failed to read audio file\n"])

    texts = _label_texts(controller.tempo_frame)
    assert texts == ["No tempo detected. See the execution log for details."]
    assert not controller._tempo_results


def test_default_execution_button_exists(hidden_root):
    """The bundled tracks are reachable from the window, and only on request."""
    import GUI_functionality

    controller = GUI_functionality.GUIController(hidden_root)
    controller.build_ui()

    buttons = _buttons(controller.root)
    assert "Default Execution" in buttons, sorted(buttons)
    assert buttons["Default Execution"].cget("command"), "button is not wired to anything"

    # Nothing is selected until it is pressed: the tracks must never be picked
    # for the user just because the window opened.
    assert controller.track1_path is None
    assert controller.track2_path is None
    assert controller.track1_var.get() == "Not selected"


def test_default_execution_fills_both_tracks_and_runs(hidden_root):
    """It selects the two samples and hands straight over to the normal run path.

    run_detection_clicked is stubbed out: this is about the selection and the
    delegation, not about spawning a real analysis subprocess.
    """
    import GUI_functionality

    controller = GUI_functionality.GUIController(hidden_root)
    controller.build_ui()

    started = []
    controller.run_detection_clicked = lambda: started.append(True)
    controller.run_default_execution()

    assert started == [True], "the run was not started"
    assert controller.track1_path is not None and controller.track2_path is not None
    assert Path(controller.track1_path).name == "pathfinder.mp3"
    assert Path(controller.track2_path).name == "celebration.mp3"
    # The labels must echo the selection, or the run looks like it came from nowhere.
    assert controller.track1_var.get() == controller.track1_path
    assert controller.track2_var.get() == controller.track2_path


def test_default_execution_reports_missing_samples(hidden_root, monkeypatch):
    """With no samples on disk it must explain itself, not start an empty run."""
    import app_paths
    import GUI_functionality

    monkeypatch.setattr(app_paths, "bundled_tracks", lambda: [])
    controller = GUI_functionality.GUIController(hidden_root)
    controller.build_ui()

    shown = []
    monkeypatch.setattr(GUI_functionality.messagebox, "showerror",
                        lambda title, message, **kw: shown.append((title, message)))
    controller.run_detection_clicked = lambda: pytest.fail("ran with no tracks selected")

    controller.run_default_execution()

    assert len(shown) == 1
    # The dialog has to say where it looked -- that differs between a checkout
    # and an unzipped download, so a bare "not found" is unactionable.
    assert "music_files" in shown[0][1]
    assert controller.track1_path is None


def test_gui_modules_import():
    """Every GUI module imports cleanly and exposes what its callers use."""
    import code_execution
    import file_picker
    import GUI_functionality
    import rhythm_detector_gui

    assert callable(code_execution.run_rhythm_detection)
    assert callable(file_picker.open_file_picker)
    assert callable(GUI_functionality.GUIController)
    assert callable(rhythm_detector_gui.main)
    # The entry point must not build a window at import time -- it used to, which
    # left a stray empty frame in the packed layout.
    assert not hasattr(rhythm_detector_gui, "root")


def test_pillow_resampling_constant_exists():
    """Guards the Image.Resampling.LANCZOS used when downscaling result images.

    The older top-level Image.LANCZOS alias is deprecated; if a future Pillow
    reshuffles this again, failing here is far better than failing inside a
    resize call that only runs when a user has a plot on screen.
    """
    from PIL import Image

    assert Image.Resampling.LANCZOS is not None


@pytest.mark.parametrize("path", [
    "/music/pathfinder.mp3",
    "/music/with spaces/my track 01.mp3",   # spaces must not truncate the path
    "relative/celebration.mp3",
])
@pytest.mark.parametrize("bpm", [120.0, 80.5, 60.0, 179.99])
def test_tempo_line_round_trips_from_worker_to_gui(path, bpm):
    """The worker's TEMPO: line must parse with the regex the GUI matches it against.

    This is a contract between two files that never import each other, so
    nothing else would notice if one side's format drifted -- the tempo would
    simply stop appearing in the window.
    """
    import GUI_functionality
    from rhythm_detection import format_tempo_line

    match = GUI_functionality.TEMPO_LINE_RE.match(format_tempo_line(path, bpm))

    assert match is not None, f"GUI cannot parse {format_tempo_line(path, bpm)!r}"
    assert float(match.group("bpm")) == pytest.approx(bpm, abs=0.005)
    assert match.group("path") == path


def test_tempo_line_ignores_unrelated_output():
    """Ordinary log lines must not be mistaken for results."""
    import GUI_functionality

    for line in ("INFO: analysing TEMPO: stuff\n",
                 "TEMPO: not-a-number BPM /x.mp3\n",
                 "SAVED: /results/celebration_total.png\n",
                 "Fundamental Tempo: 120.00 BPM\n"):  # the old format, no path
        assert GUI_functionality.TEMPO_LINE_RE.match(line) is None, line


@pytest.mark.parametrize("mode,colour,expected", [
    ("RGBA", (255, 0, 0, 0), (255, 255, 255)),    # fully transparent -> white
    ("RGBA", (255, 0, 0, 255), (255, 0, 0)),      # opaque -> unchanged
    ("P", None, None),                            # palette -> converted to RGB
])
def test_load_opaque_flattens_transparency(tmp_path, mode, colour, expected):
    """_load_opaque must flatten alpha onto white and normalise exotic modes.

    Tested directly because it is a staticmethod: the rest of the image path
    needs a Tk root, but this part is pure and carries the actual logic.
    """
    from PIL import Image

    import GUI_functionality

    path = tmp_path / f"sample_{mode}.png"
    if colour is None:
        Image.new("RGB", (4, 4), (0, 128, 0)).convert("P").save(path)
    else:
        Image.new(mode, (4, 4), colour).save(path)

    out = GUI_functionality.GUIController._load_opaque(str(path))  # pylint: disable=protected-access

    assert out.mode in ("RGB", "L"), f"unexpected mode {out.mode}"
    if expected is not None:
        assert out.getpixel((0, 0)) == expected
