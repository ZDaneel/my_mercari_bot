import requests
from abc import ABC, abstractmethod
import configparser
from pathlib import Path
import webbrowser
from typing import Optional
import threading 
import time
import sys
import os
import platform
import traceback

# 导入日志模块
try:
    from ..utils.logger import get_logger
    logger = get_logger('notifier')
except ImportError:
    # 如果无法导入日志模块，创建一个简单的日志函数
    def get_logger(name):
        class SimpleLogger:
            def info(self, msg): print(f"[INFO] {msg}")
            def warning(self, msg): print(f"[WARNING] {msg}")
            def error(self, msg): print(f"[ERROR] {msg}")
            def debug(self, msg): print(f"[DEBUG] {msg}")
        return SimpleLogger()
    logger = get_logger('notifier')

try:
    from win11toast import toast
    WIN11TOAST_AVAILABLE = True
    logger.info("✅ win11toast 库可用")
except ImportError as e:
    WIN11TOAST_AVAILABLE = False
    logger.error(f"❌ win11toast 库导入失败: {e}")


class Notifier(ABC):
    @abstractmethod
    def send(self, title: str, message: str, details: dict = None, timestamp=None, time_type=None):
        """
        发送通知的通用方法。
        details 参数可以包含如 link, image_url 等额外信息。
        timestamp 参数用于显示时间信息。
        time_type 参数用于标识时间类型（上架/更新/发现）。
        """
        pass

def notifier_factory(config: configparser.ConfigParser, link_type: str = "mercari", log_queue=None) -> Notifier:
    try:
        # 详细记录配置信息
        logger.info("🔍 开始初始化通知器...")
        logger.info(f"📋 配置对象类型: {type(config)}")
        logger.info(f"📋 配置节: {list(config.sections()) if hasattr(config, 'sections') else '无法获取节'}")
        
        if hasattr(config, 'sections') and 'notifier' in config.sections():
            logger.info(f"📋 notifier节内容: {dict(config['notifier'])}")
        else:
            logger.warning("⚠️ 配置中没有notifier节")
        
        notifier_type = config.get("notifier", "type", fallback="console").lower()
        logger.info(f"🔧 根据配置，正在初始化 '{notifier_type}' 通知器...")

        # 记录环境信息
        logger.info(f"💻 操作系统: {platform.system()} {platform.release()}")
        logger.info(f"🐍 Python版本: {sys.version}")
        logger.info(f"📁 当前工作目录: {os.getcwd()}")
        logger.info(f"🔧 是否打包环境: {getattr(sys, 'frozen', False)}")
        if getattr(sys, 'frozen', False):
            logger.info(f"📦 可执行文件路径: {sys.executable}")

        if notifier_type == "console":
            logger.info("📝 使用控制台通知器")
            return ConsoleNotifier(link_type, log_queue)
        elif notifier_type == "windows":
            logger.info("🪟 使用Windows通知器")
            return WindowsNotifier(link_type)
        else:
            logger.warning(f"⚠️ 未知的通知器类型 '{notifier_type}'，将默认使用控制台通知。")
            return ConsoleNotifier(link_type, log_queue)

    except Exception as e:
        logger.error(f"❌ 初始化通知器时发生错误: {e}")
        logger.error(f"📋 错误详情: {traceback.format_exc()}")
        logger.info("🔄 将回退到控制台通知。")
        return ConsoleNotifier(link_type, log_queue)


