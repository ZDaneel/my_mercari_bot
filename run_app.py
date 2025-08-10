# run_app.py
import tkinter as tk
from src.gui import App # 从 src 目录导入我们的 App 类

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()