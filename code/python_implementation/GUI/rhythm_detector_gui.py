"""Entry point for the Rhythm Detector application.

Normally this opens the GUI: all widget construction and event handling live in
``GUI_functionality.GUIController``, and this module only creates the Tk root
window, hands it to the controller and enters the event loop.

Given ``--run-detection`` it instead acts as the analysis worker. A frozen build
has no rhythm_detection.py on disk to spawn, so the application re-executes
itself with that flag and dispatches here; see ``code_execution._worker_command``
for the other half of the arrangement.
"""
import sys

# Importing code_execution also puts the implementation directory on sys.path,
# which is what makes `import rhythm_detection` work in run_worker below.
try:
    from GUI.code_execution import WORKER_FLAG
except ImportError:  # launched as a script from inside the GUI/ folder
    from code_execution import WORKER_FLAG  # type: ignore

AUDIO_EXTENSIONS = (".mp3", ".wav", ".flac", ".ogg", ".m4a")


def run_worker(argv: list[str]) -> int:
    """Run the analysis pipeline in-process and return its exit code.

    The GUI parses the worker's stdout line by line (the ``TEMPO:`` and
    ``SAVED:`` lines), so the streams are switched to line buffering: a frozen
    build has no ``-u`` flag to pass, and block-buffered output would only reach
    the window when the process exited.
    """
    # Imported here, not at module scope, so the GUI path does not pay for numpy
    # and scipy and the worker path does not pay for tkinter and Pillow.
    import rhythm_detection  # pylint: disable=import-outside-toplevel

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)
        except (AttributeError, ValueError):  # already closed, or not a TextIOWrapper
            pass

    sys.argv = [sys.argv[0], *argv]
    return rhythm_detection.main()


def run_gui() -> int:
    """Open the main window and run the Tk event loop until it is closed."""
    import tkinter as tk  # pylint: disable=import-outside-toplevel

    try:
        from GUI.GUI_functionality import GUIController  # pylint: disable=import-outside-toplevel
    except ImportError:  # launched as a script from inside the GUI/ folder
        from GUI_functionality import GUIController  # type: ignore  # pylint: disable=import-outside-toplevel

    root = tk.Tk()
    controller = GUIController(root, audio_extensions=AUDIO_EXTENSIONS)
    controller.start()
    root.mainloop()
    return 0


def main() -> int:
    """Dispatch to the worker when asked for it, otherwise open the GUI."""
    if sys.argv[1:2] == [WORKER_FLAG]:
        return run_worker(sys.argv[2:])
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
