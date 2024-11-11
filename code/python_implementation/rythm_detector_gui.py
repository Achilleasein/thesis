import tkinter as tk
from tkinter import filedialog, messagebox

# Initialize main application window
root = tk.Tk()
root.title("MP3 File Selector")
root.geometry("1080x920")

# Initialize file paths
file1_path = tk.StringVar()
file2_path = tk.StringVar()

# Function to select MP3 files
def select_file1():
    file_path = filedialog.askopenfilename(filetypes=[("MP3 files", "*.mp3")])
    file1_path.set(file_path)

def select_file2():
    file_path = filedialog.askopenfilename(filetypes=[("MP3 files", "*.mp3")])
    file2_path.set(file_path)

# Function to execute code on the selected files
def process_files():
    file1 = file1_path.get()
    file2 = file2_path.get()
    if not file1 or not file2:
        messagebox.showwarning("Warning", "Please select both MP3 files!")
        return
    
    # Place your processing code here
    # Example: Print file paths to the console
    print("Processing files:")
    print("File 1:", file1)
    print("File 2:", file2)
    
    # Placeholder for further processing code
    messagebox.showinfo("Info", "Processing completed!")

# Create GUI elements
tk.Label(root, text="Select MP3 File 1:").pack(pady=5)
tk.Entry(root, textvariable=file1_path, width=50).pack(pady=5)
tk.Button(root, text="Browse", command=select_file1).pack(pady=5)

tk.Label(root, text="Select MP3 File 2:").pack(pady=5)
tk.Entry(root, textvariable=file2_path, width=50).pack(pady=5)
tk.Button(root, text="Browse", command=select_file2).pack(pady=5)

tk.Button(root, text="Process Files", command=process_files).pack(pady=20)

root.mainloop()
