"""Entry point for the Rhythm Detector GUI.

All widget construction and event handling live in
``GUI_functionality.GUIController``; this module only creates the Tk root
window, hands it to the controller and enters the event loop.
"""
import tkinter as tk

try:
    from GUI.GUI_functionality import GUIController
except ImportError:  # launched as a script from inside the GUI/ folder
    from GUI_functionality import GUIController  # type: ignore

AUDIO_EXTENSIONS = (".mp3", ".wav", ".flac", ".ogg", ".m4a")


def main() -> None:
    root = tk.Tk()
    controller = GUIController(root, audio_extensions=AUDIO_EXTENSIONS)
    controller.start()
    root.mainloop()


if __name__ == "__main__":
    main()
