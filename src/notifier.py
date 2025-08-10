import requests
from abc import ABC, abstractmethod
import configparser
from pathlib import Path
import webbrowser
from typing import Optional
import threading 
import time

try:
    from win11toast import toast
    WIN11TOAST_AVAILABLE = True
except ImportError:
    WIN11TOAST_AVAILABLE = False


class Notifier(ABC):
    @abstractmethod
    def send(self, title: str, message: str, details: dict = None):
        """
        发送通知的通用方法。
        details 参数可以包含如 link, image_url 等额外信息。
        """
        pass

def notifier_factory(config: configparser.ConfigParser) -> Notifier:
    try:
        notifier_type = config.get("notifier", "type", fallback="console").lower()
        print(f"...根据配置，正在初始化 '{notifier_type}' 通知器...")

        if notifier_type == "console":
            return ConsoleNotifier()
        elif notifier_type == "windows":
            return WindowsNotifier()
        else:
            print(f"⚠️ 警告: 未知的通知器类型 '{notifier_type}'，将默认使用控制台通知。")
            return ConsoleNotifier()

    except Exception as e:
        print(f"❌ 初始化通知器时发生错误: {e}。将回退到控制台通知。")
        return ConsoleNotifier()


class ConsoleNotifier(Notifier):
    def send(self, title: str, message: str, details: dict = None):
        print("\n" + "=" * 30)
        print(f"📬 [{title}]")
        print(message)
        link = "https://jp.mercari.com/item/" + details.get("id")
        print(f"   🔗 链接: {link}")
        print("=" * 30)

class WindowsNotifier(Notifier):
    def __init__(self):
        if not WIN11TOAST_AVAILABLE:
            print("⚠️ 警告: 'win11toast' 库未安装或当前非Windows环境，Windows通知将不可用。")
        print("WindowsNotifier init")
        # 创建一个用于缓存图片的目录
        self.image_cache_dir = Path(__file__).resolve().parent.parent / "data" / "image_cache"
        self.image_cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_image(self, image_url: str) -> Optional[str]:
        if not image_url:
            return None
        try:
            # 用图片URL的最后一部分作为文件名
            file_name = image_url.split('/')[-1].split('?')[0]
            local_path = self.image_cache_dir / file_name

            # 如果文件已存在，则不重复下载
            if local_path.exists():
                return str(local_path)
            
            response = requests.get(image_url, stream=True, timeout=10)
            response.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)
            
            return str(local_path)
        except Exception as e:
            print(f"❌ 缓存图片失败: {e}")
            return None
    
    def _send_toast_in_thread(self, title, message, image_payload, click_action):
        try:
            toast(
                title,
                message,
                image=image_payload,
                on_click=click_action,
                app_id="Mercari Monitor"
            )
        except Exception as e:
            # 在线程中打印错误，避免主程序崩溃
            print(f"❌ (线程)发送 Windows 通知失败: {e}")

    def send(self, title: str, message: str, details: dict = None):
        if not WIN11TOAST_AVAILABLE:
            # 如果库不可用，可以降级为打印到控制台
            print(" fallback to console")
            ConsoleNotifier().send(title, message, details)
            return

        print(details)
        image_url = details.get('image_url') if details else None
        link_url = "https://jp.mercari.com/item/" + details.get("id")

        # 1. 缓存图片
        local_image_path = self._cache_image(image_url)

        # 2. 构建图片参数
        image_payload = {}
        if local_image_path:
            image_payload = {
                'src': local_image_path,
                'placement': 'inline'
            }

        # 3. 定义点击事件
        # win11toast 的 on_click 可以是一个 URL 字符串，也可以是一个回调函数
        click_action = link_url

        # 2. 创建并启动一个新线程来发送通知
        thread = threading.Thread(
            target=self._send_toast_in_thread,
            args=(title, message, image_payload, click_action)
        )
        thread.start() # 立即启动，主程序不会在此等待
        
        print(f"✔️ Windows 通知已派发: {title}")
        # (可选) 在连续发送多个通知之间加入一个极短的延迟，防止系统过载
        time.sleep(0.1) 
