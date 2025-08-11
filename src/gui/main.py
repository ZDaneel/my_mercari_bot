import tkinter as tk
from PIL import Image
from pystray import Icon as icon, Menu as menu, MenuItem as item
from src.gui.gui import App
import threading

def create_gui():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing) # 拦截关闭事件
    root.mainloop()

if __name__ == "__main__":
    # 在后台线程中创建并运行GUI
    gui_thread = threading.Thread(target=create_gui, daemon=True)
    gui_thread.start()

    # --- 创建系统托盘图标 ---
    image = Image.open("icon.png") # 确保项目根目录有 icon.png

    def show_window(icon, item):
        # 这里需要一种方法来访问GUI的root窗口并调用 deiconify()
        # 这通常通过全局变量或更复杂的类通信来完成
        # 为了简单起见，我们重启GUI（这是一个简化的策略）
        # 一个更健壮的实现会涉及线程间的通信
        print("显示窗口的逻辑需要更复杂的实现，暂时忽略")

    def exit_action(icon, item):
        print("正在退出...")
        # 这里需要安全地停止 monitor 线程
        # app.stop_monitor() # 需要访问app实例
        icon.stop()
        # root.quit() # 需要访问root实例

    menu = menu(
        item('显示/隐藏', show_window, default=True),
        item('退出', exit_action)
    )
    
    tray_icon = icon("MercariMonitor", image, "Mercari 监控器", menu)
    
    print("托盘图标已创建，程序在后台运行。")
    tray_icon.run()