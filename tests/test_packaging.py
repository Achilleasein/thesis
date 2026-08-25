"""Checks for the pieces that only differ between a source run and a build.

Everything here is about paths and process plumbing rather than signal
processing, and all of it is invisible from a source checkout: the frozen
branches cannot be exercised without building, so what these tests pin down is
the contracts around them -- where assets are looked up, which arguments select
which behaviour, and that the two halves of the worker handshake agree.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
IMPL_DIR = REPO_ROOT / "code" / "python_implementation"
GUI_DIR = IMPL_DIR / "GUI"
MUSIC_DIR = REPO_ROOT / "music_files"

# Same import roots the application uses: the analysis modules are a flat set of
# siblings, and the GUI modules import each other by bare name.
sys.path.insert(0, str(IMPL_DIR))
sys.path.insert(0, str(GUI_DIR))

# pylint: disable=wrong-import-position
import app_paths  # noqa: E402
import rhythm_detection  # noqa: E402
# pylint: enable=wrong-import-position


# ---------------------------------------------------------------- asset lookup

def test_bundled_tracks_found_from_source():
    """A source checkout must resolve both samples out of <repo>/music_files."""
    tracks = app_paths.bundled_tracks()

    assert len(tracks) == len(app_paths.SAMPLE_TRACK_NAMES)
    assert [Path(p).name for p in tracks] == list(app_paths.SAMPLE_TRACK_NAMES)
    for path in tracks:
        assert Path(path).is_file()
        assert Path(path).parent == MUSIC_DIR


def test_bundled_tracks_returns_only_existing_files(monkeypatch, tmp_path):
    """Callers branch on the length, so a missing sample must shorten the list.

    Returning a path that does not exist is what the old default_tracks() did,
    and it turned "the samples were not shipped" into a decode failure several
    seconds into a run.
    """
    monkeypatch.setattr(app_paths, "_music_dir_candidates", lambda: [tmp_path])
    assert not app_paths.bundled_tracks()

    (tmp_path / app_paths.SAMPLE_TRACK_NAMES[0]).write_bytes(b"not really audio")
    assert [Path(p).name for p in app_paths.bundled_tracks()] == [app_paths.SAMPLE_TRACK_NAMES[0]]


def test_results_dir_from_source_is_next_to_the_implementation():
    """Unfrozen behaviour is unchanged: plots stay in the working tree."""
    assert app_paths.results_dir() == IMPL_DIR / "results"


def test_music_dir_hint_names_every_place_searched():
    """The GUI puts this in a dialog, so it has to be the real search list."""
    hint = app_paths.music_dir_hint()

    assert str(MUSIC_DIR) in hint
    for candidate in app_paths._music_dir_candidates():  # pylint: disable=protected-access
        assert str(candidate) in hint


# ------------------------------------------------------- CLI file selection

def test_no_arguments_is_an_error_not_a_default_run():
    """An empty command line must analyse nothing.

    It used to fall back to the two bundled samples, which made them look like
    part of every run's output. Selecting them is now always explicit.
    """
    files, code = rhythm_detection.resolve_input_files([])

    assert files == []
    assert code == 2


def test_main_refuses_an_empty_command_line(monkeypatch):
    """The exit code has to survive the trip through main()."""
    monkeypatch.setattr(sys, "argv", ["rhythm_detection.py"])
    assert rhythm_detection.main() == 2


@pytest.mark.parametrize("argv", [
    ["track.mp3"],
    ["one.mp3", "two.wav"],
    ["  ", "one.mp3"],   # blank arguments are dropped, not analysed
])
def test_explicit_files_are_used_verbatim(argv):
    files, code = rhythm_detection.resolve_input_files(argv)

    assert code == 0
    assert files == [a for a in argv if a.strip()]


def test_default_tracks_flag_selects_the_samples():
    files, code = rhythm_detection.resolve_input_files([rhythm_detection.DEFAULT_TRACKS_FLAG])

    assert code == 0
    assert [Path(p).name for p in files] == list(app_paths.SAMPLE_TRACK_NAMES)


def test_default_tracks_flag_composes_with_own_files():
    """--default-tracks alongside a file analyses both, for A/B comparison."""
    files, code = rhythm_detection.resolve_input_files(
        [rhythm_detection.DEFAULT_TRACKS_FLAG, "mine.mp3"]
    )

    assert code == 0
    assert files[-1] == "mine.mp3"
    assert len(files) == len(app_paths.SAMPLE_TRACK_NAMES) + 1


def test_default_tracks_flag_fails_when_samples_are_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "_music_dir_candidates", lambda: [tmp_path])

    files, code = rhythm_detection.resolve_input_files([rhythm_detection.DEFAULT_TRACKS_FLAG])

    assert files == []
    assert code == 2


# ------------------------------------------------------- worker handshake

def test_worker_flag_round_trips_between_spawner_and_entry_point(monkeypatch):
    """The frozen app spawns itself; both halves must agree on the argument.

    code_execution builds the command line and rhythm_detector_gui.main()
    interprets it. Nothing imports the flag from a third place, so a rename on
    one side would only show up as a frozen build whose every run opens a second
    window instead of analysing anything.
    """
    import code_execution  # pylint: disable=import-outside-toplevel
    import rhythm_detector_gui  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    command, cwd = code_execution._worker_command(["/music/a.mp3"])  # pylint: disable=protected-access

    assert command == [sys.executable, code_execution.WORKER_FLAG, "/music/a.mp3"]
    assert cwd is None

    # Feed that command's arguments back to the entry point and confirm it
    # dispatches to the worker rather than opening a window.
    seen: list[list[str]] = []
    monkeypatch.setattr(rhythm_detector_gui, "run_worker", lambda argv: seen.append(argv) or 0)
    monkeypatch.setattr(rhythm_detector_gui, "run_gui",
                        lambda: pytest.fail("worker invocation opened the GUI"))
    monkeypatch.setattr(sys, "argv", command)

    assert rhythm_detector_gui.main() == 0
    assert seen == [["/music/a.mp3"]]


def test_entry_point_opens_the_gui_without_the_flag(monkeypatch):
    import rhythm_detector_gui  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(rhythm_detector_gui, "run_gui", lambda: 0)
    monkeypatch.setattr(rhythm_detector_gui, "run_worker",
                        lambda argv: pytest.fail("plain launch went to the worker"))
    monkeypatch.setattr(sys, "argv", ["RhythmDetector"])

    assert rhythm_detector_gui.main() == 0


def test_source_worker_command_points_at_the_real_script(monkeypatch):
    """Unfrozen, the worker is still a plain `python -u rhythm_detection.py` run."""
    import code_execution  # pylint: disable=import-outside-toplevel

    monkeypatch.delattr(sys, "frozen", raising=False)
    command, cwd = code_execution._worker_command(["/music/a.mp3"])  # pylint: disable=protected-access

    assert command[:2] == [sys.executable, "-u"]
    assert Path(command[2]) == IMPL_DIR / "rhythm_detection.py"
    assert command[3:] == ["/music/a.mp3"]
    assert Path(cwd) == IMPL_DIR
