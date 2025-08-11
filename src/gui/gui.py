import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, scrolledtext
import threading
import queue
import json
from pathlib import Path
from ..core.monitor import MercariMonitor
from ..utils.notifier import notifier_factory
from ..utils.logger import setup_logging, get_log_manager, get_logger
import sys

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Mercari 监控器")
        self.root.geometry("800x900")

        self.monitor: MercariMonitor | None = None
        self.is_running = False
        self.last_config = None  # 用于跟踪配置变化

        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(__file__).resolve().parent.parent.parent
        self.settings_path = base_path / "data" / "settings.json"
        self.settings_path.parent.mkdir(exist_ok=True)

        # 初始化日志系统
        self.log_manager = setup_logging("MercariBot")
        self.logger = get_logger("gui")
        self.log_queue = self.log_manager.get_queue()
        
        # 记录启动信息
        self.log_manager.log_startup()

        self._create_widgets()
        self.load_settings()
        
        self.root.after(100, self.poll_log_queue)

    def _create_widgets(self):
        """创建所有GUI控件"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 关键词管理区 ---
        kw_frame = ttk.LabelFrame(main_frame, text="关键词管理", padding="10")
        kw_frame.pack(fill=tk.X, pady=5)

        self.keywords_list = tk.Listbox(kw_frame, height=8)
        self.keywords_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        kw_actions_frame = ttk.Frame(kw_frame)
        kw_actions_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        self.keyword_entry = ttk.Entry(kw_actions_frame, width=30)
        self.keyword_entry.pack(fill=tk.X)
        self.keyword_entry.bind("<Return>", lambda event: self.add_keyword())

        add_button = ttk.Button(kw_actions_frame, text="添加关键词", command=self.add_keyword)
        add_button.pack(fill=tk.X, pady=5)

        remove_button = ttk.Button(kw_actions_frame, text="删除选中", command=self.remove_keyword)
        remove_button.pack(fill=tk.X)

         # --- (新增) 监控设置区 ---
        settings_frame = ttk.LabelFrame(main_frame, text="监控设置", padding="10")
        settings_frame.pack(fill=tk.X, pady=5)
        
        # 使用 grid 布局来对齐标签和输入框
        settings_frame.columnconfigure(1, weight=1)
        
        ttk.Label(settings_frame, text="最小间隔 (秒):").grid(row=0, column=0, sticky="w", pady=2)
        self.min_interval_entry = ttk.Entry(settings_frame)
        self.min_interval_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.min_interval_entry.bind("<FocusOut>", lambda e: self.save_settings())

        ttk.Label(settings_frame, text="最大间隔 (秒):").grid(row=1, column=0, sticky="w", pady=2)
        self.max_interval_entry = ttk.Entry(settings_frame)
        self.max_interval_entry.grid(row=1, column=1, sticky="ew", padx=5)
        self.max_interval_entry.bind("<FocusOut>", lambda e: self.save_settings())
        
        ttk.Label(settings_frame, text="查询数量 (Page Size):").grid(row=2, column=0, sticky="w", pady=2)
        self.page_size_entry = ttk.Entry(settings_frame)
        self.page_size_entry.grid(row=2, column=1, sticky="ew", padx=5)
        self.page_size_entry.bind("<FocusOut>", lambda e: self.save_settings())

        ttk.Label(settings_frame, text="链接跳转:").grid(row=3, column=0, sticky="w", pady=2)
        self.link_type_var = tk.StringVar(value="mercari")
        link_frame = ttk.Frame(settings_frame)
        link_frame.grid(row=3, column=1, sticky="ew", padx=5)
        
        ttk.Radiobutton(link_frame, text="煤炉", variable=self.link_type_var, value="mercari", command=self.save_settings).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(link_frame, text="乐一番", variable=self.link_type_var, value="letaoyifan", command=self.save_settings).pack(side=tk.LEFT)

        ttk.Label(settings_frame, text="通知类型:").grid(row=4, column=0, sticky="w", pady=2)
        self.notifier_type_var = tk.StringVar(value="windows")
        notifier_frame = ttk.Frame(settings_frame)
        notifier_frame.grid(row=4, column=1, sticky="ew", padx=5)
        
        ttk.Radiobutton(notifier_frame, text="Windows通知", variable=self.notifier_type_var, value="windows", command=self.save_settings).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(notifier_frame, text="控制台输出", variable=self.notifier_type_var, value="console", command=self.save_settings).pack(side=tk.LEFT)

        # 添加凭据过期时间设置
        ttk.Label(settings_frame, text="凭据过期时间 (秒):").grid(row=5, column=0, sticky="w", pady=2)
        self.credential_expiry_entry = ttk.Entry(settings_frame)
        self.credential_expiry_entry.grid(row=5, column=1, sticky="ew", padx=5)
        self.credential_expiry_entry.bind("<FocusOut>", lambda e: self.save_settings())
        
        # 添加说明文字
        expiry_help_frame = ttk.Frame(settings_frame)
        expiry_help_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        help_text = "说明：凭据过期时间是指API访问的有效期，每次自动刷新需要数十秒，刷新后相当于使用新设备访问。如果访问间隔较短可以适当调小，减小风险，但没法排除ip被封的风险（"
        help_label = ttk.Label(expiry_help_frame, text=help_text, wraplength=600, foreground="gray")
        help_label.pack(anchor="w")

        # --- 控制区 ---
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)

        self.toggle_button = ttk.Button(control_frame, text="▶ 启动监控", command=self.toggle_monitor, width=20)
        self.toggle_button.pack(side=tk.LEFT, padx=(0, 10))

        self.status_label = ttk.Label(control_frame, text="状态: 已停止", font=("", 10, "bold"))
        self.status_label.pack(side=tk.LEFT)

        # --- 日志区 ---
        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def load_settings(self) -> dict:
        """从 settings.json 加载所有配置并更新GUI，然后返回配置字典"""
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # 如果文件不存在或为空，使用默认值
            settings = {}

        # --- 加载关键词 ---
        self.keywords_list.delete(0, tk.END)
        for kw in settings.get('keywords', []):
            self.keywords_list.insert(tk.END, kw)
            
        # --- 加载其他设置到输入框 ---
        # 使用 .get() 提供默认值，防止配置文件不完整
        self.min_interval_entry.delete(0, tk.END)
        self.min_interval_entry.insert(0, settings.get('min_interval', 60))
        
        self.max_interval_entry.delete(0, tk.END)
        self.max_interval_entry.insert(0, settings.get('max_interval', 90))
        
        self.page_size_entry.delete(0, tk.END)
        self.page_size_entry.insert(0, settings.get('page_size', 20))
        
        # 加载链接类型设置
        self.link_type_var.set(settings.get('link_type', 'mercari'))
        
        # 加载通知器类型设置
        self.notifier_type_var.set(settings.get('notifier_type', 'console'))
        
        # 加载凭据过期时间设置
        self.credential_expiry_entry.delete(0, tk.END)
        self.credential_expiry_entry.insert(0, settings.get('credential_expiry', 1800))
        
        # (关键) 返回完整的配置字典，使用GUI中的实际关键词列表
        return {
            'keywords': list(self.keywords_list.get(0, tk.END)),  # 使用GUI中的实际关键词列表
            'min_interval': int(self.min_interval_entry.get()),
            'max_interval': int(self.max_interval_entry.get()),
            'page_size': int(self.page_size_entry.get()),
            'link_type': self.link_type_var.get(),
            'notifier_type': self.notifier_type_var.get(),
            'credential_expiry': int(self.credential_expiry_entry.get())
        }

    def save_settings(self):
        """从GUI控件读取当前值并保存到 settings.json"""
        try:
            settings = {
                'keywords': list(self.keywords_list.get(0, tk.END)),
                'min_interval': int(self.min_interval_entry.get()),
                'max_interval': int(self.max_interval_entry.get()),
                'page_size': int(self.page_size_entry.get()),
                'link_type': self.link_type_var.get(),
                'notifier_type': self.notifier_type_var.get(),
                'credential_expiry': int(self.credential_expiry_entry.get())
            }
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            self.logger.info(f"⚙️ 配置已保存。link_type: {settings['link_type']}, notifier_type: {settings['notifier_type']}")
        except ValueError:
            # 如果用户在输入框里输入了非数字，int()会失败
            messagebox.showerror("错误", "间隔时间和查询数量必须是有效的数字！")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")


    def add_keyword(self):
        kw = self.keyword_entry.get().strip()
        if kw and kw not in self.keywords_list.get(0, tk.END):
            self.keywords_list.insert(tk.END, kw)
            self.keyword_entry.delete(0, tk.END)
            self.save_settings()
            self.logger.info(f"✅ 已添加关键词: {kw}")
    
    def remove_keyword(self):
        selected_indices = self.keywords_list.curselection()
        if not selected_indices: return
        # 从后往前删，避免索引错乱
        removed_keywords = []
        for i in reversed(selected_indices):
            removed_keywords.append(self.keywords_list.get(i))
            self.keywords_list.delete(i)
        
        # 获取删除后的关键词列表
        remaining_keywords = list(self.keywords_list.get(0, tk.END))
        self.logger.info(f"🗑️ 删除关键词: {', '.join(removed_keywords)}")
        self.logger.info(f"📝 剩余关键词: {remaining_keywords}")
        
        self.save_settings()
        if removed_keywords:
            self.logger.info(f"🗑️ 已删除关键词: {', '.join(removed_keywords)}")

    def toggle_monitor(self):
        if self.is_running:
            # --- 停止监控 ---
            if self.monitor: 
                self.monitor.stop()
                # 等待监控线程完全停止
                if self.monitor.monitor_thread and self.monitor.monitor_thread.is_alive():
                    self.monitor.monitor_thread.join(timeout=3)
            self.monitor = None
            self.is_running = False
            self.toggle_button.config(text="▶ 启动监控")
            self.status_label.config(text="状态: 已停止")
        else:
            # --- 启动监控 ---
            # 获取当前配置
            current_config = self.get_current_config()
            if not current_config['keywords']:
                messagebox.showwarning("提示", "请先添加至少一个关键词。")
                return
            
            self.save_settings()
            
            # 确保没有其他监控实例在运行
            if self.monitor:
                self.monitor.stop()
                if self.monitor.monitor_thread and self.monitor.monitor_thread.is_alive():
                    self.monitor.monitor_thread.join(timeout=3)
            
            # 创建通知器实例
            notifier = self.create_notifier()
            
            # 创建新的 monitor 实例
            self.monitor = MercariMonitor(
                current_config['keywords'],
                current_config['page_size'], 
                current_config['min_interval'], 
                current_config['max_interval'],
                current_config['link_type'],
                notifier=notifier,
                log_queue=self.log_queue,
                credential_expiry=current_config['credential_expiry']
            ) 
            self.monitor.run_in_thread() # 在后台线程中运行
            
            # 初始化配置跟踪
            self.last_config = self.get_current_config()
            
            self.is_running = True
            self.toggle_button.config(text="■ 停止监控")
            self.status_label.config(text="状态: 运行中...")

    def poll_log_queue(self):
        while True:
            try:
                record = self.log_queue.get(block=False)
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, record + '\n')
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
            except queue.Empty:
                break
        
        # 检查配置变化并热更新（降低频率，避免过于频繁的检查）
        if self.is_running and self.monitor:
            self.check_and_update_config()
            
        self.root.after(500, self.poll_log_queue)  # 改为500ms检查一次

    def check_and_update_config(self):
        """检查配置变化并热更新监控器"""
        current_config = self.get_current_config()
        
        if self.last_config != current_config:
            try:
                # 添加详细的调试信息
                self.logger.info(f"🔄 检测到配置变化:")
                self.logger.info(f"   旧配置: {self.last_config}")
                self.logger.info(f"   新配置: {current_config}")
                
                # 创建新的通知器实例
                new_notifier = self.create_notifier()
                
                self.monitor.update_config(
                    current_config['keywords'],
                    current_config['page_size'],
                    current_config['min_interval'],
                    current_config['max_interval'],
                    current_config['link_type'],
                    notifier=new_notifier,
                    credential_expiry=current_config['credential_expiry']
                )
                self.last_config = current_config
                self.logger.info("🔄 配置更新请求已发送")
            except Exception as e:
                self.logger.error(f"发送配置更新失败: {e}")

    def create_notifier(self):
        """创建通知器实例"""
        import configparser
        config = configparser.ConfigParser()
        config.add_section('notifier')
        config.set('notifier', 'type', self.notifier_type_var.get())
        
        return notifier_factory(config, self.link_type_var.get(), self.log_queue)

    def get_current_config(self):
        """获取当前GUI配置"""
        return {
            'keywords': list(self.keywords_list.get(0, tk.END)),
            'min_interval': int(self.min_interval_entry.get()),
            'max_interval': int(self.max_interval_entry.get()),
            'page_size': int(self.page_size_entry.get()),
            'link_type': self.link_type_var.get(),
            'notifier_type': self.notifier_type_var.get(),
            'credential_expiry': int(self.credential_expiry_entry.get())
        }

    def on_closing(self):   
        if self.is_running:
            if messagebox.askyesno("确认", "监控正在运行中，关闭窗口将停止监控并退出程序，确定吗？"):
                if self.monitor: self.monitor.stop()
                # 记录关闭信息
                self.log_manager.log_shutdown()
                self.root.destroy()
        else:
            # 记录关闭信息
            self.log_manager.log_shutdown()
            self.root.destroy()

