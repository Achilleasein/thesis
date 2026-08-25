"""Tk controller for the Rhythm Detector: widgets, log streaming and results.

The module name keeps the capitalised form of its GUI/ package directory rather
than snake_case, so the naming check is suppressed for this file alone.
"""
# pylint: disable=invalid-name
import os
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog

from PIL import Image, ImageTk

# Absolute imports when launched as a package, sibling imports when the GUI/
# folder is itself the script directory (which is how run.py starts it).
try:
    from GUI.file_picker import open_file_picker
    from GUI.code_execution import run_rhythm_detection
except ImportError:
    from file_picker import open_file_picker  # type: ignore
    from code_execution import run_rhythm_detection  # type: ignore

# Must follow code_execution, which is what puts the implementation directory on
# sys.path -- app_paths lives there, one level up, alongside the worker.
import app_paths  # pylint: disable=wrong-import-position

# Enqueued once the worker's streams are fully drained, so the UI finalises only
# after every real output line has been handled.
_RUN_FINISHED = object()

# The worker's machine-readable stdout lines. Module-level so the wire format can
# be tested without constructing a controller (which needs a live Tk root):
# rhythm_detection.format_tempo_line is the producer for TEMPO_LINE_RE, and
# plot_handler prints the SAVED: lines. The tempo pattern puts the number before
# the path so a path containing spaces is still captured whole.
SAVED_LINE_RE = re.compile(r"^\s*SAVED:\s*(?P<path>.+\.(?:png|jpg|jpeg|bmp))\s*$", re.IGNORECASE)
TEMPO_LINE_RE = re.compile(r"^\s*TEMPO:\s*(?P<bpm>[0-9]+(?:\.[0-9]+)?)\s*BPM\s+(?P<path>.+?)\s*$",
                           re.IGNORECASE)


