# code/python_implementation/GUI/file_picker.py
import os
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Iterable, Tuple

def open_file_picker(
    parent: tk.Tk | tk.Toplevel,
    initial_dir: str,
    audio_extensions: Iterable[str],
    on_confirm: Callable[[list[str], str], None],
    title: str = "Select Files",
    size: Tuple[int, int] = (700, 500),
) -> None:
    """
    Open a modal file picker dialog with:
    - Directory navigation
    - 'Up Directory' button
    - Multi-select for files filtered by audio_extensions

    Parameters:
        parent: Parent window
        initial_dir: Starting directory
        audio_extensions: Iterable of extensions (e.g., (".mp3", ".wav"))
        on_confirm: Callback called with (selected_files, chosen_dir)
        title: Dialog title
        size: Width, Height tuple
    """
    audio_exts = tuple(e.lower() for e in audio_extensions)
    current = {"path": initial_dir if os.path.isdir(initial_dir) else os.getcwd()}

    def set_dir(new_dir: str):
        try:
            current["path"] = new_dir
            path_var.set(current["path"])
            refresh_list()
        except Exception as e:
            messagebox.showerror("Error", f"Cannot access directory:\n{e}", parent=tl)

    def go_up():
        parent_dir = os.path.dirname(current["path"])
        if parent_dir and os.path.isdir(parent_dir):
            set_dir(parent_dir)

    def refresh_list():
        listbox_dirs.delete(0, tk.END)
        listbox_files.delete(0, tk.END)
        try:
            entries = sorted(os.listdir(current["path"]), key=str.lower)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot list directory:\n{e}", parent=tl)
            return
        # Directories first
        for name in entries:
            full = os.path.join(current["path"], name)
            if os.path.isdir(full):
                listbox_dirs.insert(tk.END, name)
        # Then files matching filter
        for name in entries:
            full = os.path.join(current["path"], name)
            if os.path.isfile(full) and name.lower().endswith(audio_exts):
                listbox_files.insert(tk.END, name)

    def enter_dir(event=None):
        sel = listbox_dirs.curselection()
        if not sel:
            return
        name = listbox_dirs.get(sel[0])
        set_dir(os.path.join(current["path"], name))

    def confirm_selection():
        files_idx = listbox_files.curselection()
        if not files_idx:
            messagebox.showinfo("No Selection", "Please select one or more audio files.", parent=tl)
            return
        selected = []
        base = current["path"]
        for idx in files_idx:
            fname = listbox_files.get(idx)
            selected.append(os.path.join(base, fname))
        on_confirm(selected, current["path"])
        tl.destroy()

    def cancel():
        tl.destroy()

    tl = tk.Toplevel(parent)
    tl.title(title)
    tl.geometry(f"{size[0]}x{size[1]}")
    tl.transient(parent)
    tl.grab_set()

    # Top bar
    top_bar = tk.Frame(tl, padx=8, pady=8)
    top_bar.pack(fill=tk.X)

    path_var = tk.StringVar(value=current["path"])
    path_entry = tk.Entry(top_bar, textvariable=path_var)
    path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

    up_btn = tk.Button(top_bar, text="Up Directory ⬆", command=go_up)
    up_btn.pack(side=tk.LEFT)

    # Body split
    body = tk.Frame(tl, padx=8, pady=8)
    body.pack(fill=tk.BOTH, expand=True)

    # Directories
    dir_frame = tk.LabelFrame(body, text="Directories")
    dir_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

    dir_scroll = tk.Scrollbar(dir_frame, orient=tk.VERTICAL)
    listbox_dirs = tk.Listbox(dir_frame, yscrollcommand=dir_scroll.set)
    dir_scroll.config(command=listbox_dirs.yview)
    dir_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    listbox_dirs.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    listbox_dirs.bind("<Double-Button-1>", enter_dir)

    # Files
    file_frame = tk.LabelFrame(body, text="Audio Files")
    file_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))

    file_scroll = tk.Scrollbar(file_frame, orient=tk.VERTICAL)
    listbox_files = tk.Listbox(file_frame, selectmode=tk.EXTENDED, yscrollcommand=file_scroll.set)
    file_scroll.config(command=listbox_files.yview)
    file_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    listbox_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Actions
    actions = tk.Frame(tl, padx=8, pady=8)
    actions.pack(fill=tk.X)

    ok_btn = tk.Button(actions, text="Select", command=confirm_selection)
    ok_btn.pack(side=tk.RIGHT)

    cancel_btn = tk.Button(actions, text="Cancel", command=cancel)
    cancel_btn.pack(side=tk.RIGHT, padx=(0, 8))

    refresh_list()
    tl.wait_window(tl)