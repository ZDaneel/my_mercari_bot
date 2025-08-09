import requests
from abc import ABC, abstractmethod
import configparser


class Notifier(ABC):
    @abstractmethod
    def send(self, title: str, message: str, details: dict = None):
        """
        发送通知的通用方法。
        details 参数可以包含如 link, image_url 等额外信息。
        """
        pass


class ConsoleNotifier(Notifier):
    def send(self, title: str, message: str, details: dict = None):
        print("\n" + "=" * 30)
        print(f"📬 [{title}]")
        print(message)
        if details and details.get("link"):
            print(f"   🔗 链接: {details['link']}")
        print("=" * 30)


def notifier_factory(config: configparser.ConfigParser) -> Notifier:
    try:
        notifier_type = config.get("notifier", "type", fallback="console").lower()
        print(f"...根据配置，正在初始化 '{notifier_type}' 通知器...")

        if notifier_type == "console":
            return ConsoleNotifier()
        else:
            print(f"⚠️ 警告: 未知的通知器类型 '{notifier_type}'，将默认使用控制台通知。")
            return ConsoleNotifier()

    except Exception as e:
        print(f"❌ 初始化通知器时发生错误: {e}。将回退到控制台通知。")
        return ConsoleNotifier()
