"""Spawning of the rhythm_detection worker process for the GUI.

Also the single place that puts the implementation directory on sys.path. This
module already owns the GUI-to-worker relationship, and every GUI module that
needs something from one level up (app_paths, rhythm_detection) imports this
one first, so doing it here means it is not repeated in each of them.
"""
import os
import subprocess
import sys
from typing import Sequence

# The analysis modules sit one level up and are imported by bare name. That
# directory is not on sys.path when the GUI/ folder is itself the script
# directory, which is how run.py starts the application.
IMPL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if IMPL_DIR not in sys.path:
    sys.path.insert(0, IMPL_DIR)

# Argument that puts the frozen application into worker mode instead of opening
# a window. Consumed by rhythm_detector_gui.main(); see WORKER_FLAG's use below
# for why a frozen build cannot simply run the script.
WORKER_FLAG = "--run-detection"


def _worker_command(arg_files: list[str]) -> tuple[list[str], str | None]:
    """Build the command line for the worker, and the cwd it should run in.

    Two very different situations:

    * From source, ``sys.executable`` is a Python interpreter and
      rhythm_detection.py is a real file on disk, so run it directly.
    * Frozen, there is no rhythm_detection.py to run -- the modules live inside
      the bundle -- and ``sys.executable`` is the application itself. So the
      application re-executes itself with WORKER_FLAG and dispatches to the
      analysis code before any window is created. One binary, two modes, and the
      GUI keeps streaming a real subprocess exactly as it does from source.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, WORKER_FLAG, *arg_files], None

    script_path = os.path.join(IMPL_DIR, "rhythm_detection.py")
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Could not find rhythm_detection.py at: {script_path}")
    # -u keeps the child's stdout unbuffered: without it Python block-buffers
    # when stdout is a pipe, so the "SAVED:" lines the GUI watches for would
    # only surface once the process exits.
    return [sys.executable, "-u", script_path, *arg_files], os.path.dirname(script_path)


def run_rhythm_detection(file_paths: Sequence[str]) -> subprocess.Popen:
    """
    Launch the rhythm detection worker in a separate process, passing one or more file paths.
    Returns:
        subprocess.Popen: the spawned process handle with stdout/stderr pipes
    Raises:
        ValueError: if no file paths are given
        FileNotFoundError: if the worker script cannot be found (source builds only)
        RuntimeError: if process fails to start
    """
    if not file_paths:
        raise ValueError("At least one file path is required.")

    # Ensure absolute paths for audio files
    arg_files = [os.path.abspath(p) for p in file_paths]
    command, cwd = _worker_command(arg_files)

    # The frozen bootloader has no -u to pass, so ask for unbuffered streams the
    # only other way CPython offers. Harmless on the source path, where -u has
    # already done the job.
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    try:
        # Pipe stdout/stderr so the GUI can display logs.
        # Not a context manager: the process deliberately outlives this call so
        # the GUI can stream its output and terminate it on close.
        proc = subprocess.Popen(  # pylint: disable=consider-using-with
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            # Windowed builds have no console of their own, so a console child
            # would pop up a stray black window for the length of the run.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        return proc
    except Exception as e:
        raise RuntimeError(f"Failed to start the rhythm detection worker: {e}") from e
