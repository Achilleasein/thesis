# file: code/python_implementation/GUI/GUI_functionality.py
import os
import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext
import threading
import queue
import time
from PIL import Image, ImageTk

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

class GUIController:
    def __init__(self, root: tk.Tk, audio_extensions=(".mp3", ".wav", ".flac", ".ogg", ".m4a")) -> None:
        self.root = root
        self.audio_extensions = audio_extensions
        self.current_dir = os.getcwd()
        self.detection_proc = None  # try to track spawned process if available

        # Track selections
        self.track1_path: str | None = None
        self.track2_path: str | None = None
        self.track1_var = tk.StringVar(value="Not selected")
        self.track2_var = tk.StringVar(value="Not selected")

        # UI elements
        self.controls_frame = None
        self.status_var = None
        # Embedded log widgets/state
        self.log_text: scrolledtext.ScrolledText | None = None
        self._log_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self._log_after_id: str | None = None
        # Results (images) area
        self.results_frame: tk.Frame | None = None
        self._image_refs: list[ImageTk.PhotoImage] = []
        self._run_start_time: float | None = None
        self._workdir: str | None = None

    def build_ui(self) -> None:
        self.root.title("Rhythm Detector - File Selector")
        self.root.geometry("1600x1200")
        self.root.minsize(600, 400)

        # Top controls
        self.controls_frame = tk.Frame(self.root, padx=10, pady=10)
        self.controls_frame.pack(fill=tk.X)

        # Track selection area
        tracks_frame = tk.LabelFrame(self.root, text="Tracks", padx=10, pady=10)
        tracks_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Row for Track 1
        row1 = tk.Frame(tracks_frame)
        row1.pack(fill=tk.X, pady=4)
        tk.Label(row1, text="Track 1:").pack(side=tk.LEFT)
        tk.Label(row1, textvariable=self.track1_var, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        tk.Button(row1, text="Choose...", command=self.select_track1).pack(side=tk.RIGHT)

        # Row for Track 2
        row2 = tk.Frame(tracks_frame)
        row2.pack(fill=tk.X, pady=4)
        tk.Label(row2, text="Track 2:").pack(side=tk.LEFT)
        tk.Label(row2, textvariable=self.track2_var, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))
        tk.Button(row2, text="Choose...", command=self.select_track2).pack(side=tk.RIGHT)

        # Embedded Execution Log (within main window)
        log_frame = tk.LabelFrame(self.root, text="Execution Log", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        # Simple styling via tags
        self.log_text.tag_configure("stdout", foreground="#154360")
        self.log_text.tag_configure("stderr", foreground="#7D1E1E")
        self.log_text.tag_configure("status", foreground="#555555")

        # Results (images) gallery below the log
        results_outer = tk.LabelFrame(self.root, text="Results", padx=10, pady=10)
        results_outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Scrollable frame for images
        canvas = tk.Canvas(results_outer)
        vsb = tk.Scrollbar(results_outer, orient="vertical", command=canvas.yview)
        hsb = tk.Scrollbar(results_outer, orient="horizontal", command=canvas.xview)
        self.results_frame = tk.Frame(canvas)

        self.results_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.results_frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # Action buttons
        actions = tk.Frame(self.root, padx=10, pady=10)
        actions.pack(fill=tk.X)

        run_btn = tk.Button(actions, text="Run Detection", command=self.run_detection_clicked)
        run_btn.pack(side=tk.LEFT)

        clear_btn = tk.Button(actions, text="Clear", command=self.clear_selection)
        clear_btn.pack(side=tk.LEFT, padx=(10, 0))

        close_btn = tk.Button(actions, text="Close", command=self.on_close)
        close_btn.pack(side=tk.RIGHT)

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = tk.Label(self.root, textvariable=self.status_var, anchor="w", relief=tk.SUNKEN, padx=8)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Window close protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start(self) -> None:
        self.build_ui()

    def _append_log(self, text: str, tag: str | None = None) -> None:
        if self.log_text is None:
            return
        if tag:
            self.log_text.insert(tk.END, text, tag)
        else:
            self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)

    def _enqueue_log(self, text: str, tag: str) -> None:
        self._log_queue.put((text, tag))

    def _drain_log_queue(self) -> None:
        try:
            while True:
                text, tag = self._log_queue.get_nowait()
                self._append_log(text, tag)
        except queue.Empty:
            pass
        finally:
            if self._log_after_id is None and self.root.winfo_exists():
                self._log_after_id = self.root.after(50, self._drain_log_queue)
            elif self.root.winfo_exists():
                # reschedule regardless
                self._log_after_id = self.root.after(50, self._drain_log_queue)

    def _start_log_pump_if_needed(self) -> None:
        if self._log_after_id is None and self.root.winfo_exists():
            self._drain_log_queue()

    def _start_stream_readers(self, proc) -> None:
        # Reader for stdout
        if getattr(proc, "stdout", None) is not None:
            threading.Thread(
                target=self._reader_loop,
                args=(proc.stdout, "stdout"),
                daemon=True,
            ).start()
        # Reader for stderr
        if getattr(proc, "stderr", None) is not None:
            threading.Thread(
                target=self._reader_loop,
                args=(proc.stderr, "stderr"),
                daemon=True,
            ).start()
        # Watcher for process completion
        def wait_and_mark():
            try:
                code = proc.wait()
                self._enqueue_log(f"\n[process exited with code {code}]\n", "status")
                # After completion, collect and show images created during this run
                if self._run_start_time is not None:
                    images = self._collect_result_images(self._run_start_time)
                    self.root.after(0, lambda: self._display_images(images))
            except Exception as e:
                self._enqueue_log(f"\n[process wait error: {e}]\n", "stderr")
        threading.Thread(target=wait_and_mark, daemon=True).start()
        # Ensure the UI pump is running
        self._start_log_pump_if_needed()

    def _reader_loop(self, fp, tag: str) -> None:
        try:
            for line in iter(fp.readline, ""):
                self._enqueue_log(line, tag)
        except Exception as e:
            self._enqueue_log(f"[reader error: {e}]\n", "stderr")

    def select_track1(self) -> None:
        def on_confirm(selected_files, chosen_dir):
            if not selected_files:
                return
            # Take the first selected file
            self.track1_path = selected_files[0]
            self.track1_var.set(self.track1_path)
            self.current_dir = chosen_dir
            self.status_var.set("Track 1 selected.")
        open_file_picker(
            parent=self.root,
            initial_dir=self.current_dir,
            audio_extensions=self.audio_extensions,
            on_confirm=on_confirm,
            title="Select Track 1"
        )

    def select_track2(self) -> None:
        def on_confirm(selected_files, chosen_dir):
            if not selected_files:
                return
            # Take the first selected file
            self.track2_path = selected_files[0]
            self.track2_var.set(self.track2_path)
            self.current_dir = chosen_dir
            self.status_var.set("Track 2 selected.")
        open_file_picker(
            parent=self.root,
            initial_dir=self.current_dir,
            audio_extensions=self.audio_extensions,
            on_confirm=on_confirm,
            title="Select Track 2"
        )

    def run_detection_clicked(self) -> None:
        # Ensure both tracks are chosen before running
        if not self.track1_path or not self.track2_path:
            messagebox.showerror("Selection Error", "Please select both Track 1 and Track 2 before running the detection.")
            return
        try:
            # Clear previous log and results
            if self.log_text is not None:
                self.log_text.delete("1.0", tk.END)
                self._append_log("Process started...\n", "status")
            self._clear_results()

            # Record start time and working directory where images are expected
            self._run_start_time = time.time()
            self._workdir = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

            # Start process and capture handle
            proc = run_rythm_detection([self.track1_path, self.track2_path])
            self.detection_proc = proc
            # Start streaming into embedded log and set up image collection
            self._start_stream_readers(proc)
            self.status_var.set("Started rythm_detection.py...")
        except Exception as e:
            messagebox.showerror("Execution Error", f"Failed to start detection:\n{e}")

    def clear_selection(self) -> None:
        self.track1_path = None
        self.track2_path = None
        self.track1_var.set("Not selected")
        self.track2_var.set("Not selected")
        self.status_var.set("Selection cleared.")
        if self.log_text is not None:
            self.log_text.delete("1.0", tk.END)
        if self.results_frame is not None:
            self._clear_results()

    def on_close(self) -> None:
        try:
            if self.detection_proc is not None:
                try:
                    # If the process is still running, attempt to stop it
                    if self.detection_proc.poll() is None:
                        self.status_var.set("Stopping detection...")
                        try:
                            self.detection_proc.terminate()
                            self.detection_proc.wait(timeout=3)
                        except Exception:
                            try:
                                self.detection_proc.kill()
                            except Exception:
                                pass
                except Exception:
                    pass
        finally:
            # Stop log pump
            if self._log_after_id is not None:
                try:
                    self.root.after_cancel(self._log_after_id)
                except Exception:
                    pass
                self._log_after_id = None
            self.root.destroy()

    def _clear_results(self) -> None:
        if self.results_frame is None:
            return
        for child in list(self.results_frame.children.values()):
            child.destroy()
        self._image_refs.clear()

    def _collect_result_images(self, since_time: float) -> list[str]:
        """
        Collect image file paths generated since 'since_time' in the working directory.
        """
        if not self._workdir:
            return []
        exts = {".png", ".jpg", ".jpeg", ".bmp"}
        found: list[tuple[float, str]] = []
        # Search the working directory and a 'results' subfolder if present
        search_roots = [self._workdir]
        results_dir = os.path.join(self._workdir, "results")
        if os.path.isdir(results_dir):
            search_roots.append(results_dir)

        for root_dir in search_roots:
            try:
                for dirpath, _, filenames in os.walk(root_dir):
                    for name in filenames:
                        if os.path.splitext(name)[1].lower() in exts:
                            full = os.path.join(dirpath, name)
                            try:
                                mtime = os.path.getmtime(full)
                                if mtime >= since_time - 1.0:  # small slack
                                    found.append((mtime, full))
                            except OSError:
                                pass
            except Exception:
                pass
        # Sort by time ascending
        found.sort(key=lambda t: t[0])
        return [p for _, p in found]

    def _display_images(self, image_paths: list[str]) -> None:
        """
        Display images in the results area, keeping references to prevent GC.
        """
        if self.results_frame is None:
            return
        if not image_paths:
            lbl = tk.Label(self.results_frame, text="No images were produced.", anchor="w")
            lbl.pack(fill=tk.X, pady=4)
            return

        # Clear any existing children
        self._clear_results()

        max_width = 1500  # fit nicely in the 1600px wide window
        for path in image_paths:
            try:
                img = Image.open(path)
                # Scale down if necessary to fit width
                if img.width > max_width:
                    scale = max_width / float(img.width)
                    new_size = (int(img.width * scale), int(img.height * scale))
                    img = img.resize(new_size, Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._image_refs.append(photo)

                # Caption with file name
                cap = tk.Label(self.results_frame, text=os.path.relpath(path, self._workdir or os.getcwd()), anchor="w")
                cap.pack(fill=tk.X, pady=(8, 2))

                # Image label
                lbl = tk.Label(self.results_frame, image=photo)
                lbl.pack(anchor="w")
            except Exception as e:
                err = tk.Label(self.results_frame, text=f"Failed to load image: {path} ({e})", fg="#7D1E1E", anchor="w")
                err.pack(fill=tk.X, pady=4)