class ConsoleNotifier(Notifier):
    def __init__(self, link_type="mercari", log_queue=None):
        self.link_type = link_type
        self.log_queue = log_queue
        logger.info(f"📝 控制台通知器初始化完成，链接类型: {link_type}")
    
    def _generate_link(self, item_id: str) -> str:
        if self.link_type == "letaoyifan":
            return f"https://letaoyifan.com/goods_detail/MERCARI/{item_id}"
        else:
            return f"https://jp.mercari.com/item/{item_id}"
    
    def send(self, title: str, message: str, details: dict = None, timestamp=None, time_type=None):
        from datetime import datetime
        
        # 处理时间戳
        if timestamp is None:
            current_time = datetime.now()
        else:
            current_time = timestamp
            
        time_str = current_time.strftime("%H:%M:%S")
        
        # 构建通知消息 - 更简洁的格式
        notification_lines = []
        
        # 计算相对时间
        now = datetime.now()
        time_diff = now - current_time
        seconds_ago = int(time_diff.total_seconds())
        
        if seconds_ago < 60:
            time_ago = f"{seconds_ago}秒前"
        elif seconds_ago < 3600:
            minutes_ago = seconds_ago // 60
            time_ago = f"{minutes_ago}分钟前"
        else:
            hours_ago = seconds_ago // 3600
            time_ago = f"{hours_ago}小时前"
        
        # 构建时间显示
        if time_type and "前" in time_type:
            # time_type已经包含了时间信息（如"上架21天前 更新2分钟前"）
            time_display = time_type
        elif time_type:
            # time_type只是类型标识（如"上架"、"更新"、"发现"）
            time_display = f"{time_type} {time_ago}"
        else:
            time_display = time_ago
            
        # 优化显示格式
        notification_lines.append(f"🔍 {title}")
        notification_lines.append(f"⏰ {time_display}")
        notification_lines.append(f"📝 {message}")
        
        if details and details.get("id"):
            link = self._generate_link(details.get("id"))
            notification_lines.append(f"🔗 {link}")
        
        notification_lines.append("─" * 40)
        
        # 如果有日志队列，发送到GUI日志区域
        if self.log_queue:
            for line in notification_lines:
                self.log_queue.put(line)
        else:
            # 否则输出到控制台（开发环境）
            for line in notification_lines:
                print(line)
            print()  # 额外空行