class GUIController:
    """Owns the main window: track selection, run control, log and results."""

    def __init__(self, root: tk.Tk, audio_extensions=(".mp3", ".wav", ".flac", ".ogg", ".m4a")) -> None:
        self.root = root
        self.audio_extensions = audio_extensions
        self.current_dir = os.getcwd()
        self.detection_proc = None  # track spawned process

        # Track selections
        self.track1_path: str | None = None
        self.track2_path: str | None = None
        self.track1_var = tk.StringVar(value="Not selected")
        self.track2_var = tk.StringVar(value="Not selected")

        # UI elements and state
        self.controls_frame: tk.Frame | None = None
        self.status_var: tk.StringVar | None = None

        # Embedded log
        self.log_text: scrolledtext.ScrolledText | None = None
        self._log_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self._log_after_id: str | None = None

        # Results (images) area
        self.results_frame: tk.Frame | None = None
        self._image_refs: list[ImageTk.PhotoImage] = []
        self._run_start_time: float | None = None
        self._workdir: str | None = None
        self._last_image_paths: list[str] = []

        # Detected tempo area
        self.tempo_frame: tk.LabelFrame | None = None
        self._tempo_placeholder: tk.Label | None = None
        self._tempo_results: list[tuple[str, float]] = []


    def build_ui(self) -> None:
        """Construct every widget: controls bar, track rows, log and results gallery."""
        self.root.title("Rhythm Detector - File Selector")
        self.root.geometry("1600x1200")
        self.root.minsize(600, 400)

        # Top controls bar
        self.controls_frame = tk.Frame(self.root, padx=10, pady=10)
        self.controls_frame.pack(fill=tk.X)

        # Left: primary actions
        btns_frame = tk.Frame(self.controls_frame)
        btns_frame.pack(side=tk.LEFT)

        # Leftmost: the one-click route through the whole pipeline, for a first
        # run with no file picking. The bundled tracks are never selected
        # implicitly -- pressing this is the only thing that chooses them.
        default_btn = tk.Button(btns_frame, text="Default Execution",
                                command=self.run_default_execution)
        default_btn.pack(side=tk.LEFT, padx=(0, 8))

        run_btn = tk.Button(btns_frame, text="Run Detection", command=self.run_detection_clicked)
        run_btn.pack(side=tk.LEFT, padx=(0, 8))

        clear_btn = tk.Button(btns_frame, text="Clear", command=self.clear_selection)
        clear_btn.pack(side=tk.LEFT, padx=(0, 8))

        close_btn = tk.Button(btns_frame, text="Close", command=self.on_close)
        close_btn.pack(side=tk.LEFT)

        # Right: compact track selection
        tracks_frame = tk.LabelFrame(self.controls_frame, text="Tracks", padx=6, pady=6)
        tracks_frame.pack(side=tk.RIGHT)

        font_small = ("TkDefaultFont", 9)

        # Track 1 row
        row1 = tk.Frame(tracks_frame)
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="Track 1:", font=font_small).pack(side=tk.LEFT)
        tk.Label(row1, textvariable=self.track1_var, anchor="w", font=font_small, width=60).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6)
        )
        tk.Button(row1, text="Choose...", command=self.select_track1).pack(side=tk.RIGHT)

        # Track 2 row
        row2 = tk.Frame(tracks_frame)
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Track 2:", font=font_small).pack(side=tk.LEFT)
        tk.Label(row2, textvariable=self.track2_var, anchor="w", font=font_small, width=60).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6)
        )
        tk.Button(row2, text="Choose...", command=self.select_track2).pack(side=tk.RIGHT)

        # Detected tempo: the headline result, above the log so it is the first
        # thing read. fill=X without expand keeps it compact as rows are added.
        self.tempo_frame = tk.LabelFrame(self.root, text="Detected Tempo", padx=10, pady=8)
        self.tempo_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._clear_tempo_results()

        # Embedded Execution Log
        log_frame = tk.LabelFrame(self.root, text="Execution Log", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_configure("stdout", foreground="#154360")
        self.log_text.tag_configure("stderr", foreground="#7D1E1E")
        self.log_text.tag_configure("status", foreground="#555555")

        # Results (images) gallery below the log
        results_outer = tk.LabelFrame(self.root, text="Results", padx=10, pady=10)
        results_outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Results actions (Save All)
        results_actions = tk.Frame(results_outer)
        results_actions.pack(fill=tk.X, side=tk.TOP, pady=(0, 8))
        tk.Button(results_actions, text="Save All as PNG…", command=self._save_all_images_png).pack(side=tk.RIGHT)

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

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = tk.Label(self.root, textvariable=self.status_var, anchor="w", relief=tk.SUNKEN, padx=8)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Close protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start(self) -> None:
        self.build_ui()

    # -----------------------
    # Logging (embedded)
    # -----------------------
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
        # Runs on the Tk main thread (driven by root.after), so it is safe to
        # touch widgets here -- including the tempo readout and the images
        # announced by the worker's "TEMPO:" and "SAVED:" lines.
        try:
            while True:
                text, tag = self._log_queue.get_nowait()
                if text is _RUN_FINISHED:
                    self._finalise_tempo_results()
                    continue
                self._append_log(text, tag)
                self._maybe_show_tempo(text)
                self._maybe_show_saved_image(text)
        except queue.Empty:
            pass
        finally:
            if self.root.winfo_exists():
                self._log_after_id = self.root.after(50, self._drain_log_queue)

    def _maybe_show_tempo(self, line: str) -> None:
        """Show the detected tempo as soon as the worker reports it."""
        match = TEMPO_LINE_RE.match(line)
        if match is None:
            return
        try:
            bpm = float(match.group("bpm"))
        except ValueError:  # not a number after all; leave it in the log only
            return
        self._add_tempo_result(match.group("path").strip(), bpm)

    def _maybe_show_saved_image(self, line: str) -> None:
        """Render a plot as soon as the worker announces it with a SAVED: line."""
        match = SAVED_LINE_RE.match(line)
        if match is None:
            return
        path = match.group("path").strip()
        if path in self._last_image_paths or not os.path.isfile(path):
            return
        self._append_image_card(path)

    def _start_log_pump_if_needed(self) -> None:
        if self._log_after_id is None and self.root.winfo_exists():
            self._drain_log_queue()

    def _reader_loop(self, fp, tag: str) -> None:
        try:
            for line in iter(fp.readline, ""):
                self._enqueue_log(line, tag)
        except Exception as e:
            self._enqueue_log(f"[reader error: {e}]\n", "stderr")

    def _start_stream_readers(self, proc) -> None:
        readers = []
        for stream, tag in (("stdout", "stdout"), ("stderr", "stderr")):
            fp = getattr(proc, stream, None)
            if fp is not None:
                thread = threading.Thread(target=self._reader_loop, args=(fp, tag), daemon=True)
                readers.append(thread)
                thread.start()

        def wait_and_mark():
            try:
                code = proc.wait()
                # Wait for the readers before announcing the end: proc.wait()
                # can return while the last lines are still being enqueued, and
                # finalising early would report "no tempo detected" for a run
                # whose TEMPO: line simply had not been processed yet.
                for thread in readers:
                    thread.join(timeout=5)
                self._enqueue_log(f"\n[process exited with code {code}]\n", "status")
                # Queued rather than scheduled directly, so it is handled after
                # every real line ahead of it in the same FIFO.
                self._log_queue.put((_RUN_FINISHED, "status"))
                # After completion, collect and show images created during this run
                if self._run_start_time is not None:
                    images = self._collect_result_images(self._run_start_time)
                    self.root.after(0, lambda: self._display_images(images))
            except Exception as e:
                self._enqueue_log(f"\n[process wait error: {e}]\n", "stderr")

        threading.Thread(target=wait_and_mark, daemon=True).start()
        self._start_log_pump_if_needed()

    # -----------------------
    # Track selection
    # -----------------------
    def select_track1(self) -> None:
        def on_confirm(selected_files, chosen_dir):
            if not selected_files:
                return
            self.track1_path = selected_files[0]
            self.track1_var.set(self.track1_path)
            self.current_dir = chosen_dir
            if self.status_var:
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
            self.track2_path = selected_files[0]
            self.track2_var.set(self.track2_path)
            self.current_dir = chosen_dir
            if self.status_var:
                self.status_var.set("Track 2 selected.")
        open_file_picker(
            parent=self.root,
            initial_dir=self.current_dir,
            audio_extensions=self.audio_extensions,
            on_confirm=on_confirm,
            title="Select Track 2"
        )

    # -----------------------
    # Run / Clear / Close
    # -----------------------
    def run_default_execution(self) -> None:
        """Load the two bundled sample tracks and start the run immediately.

        app_paths.bundled_tracks() returns only files that exist, so a short list
        means the samples were not shipped with this copy of the application --
        report where it looked, because the answer differs between a source
        checkout and an unzipped download.
        """
        tracks = app_paths.bundled_tracks()
        if len(tracks) < 2:
            messagebox.showerror(
                "Sample Tracks Not Found",
                "The bundled sample tracks could not be located.\n\n"
                f"Looked in:\n{app_paths.music_dir_hint()}\n\n"
                "Choose your own tracks with the 'Choose...' buttons instead.",
            )
            return

        self.track1_path, self.track2_path = tracks[0], tracks[1]
        self.track1_var.set(self.track1_path)
        self.track2_var.set(self.track2_path)
        if self.status_var:
            self.status_var.set("Default tracks selected.")
        self.run_detection_clicked()

    def run_detection_clicked(self) -> None:
        """Launch the detector on whichever tracks are selected and stream its output."""
        tracks = [p for p in (self.track1_path, self.track2_path) if p]
        if not tracks:
            messagebox.showerror("Selection Error",
                                 "Please select at least one track before running the detection.")
            return
        try:
            # Clear previous log and results
            if self.log_text is not None:
                self.log_text.delete("1.0", tk.END)
                self._append_log("Process started...\n", "status")
            self._clear_results()
            self._clear_tempo_results()

            # Record start time and the directory the worker writes plots into.
            # Asking app_paths rather than assuming a path next to this file is
            # what keeps the post-run image sweep working in a frozen build,
            # where the plots land in the user's home directory instead.
            self._run_start_time = time.time()
            self._workdir = str(app_paths.results_dir())

            # Launch process
            proc = run_rhythm_detection(tracks)
            self.detection_proc = proc

            # Hook up streaming
            self._start_stream_readers(proc)
            if self.status_var:
                self.status_var.set("Started rhythm_detection.py...")
        except Exception as e:
            messagebox.showerror("Execution Error", f"Failed to start detection:\n{e}")

    def clear_selection(self) -> None:
        self.track1_path = None
        self.track2_path = None
        self.track1_var.set("Not selected")
        self.track2_var.set("Not selected")
        if self.status_var:
            self.status_var.set("Selection cleared.")
        if self.log_text is not None:
            self.log_text.delete("1.0", tk.END)
        self._clear_results()
        self._clear_tempo_results()

    def on_close(self) -> None:
        """Stop any running detection, cancel the log pump and destroy the window."""
        try:
            if self.detection_proc is not None:
                try:
                    if self.detection_proc.poll() is None:
                        if self.status_var:
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
            if self._log_after_id is not None:
                try:
                    self.root.after_cancel(self._log_after_id)
                except Exception:
                    pass
                self._log_after_id = None
            self.root.destroy()

    # -----------------------
    # Detected tempo
    # -----------------------
    def _clear_tempo_results(self) -> None:
        """Empty the tempo panel and put the placeholder back."""
        if self.tempo_frame is None:
            return
        for child in list(self.tempo_frame.children.values()):
            child.destroy()
        self._tempo_results = []
        self._tempo_placeholder = tk.Label(
            self.tempo_frame,
            text="Press Default Execution for the sample tracks, "
                 "or choose your own and press Run Detection.",
            anchor="w", fg="#555555",
        )
        self._tempo_placeholder.pack(fill=tk.X)

    def _add_tempo_result(self, path: str, bpm: float) -> None:
        """Append one '<track>  <bpm> BPM' row, replacing the placeholder."""
        if self.tempo_frame is None:
            return
        if self._tempo_placeholder is not None:
            self._tempo_placeholder.destroy()
            self._tempo_placeholder = None

        self._tempo_results.append((path, bpm))

        row = tk.Frame(self.tempo_frame)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=os.path.basename(path), anchor="w",
                 font=("TkDefaultFont", 12)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(row, text=f"{bpm:g} BPM", anchor="e",
                 font=("TkDefaultFont", 20, "bold")).pack(side=tk.RIGHT)

        if self.status_var:
            self.status_var.set(f"{os.path.basename(path)}: {bpm:g} BPM")

    def _finalise_tempo_results(self) -> None:
        """After the worker exits, say so explicitly if nothing was detected.

        An empty panel is ambiguous -- it looks the same as 'still running' --
        so point at the log, which will hold the traceback.
        """
        if self.tempo_frame is None or self._tempo_results:
            return
        if self._tempo_placeholder is not None:
            self._tempo_placeholder.destroy()
        self._tempo_placeholder = tk.Label(
            self.tempo_frame,
            text="No tempo detected. See the execution log for details.",
            anchor="w", fg="#7D1E1E",
        )
        self._tempo_placeholder.pack(fill=tk.X)

    # -----------------------
    # Images (Results)
    # -----------------------
    def _clear_results(self) -> None:
        if self.results_frame is None:
            return
        for child in list(self.results_frame.children.values()):
            child.destroy()
        self._image_refs.clear()
        self._last_image_paths = []

    def _collect_result_images(self, since_time: float) -> list[str]:
        if not self._workdir:
            return []
        exts = {".png", ".jpg", ".jpeg", ".bmp"}
        found: dict[str, float] = {}

        # One walk of the working directory: os.walk already recurses into the
        # 'results' subfolder, so adding it as a second root would report every
        # image twice.
        try:
            for dirpath, dirnames, filenames in os.walk(self._workdir):
                dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                for name in filenames:
                    if os.path.splitext(name)[1].lower() not in exts:
                        continue
                    full = os.path.abspath(os.path.join(dirpath, name))
                    try:
                        mtime = os.path.getmtime(full)
                    except OSError:
                        continue
                    if mtime >= since_time - 1.0:  # small slack
                        found[full] = mtime
        except Exception:
            pass

        return sorted(found, key=found.__getitem__)

    @staticmethod
    def _load_opaque(path: str) -> Image.Image:
        """Open an image, flattening any transparency onto a white background."""
        img = Image.open(path)
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            bg.paste(img, (0, 0), img)
            return bg.convert("RGB")
        if img.mode not in ("RGB", "L"):
            return img.convert("RGB")
        return img

    def _append_image_card(self, path: str) -> None:
        """
        Append a single image card to the results area (used for live 'SAVED:' lines).
        """
        if self.results_frame is None:
            return
        try:
            img = self._load_opaque(path)

            max_width = 1500
            if img.width > max_width:
                scale = max_width / float(img.width)
                img = img.resize((int(img.width * scale), int(img.height * scale)),
                                 Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            self._image_refs.append(photo)
            self._last_image_paths.append(path)

            item = tk.Frame(self.results_frame, padx=4, pady=4, bg="white")
            item.pack(fill=tk.X, anchor="w")

            top_row = tk.Frame(item, bg="white")
            top_row.pack(fill=tk.X, pady=(4, 2))

            caption_text = os.path.relpath(path, self._workdir or os.getcwd())
            tk.Label(top_row, text=caption_text, anchor="w", bg="white").pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Button(top_row, text="Save PNG",
                      command=lambda p=path: self._save_single_image_png(p)).pack(side=tk.RIGHT)

            lbl = tk.Label(item, image=photo, bg="white")
            lbl.pack(anchor="w")

        except Exception as e:
            err = tk.Label(self.results_frame, text=f"Failed to load image: {path} ({e})", fg="#7D1E1E", anchor="w")
            err.pack(fill=tk.X, pady=4)

    def _display_images(self, image_paths: list[str]) -> None:
        """
        Display plot images in the results area with per-image Save buttons.
        """
        if self.results_frame is None:
            return

        # The SAVED: lines usually render everything live; only redraw when the
        # post-run sweep turned up something those lines did not announce.
        already = {os.path.abspath(p) for p in self._last_image_paths}
        if already and all(os.path.abspath(p) in already for p in image_paths):
            return

        # Replace content with the final set discovered after completion
        self._clear_results()

        if not image_paths:
            lbl = tk.Label(self.results_frame, text="No images were produced.", anchor="w")
            lbl.pack(fill=tk.X, pady=4)
            return

        self._last_image_paths = list(image_paths)
        for path in image_paths:
            self._append_image_card(path)

    # Saving functions
    @staticmethod
    def _default_png_name(src_path: str) -> str:
        base, _ = os.path.splitext(os.path.basename(src_path))
        return f"{base}.png"

    def _save_single_image_png(self, src_path: str) -> None:
        """
        Save a single displayed image to PNG. Prompts for location.
        """
        try:
            # Ask where to save
            initialfile = self._default_png_name(src_path)
            target = filedialog.asksaveasfilename(
                title="Save image as PNG",
                defaultextension=".png",
                filetypes=[("PNG image", "*.png")],
                initialfile=initialfile,
            )
            if not target:
                return

            self._load_opaque(src_path).save(target, format="PNG")
            messagebox.showinfo("Saved", f"Saved as:\n{target}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save image:\n{e}")

    def _save_all_images_png(self) -> None:
        """
        Save all currently displayed images as PNG into a chosen folder.
        """
        if not self._last_image_paths:
            messagebox.showinfo("No Images", "There are no images to save.")
            return

        folder = filedialog.askdirectory(title="Choose folder to save all images as PNG")
        if not folder:
            return

        saved = 0
        errors: list[str] = []
        for src_path in self._last_image_paths:
            try:
                target = os.path.join(folder, self._default_png_name(src_path))
                self._load_opaque(src_path).save(target, format="PNG")
                saved += 1
            except Exception as e:
                errors.append(f"{os.path.basename(src_path)}: {e}")

        if errors:
            messagebox.showwarning(
                "Save Completed with Errors",
                f"Saved {saved} image(s).\nFailed {len(errors)}:\n"
                + "\n".join(errors[:10])
                + ("..." if len(errors) > 10 else "")
            )
        else:
            messagebox.showinfo("Save Completed", f"Saved {saved} image(s) to:\n{folder}")
