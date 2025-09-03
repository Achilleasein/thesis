# file: code/python_implementation/GUI/code_execution.py
import os
import subprocess
import sys
from typing import Sequence

def run_rythm_detection(file_paths: Sequence[str]) -> subprocess.Popen:
    """
    Launch rythm_detection.py in a separate process, passing exactly two file paths.
    Returns:
        subprocess.Popen: the spawned process handle with stdout/stderr pipes
    Raises:
        ValueError: if file_paths length is not 2
        FileNotFoundError: if script cannot be found
        RuntimeError: if process fails to start
    """
    if len(file_paths) != 2:
        raise ValueError("Exactly 2 file paths are required.")

    # Resolve the path to rythm_detection.py relative to this file
    script_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "rythm_detection.py"))
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Could not find rythm_detection.py at: {script_path}")

    # Ensure absolute paths for audio files
    arg_files = [os.path.abspath(p) for p in file_paths]

    try:
        # Pipe stdout/stderr so the GUI can display logs
        proc = subprocess.Popen(
            [sys.executable, script_path, *arg_files],
            cwd=os.path.dirname(script_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        return proc
    except Exception as e:
        raise RuntimeError(f"Failed to start rythm_detection.py: {e}") from e