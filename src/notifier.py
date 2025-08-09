from abc import ABC, abstractmethod

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
        print("="*30)
        print(f"【{title}】")
        print(message)
        if details:
            for key, value in details.items():
                print(f"- {key.capitalize()}: {value}")
        print("="*30)