class WindowsNotifier(Notifier):
    def __init__(self, link_type="mercari"):
        self.link_type = link_type
        logger.info(f"🪟 Windows通知器初始化开始，链接类型: {link_type}")
        
        # 检查环境
        self._check_environment()
        
        # 创建一个用于缓存图片的目录
        try:
            if getattr(sys, 'frozen', False):
                # 打包环境
                self.image_cache_dir = Path(sys.executable).parent / "data" / "image_cache"
            else:
                # 开发环境
                self.image_cache_dir = Path(__file__).resolve().parent.parent.parent / "data" / "image_cache"
            
            self.image_cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 图片缓存目录: {self.image_cache_dir}")
        except Exception as e:
            logger.error(f"❌ 创建图片缓存目录失败: {e}")
            logger.error(f"📋 错误详情: {traceback.format_exc()}")
            self.image_cache_dir = None

    def _check_environment(self):
        """检查运行环境"""
        logger.info("🔍 检查Windows通知环境...")
        
        # 检查操作系统
        if platform.system() != "Windows":
            logger.warning(f"⚠️ 当前操作系统不是Windows: {platform.system()}")
        
        # 检查win11toast库
        if not WIN11TOAST_AVAILABLE:
            logger.error("❌ win11toast库不可用")
            logger.info("💡 建议运行: pip install win11toast")
        else:
            logger.info("✅ win11toast库可用")
            
            # 测试toast功能
            try:
                # 尝试导入toast函数
                from win11toast import toast
                logger.info("✅ toast函数导入成功")
            except Exception as e:
                logger.error(f"❌ toast函数导入失败: {e}")
        
        # 检查Windows版本
        try:
            win_ver = platform.win32_ver()
            logger.info(f"🪟 Windows版本: {win_ver}")
        except:
            logger.warning("⚠️ 无法获取Windows版本信息")

    def _generate_link(self, item_id: str) -> str:
        if self.link_type == "letaoyifan":
            return f"https://letaoyifan.com/goods_detail/MERCARI/{item_id}"
        else:
            return f"https://jp.mercari.com/item/{item_id}"

    def _cache_image(self, image_url: str) -> Optional[str]:
        if not image_url:
            logger.debug("📷 无图片URL，跳过缓存")
            return None
            
        if not self.image_cache_dir:
            logger.warning("⚠️ 图片缓存目录不可用，跳过图片缓存")
            return None
            
        try:
            logger.info(f"📷 开始缓存图片: {image_url}")
            
            # 用图片URL的最后一部分作为文件名
            file_name = image_url.split('/')[-1].split('?')[0]
            local_path = self.image_cache_dir / file_name

            # 如果文件已存在，则不重复下载
            if local_path.exists():
                logger.info(f"📷 图片已缓存: {local_path}")
                return str(local_path)
            
            logger.info(f"📥 下载图片到: {local_path}")
            response = requests.get(image_url, stream=True, timeout=10)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)
            
            logger.info(f"✅ 图片缓存成功: {local_path}")
            return str(local_path)
            
        except Exception as e:
            logger.error(f"❌ 缓存图片失败: {e}")
            logger.error(f"📋 错误详情: {traceback.format_exc()}")
            return None
    
    def _send_toast_in_thread(self, title, message, image_payload, click_action):
        """在线程中发送toast通知"""
        try:
            logger.info(f"🔄 在后台线程中发送Windows通知: {title}")
            
            # 记录通知参数
            logger.debug(f"📋 通知参数:")
            logger.debug(f"   - 标题: {title}")
            logger.debug(f"   - 消息: {message}")
            logger.debug(f"   - 图片: {image_payload}")
            logger.debug(f"   - 点击动作: {click_action}")
            
            # 发送通知
            toast(
                title,
                message,
                image=image_payload,
                on_click=click_action,
                app_id="Mercari Monitor"
            )
            
            logger.info(f"✅ Windows通知发送成功: {title}")
            
        except Exception as e:
            logger.error(f"❌ (线程)发送Windows通知失败: {e}")
            logger.error(f"📋 错误详情: {traceback.format_exc()}")

    def send(self, title: str, message: str, details: dict = None, timestamp=None, time_type=None):
        logger.info(f"📬 开始发送Windows通知: {title}")
        
        if not WIN11TOAST_AVAILABLE:
            logger.warning("⚠️ win11toast不可用，降级到控制台通知")
            ConsoleNotifier(self.link_type).send(title, message, details, timestamp, time_type)
            return

        try:
            logger.info(f"🔍 通知详情: {details}")
            
            # 计算相对时间
            from datetime import datetime
            if timestamp is None:
                current_time = datetime.now()
            else:
                current_time = timestamp
                
            now = datetime.now()
            time_diff = now - current_time
            seconds_ago = int(time_diff.total_seconds())
            
            if seconds_ago < 60:
                time_ago = f"{seconds_ago}秒前"
            elif seconds_ago < 3600:
                minutes_ago = seconds_ago // 60
                time_ago = f"{minutes_ago}分钟前"
            else:
                hours_ago = seconds_ago // 3600
                time_ago = f"{hours_ago}小时前"
            
            # 构建带时间的标题
            if time_type and "前" in time_type:
                # time_type已经包含了时间信息（如"上架21天前 更新2分钟前"）
                time_display = time_type
            elif time_type:
                # time_type只是类型标识（如"上架"、"更新"、"发现"）
                time_display = f"{time_type} {time_ago}"
            else:
                time_display = time_ago
            title_with_time = f"{title} | {time_display}"
            
            # 提取通知数据
            image_url = details.get('image_url') if details else None
            item_id = details.get("id") if details else None
            link_url = self._generate_link(item_id) if item_id else None
            
            logger.info(f"🔗 生成链接: {link_url}")
            logger.info(f"📷 图片URL: {image_url}")

            # 1. 缓存图片
            local_image_path = self._cache_image(image_url)

            # 2. 构建图片参数
            image_payload = {}
            if local_image_path:
                image_payload = {
                    'src': local_image_path,
                    'placement': 'inline'
                }
                logger.info(f"📷 使用本地图片: {local_image_path}")

            # 3. 定义点击事件
            click_action = link_url
            logger.info(f"🔗 点击动作: {click_action}")

            # 4. 创建并启动一个新线程来发送通知
            logger.info("🔄 创建通知线程...")
            thread = threading.Thread(
                target=self._send_toast_in_thread,
                args=(title_with_time, message, image_payload, click_action),
                daemon=True  # 设置为守护线程
            )
            
            logger.info("▶️ 启动通知线程...")
            thread.start()
            
            logger.info(f"✔️ Windows通知已派发: {title}")
            
            # 等待一小段时间确保线程启动
            time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"❌ Windows通知发送失败: {e}")
            logger.error(f"📋 错误详情: {traceback.format_exc()}")
            
            # 降级到控制台通知
            logger.info("🔄 降级到控制台通知")
            ConsoleNotifier(self.link_type).send(title, message, details, timestamp, time_type) 
