#!/usr/bin/env python3
"""
Mercari Bot GUI Application
GUI应用的主入口文件
"""

import tkinter as tk
from PIL import Image
from pystray import Icon as icon, Menu as menu, MenuItem as item
from src.gui.gui import App
import threading
import sys
from pathlib import Path

def create_gui():
    """创建并运行GUI"""
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

def main():
    """主函数"""
    # 在后台线程中创建并运行GUI
    gui_thread = threading.Thread(target=create_gui, daemon=True)
    gui_thread.start()

    # 获取图标路径
    if getattr(sys, 'frozen', False):
        base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).resolve().parent.parent.parent
    
    icon_path = base_path / "icon.png"

    # --- 创建系统托盘图标 ---
    try:
        image = Image.open(icon_path)
    except FileNotFoundError:
        print(f"警告: 找不到图标文件 {icon_path}")
        return

    def show_window(icon, item):
        """显示窗口"""
        print("显示窗口的逻辑需要更复杂的实现，暂时忽略")

    def exit_action(icon, item):
        """退出应用"""
        print("正在退出...")
        icon.stop()

    menu = menu(
        item('显示/隐藏', show_window, default=True),
        item('退出', exit_action)
    )
    
    tray_icon = icon("MercariMonitor", image, "Mercari 监控器", menu)
    
    print("托盘图标已创建，程序在后台运行。")
    tray_icon.run()

if __name__ == "__main__":
    main()
