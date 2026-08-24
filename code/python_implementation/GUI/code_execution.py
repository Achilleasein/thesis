"""Spawning of the rhythm_detection.py worker process for the GUI."""
import os
import subprocess
import sys
from typing import Sequence

def run_rhythm_detection(file_paths: Sequence[str]) -> subprocess.Popen:
    """
    Launch rhythm_detection.py in a separate process, passing one or more file paths.
    Returns:
        subprocess.Popen: the spawned process handle with stdout/stderr pipes
    Raises:
        ValueError: if no file paths are given
        FileNotFoundError: if script cannot be found
        RuntimeError: if process fails to start
    """
    if not file_paths:
        raise ValueError("At least one file path is required.")

    # Resolve the path to rhythm_detection.py relative to this file
    script_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "rhythm_detection.py"))
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Could not find rhythm_detection.py at: {script_path}")

    # Ensure absolute paths for audio files
    arg_files = [os.path.abspath(p) for p in file_paths]

    try:
        # Pipe stdout/stderr so the GUI can display logs. -u keeps the child's
        # stdout unbuffered: without it Python block-buffers when stdout is a
        # pipe, so the "SAVED:" lines the GUI watches for would only surface
        # once the process exits.
        # Not a context manager: the process deliberately outlives this call so
        # the GUI can stream its output and terminate it on close.
        proc = subprocess.Popen(  # pylint: disable=consider-using-with
            [sys.executable, "-u", script_path, *arg_files],
            cwd=os.path.dirname(script_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        return proc
    except Exception as e:
        raise RuntimeError(f"Failed to start rhythm_detection.py: {e}") from e
