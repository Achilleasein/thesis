# file: code/python_implementation/GUI/execution_display.py
import threading
import queue
import tkinter as tk
from tkinter import scrolledtext

class ExecutionDisplay:
    def __init__(self, parent: tk.Tk | tk.Toplevel, title: str = "Execution Log") -> None:
        self.parent = parent
        self.tl = tk.Toplevel(parent)
        self.tl.title(title)
        self.tl.geometry("800x300")
        self.tl.transient(parent)

        self.text = scrolledtext.ScrolledText(self.tl, state=tk.NORMAL, wrap=tk.WORD)
        self.text.pack(fill=tk.BOTH, expand=True)

        # Configure tags for styling
        self.text.tag_configure("stdout", foreground="#154360")
        self.text.tag_configure("stderr", foreground="#7D1E1E")
        self.text.tag_configure("status", foreground="#555555")

        # Internal
        self._queue: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self._after_id: str | None = None
        self._reader_threads: list[threading.Thread] = []
        self._attached_proc = None

        # Ensure child closes when parent closes
        self.tl.protocol("WM_DELETE_WINDOW", self._on_close)

    def clear(self) -> None:
        self.text.delete("1.0", tk.END)

    def _on_close(self) -> None:
        # Only close the window; process lifecycle is handled by the controller
        try:
            self._stop_readers()
        finally:
            self.tl.destroy()

    def _stop_readers(self) -> None:
        # Reader threads will naturally exit once streams close; nothing special to stop
        if self._after_id is not None:
            try:
                self.tl.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _enqueue_line(self, line: str, tag: str) -> None:
        self._queue.put((line, tag))

    def _reader(self, fp, tag: str) -> None:
        try:
            for line in iter(fp.readline, ""):
                self._enqueue_line(line, tag)
        except Exception as e:
            self._enqueue_line(f"[reader error: {e}]\n", "stderr")

    def _drain_queue(self) -> None:
        try:
            while True:
                line, tag = self._queue.get_nowait()
                self.text.insert(tk.END, line, tag)
                self.text.see(tk.END)
        except queue.Empty:
            pass
        finally:
            if self.tl.winfo_exists():
                self._after_id = self.tl.after(50, self._drain_queue)

    def attach_process(self, proc) -> None:
        """
        Attach a subprocess.Popen-like object that has stdout/stderr as text streams.
        """
        self._attached_proc = proc
        self.clear()
        self.text.insert(tk.END, "Process started...\n", "status")
        self.text.see(tk.END)

        # Start reader threads for stdout and stderr
        self._reader_threads = []
        if getattr(proc, "stdout", None) is not None:
            t_out = threading.Thread(target=self._reader, args=(proc.stdout, "stdout"), daemon=True)
            self._reader_threads.append(t_out)
            t_out.start()
        if getattr(proc, "stderr", None) is not None:
            t_err = threading.Thread(target=self._reader, args=(proc.stderr, "stderr"), daemon=True)
            self._reader_threads.append(t_err)
            t_err.start()

        # Start UI queue pump
        self._drain_queue()

        # Also watch for process completion to append status
        def wait_and_mark():
            try:
                code = proc.wait()
                self._enqueue_line(f"\n[process exited with code {code}]\n", "status")
            except Exception as e:
                self._enqueue_line(f"\n[process wait error: {e}]\n", "stderr")

        threading.Thread(target=wait_and_mark, daemon=True).start()