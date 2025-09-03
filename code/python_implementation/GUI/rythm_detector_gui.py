import tkinter as tk
from tkinter import filedialog, messagebox
import os

# Initialize main application window
root = tk.Tk()
# Top controls frame
controls_frame = tk.Frame(root, padx=10, pady=10)
controls_frame.pack(fill=tk.X)

# Keep track of the current directory for the custom picker
current_dir = os.getcwd()
audio_extensions = (".mp3", ".wav", ".flac", ".ogg", ".m4a")

# Import the separated file picker
try:
    from GUI.file_picker import open_file_picker
except ImportError:
    from file_picker import open_file_picker  # type: ignore

# Import code execution helper
try:
    from GUI.code_execution import run_rythm_detection
except ImportError:
    from code_execution import run_rythm_detection  # type: ignore

# The above imports remain available to keep backward compatibility, but UI logic is moved to GUI_functionality.

# Use the extracted GUI controller
try:
    from GUI.GUI_functionality import GUIController
except ImportError:
    from GUI_functionality import GUIController  # type: ignore

if __name__ == "__main__":
    # Build and start the GUI using the controller
    controller = GUIController(root, audio_extensions=audio_extensions)
    controller.start()
    root.mainloop()