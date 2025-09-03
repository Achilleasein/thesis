import os
import re
import time
import threading
import queue
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
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

        # Pattern to detect "SAVED: /path/to/image.png" lines from the process output
        self._saved_line_re = re.compile(r"^\s*SAVED:\s*(?P<path>.+\.(?:png|jpg|jpeg|bmp))\s*$", re.IGNORECASE)

    def build_ui(self) -> None:
        self.root.title("Rhythm Detector - File Selector")
        self.root.geometry("1600x1200")
        self.root.minsize(600, 400)

        # Top controls bar
        self.controls_frame = tk.Frame(self.root, padx=10, pady=10)
        self.controls_frame.pack(fill=tk.X)

        # Left: primary actions
        btns_frame = tk.Frame(self.controls_frame)
        btns_frame.pack(side=tk.LEFT)

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
        try:
            while True:
                text, tag = self._log_queue.get_nowait()
                self._append_log(text, tag)
        except queue.Empty:
            pass
        finally:
            if self.root.winfo_exists():
                self._log_after_id = self.root.after(50, self._drain_log_queue)

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
        if getattr(proc, "stdout", None) is not None:
            threading.Thread(target=self._reader_loop, args=(proc.stdout, "stdout"), daemon=True).start()
        if getattr(proc, "stderr", None) is not None:
            threading.Thread(target=self._reader_loop, args=(proc.stderr, "stderr"), daemon=True).start()

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
    def run_detection_clicked(self) -> None:
        if not self.track1_path or not self.track2_path:
            messagebox.showerror("Selection Error", "Please select both Track 1 and Track 2 before running the detection.")
            return
        try:
            # Clear previous log and results
            if self.log_text is not None:
                self.log_text.delete("1.0", tk.END)
                self._append_log("Process started...\n", "status")
            self._clear_results()

            # Record start time and working directory
            self._run_start_time = time.time()
            # Same workdir as the detection script runs in (parent folder of GUI)
            self._workdir = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

            # Launch process
            proc = run_rythm_detection([self.track1_path, self.track2_path])
            self.detection_proc = proc

            # Hook up streaming
            self._start_stream_readers(proc)
            if self.status_var:
                self.status_var.set("Started rythm_detection.py...")
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

    def on_close(self) -> None:
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
        found: list[tuple[float, str]] = []

        # Search the working directory and an optional 'results' subfolder
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

        found.sort(key=lambda t: t[0])
        return [p for _, p in found]

    def _append_image_card(self, path: str) -> None:
        """
        Append a single image card to the results area (used for live 'SAVED:' lines).
        """
        if self.results_frame is None:
            return
        try:
            img = Image.open(path)
            # Handle transparency
            if img.mode in ("RGBA", "LA"):
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                bg.paste(img, (0, 0), img)
                img = bg.convert("RGB")
            elif img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            max_width = 1500
            if img.width > max_width:
                scale = max_width / float(img.width)
                img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            self._image_refs.append(photo)
            self._last_image_paths.append(path)

            item = tk.Frame(self.results_frame, padx=4, pady=4, bg="white")
            item.pack(fill=tk.X, anchor="w")

            top_row = tk.Frame(item, bg="white")
            top_row.pack(fill=tk.X, pady=(4, 2))

            caption_text = os.path.relpath(path, self._workdir or os.getcwd())
            tk.Label(top_row, text=caption_text, anchor="w", bg="white").pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Button(top_row, text="Save PNG", command=lambda p=path: self._save_single_image_png(p)).pack(side=tk.RIGHT)

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
    def _default_png_name(self, src_path: str) -> str:
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

            # Load and convert as needed (handle transparency like in display)
            img = Image.open(src_path)
            if img.mode in ("RGBA", "LA"):
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                bg.paste(img, (0, 0), img)
                img = bg.convert("RGB")
            elif img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Save as PNG
            img.save(target, format="PNG")
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
                img = Image.open(src_path)
                if img.mode in ("RGBA", "LA"):
                    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                    bg.paste(img, (0, 0), img)
                    img = bg.convert("RGB")
                elif img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                target = os.path.join(folder, self._default_png_name(src_path))
                img.save(target, format="PNG")
                saved += 1
            except Exception as e:
                errors.append(f"{os.path.basename(src_path)}: {e}")

        if errors:
            messagebox.showwarning(
                "Save Completed with Errors",
                f"Saved {saved} image(s).\nFailed {len(errors)}:\n" + "\n".join(errors[:10]) + ("..." if len(errors) > 10 else "")
            )
        else:
            messagebox.showinfo("Save Completed", f"Saved {saved} image(s) to:\n{folder}")