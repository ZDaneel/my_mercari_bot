import threading
import time
import sqlite3
import configparser
from pathlib import Path
import random
from typing import Dict, List, Optional
from dataclasses import dataclass
import sys
import queue
from datetime import datetime

from . import database
from .token_manager import load_credentials, save_credentials
from .token_gen import get_new_tokens
from .mercari_api import fetch_mercari_items, InvalidTokenError
from .notifier import notifier_factory
from .logger import get_logger

logger = get_logger("monitor")

# 常量定义
MAX_CREDENTIAL_AGE_SECONDS = 1800
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5


@dataclass
class AppConfig:
    """应用配置数据类"""

    min_interval: int
    max_interval: int
    page_size: int
    keywords: List[str]


class MercariMonitor:
    """Mercari监控器主类"""

    def __init__(self, keywords: list, page_size: int, min_interval: int, max_interval: int, link_type: str = "mercari", notifier=None, log_queue=None):
        # 它不再需要 self.config，直接将配置存为实例属性
        self.keywords = keywords.copy()  # 使用copy避免外部修改影响
        self.page_size = page_size
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.link_type = link_type
        self.log_queue = log_queue

        # 如果传入了notifier实例就使用，否则创建新的
        if notifier is not None:
            self.notifier = notifier
        else:
            config_parser = self._load_configparser_for_notifier_only()
            self.notifier = notifier_factory(config_parser, link_type, log_queue)
        self.credentials: Optional[Dict] = None
        self.stop_event = threading.Event()  # 停止事件标志
        self.monitor_thread = None  # 用于存放监控线程
        self.db_conn = None  # 数据库连接
        self.config_queue = queue.Queue()  # 配置更新队列

    def _load_configparser_for_notifier_only(self) -> configparser.ConfigParser:
        """加载配置文件"""
        root_dir = ""
        # 判断程序是否被打包
        if getattr(sys, 'frozen', False):
            # 如果是打包后的 .exe 文件，根目录是 .exe 文件所在的目录
            root_dir = Path(sys.executable).parent
        else:
            # 如果是正常运行的 .py 脚本，根目录是 src 的上一级
            root_dir = Path(__file__).resolve().parent.parent
        config_file_path = root_dir / "config.ini"

        config = configparser.ConfigParser()
        config.read(config_file_path, encoding="utf-8")
        return config

    def _load_config(self) -> AppConfig:
        """加载应用配置"""
        config = self._load_configparser()

        return AppConfig(
            min_interval=config.getint("settings", "min_interval_seconds", fallback=30),
            max_interval=config.getint("settings", "max_interval_seconds", fallback=60),
            page_size=config.getint("settings", "page_size", fallback=20),
            keywords=list(config["keywords"].values()),
        )

    def _init_database(self) -> sqlite3.Connection:
        """初始化数据库"""
        conn = database.get_connection()
        database.setup_database(conn)
        database.sync_keywords(conn, self.keywords)
        return conn

    def _load_or_refresh_credentials(self, force_refresh: bool = False) -> bool:
        """加载或刷新凭据"""
        if not force_refresh:
            self.credentials = load_credentials()
            if not self.credentials:
                logger.info("首次运行或凭据文件无效，开始获取新凭据...")
                return self._refresh_credentials()

        if self.credentials:
            saved_last_update = self.credentials.get("last_update", 0)
            age = time.time() - saved_last_update
            if age > MAX_CREDENTIAL_AGE_SECONDS:
                logger.warning(f"凭据已过期，开始获取新凭据... ({age:.0f}秒)")
                return self._refresh_credentials()

        return True

    def _refresh_credentials(self) -> bool:
        """刷新凭据"""
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                dpop, laplace = get_new_tokens()
                if dpop and laplace:
                    self.credentials = {
                        "dpop_token": dpop,
                        "laplace_uuid": laplace,
                        "last_update": int(time.time()),
                    }
                    save_credentials(dpop, laplace)
                    logger.info("✅ 成功获取新凭据")
                    return True
                else:
                    logger.error(
                        f"❌ 无法获取凭据，尝试 {attempt + 1}/{MAX_RETRY_ATTEMPTS}"
                    )
            except Exception as e:
                logger.error(f"获取凭据时发生错误: {e}")

            if attempt < MAX_RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SECONDS)

        return False

    def _process_keyword(self, keyword_id: int, keyword_name: str) -> bool:
        """处理单个关键词的监控"""
        logger.info(f"🔍 开始监控关键词: {keyword_name}")
        start_time = time.perf_counter()

        try:
            items_data = fetch_mercari_items(
                keyword=keyword_name,
                dpop_token=self.credentials["dpop_token"],
                laplace_uuid=self.credentials["laplace_uuid"],
                page_size=self.page_size,
            )

            if not items_data or "items" not in items_data:
                logger.warning(f"关键词 '{keyword_name}' 未获取到数据")
                return True

            # 清理数据
            cleaned_items = self._clean_items_data(items_data["items"])
            logger.info(f"📊 获取到 {len(cleaned_items)} 个商品")

            # 处理数据并获取变化
            processed_results = database.process_items_batch(
                self.db_conn, cleaned_items, keyword_id
            )

            # 记录处理结果
            new_count = len(processed_results.get("new", []))
            price_drop_count = len(processed_results.get("price_drop", []))
            status_change_count = len(processed_results.get("status_changes", []))
            
            if new_count > 0 or price_drop_count > 0 or status_change_count > 0:
                logger.info(f"📈 处理结果 - 新商品: {new_count}, 降价: {price_drop_count}, 状态变化: {status_change_count}")
                # 发送通知
                self._send_notifications(keyword_name, processed_results)
            else:
                logger.info(f"📊 关键词 '{keyword_name}' 无变化")

            return True

        except InvalidTokenError:
            logger.error("🚨 检测到令牌已失效！开始执行刷新流程...")
            return self._refresh_credentials()

        except Exception as e:
            logger.error(f"处理关键词 '{keyword_name}' 时发生错误: {e}")
            return True

        finally:
            end_time = time.perf_counter()
            duration = end_time - start_time
            logger.info(f"关键词 '{keyword_name}' 处理耗时: {duration:.2f} 秒")

    def _clean_items_data(self, items: List[Dict]) -> List[Dict]:
        """清理商品数据"""
        cleaned_list = []
        for item in items:
            try:
                cleaned_list.append(
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "price": int(item["price"]),
                        "image_url": (
                            item["thumbnails"][0] if item.get("thumbnails") else None
                        ),
                        "status": item.get("status", "unknown"),
                        "created": item.get("created"),  # 商品创建时间
                        "updated": item.get("updated"),  # 商品更新时间
                    }
                )
            except (KeyError, ValueError) as e:
                logger.warning(f"跳过无效商品数据: {e}")
                continue

        return cleaned_list

    def _send_notifications(self, keyword_name: str, processed_results: Dict):
        """发送通知"""
        current_time = datetime.now()
        
        # 新商品通知
        for new_item in processed_results.get("new", []):
            try:
                price = int(new_item.get('price', 0))
            except (ValueError, TypeError):
                price = 0
            # 比较created和updated时间，决定显示哪个
            created_time = new_item.get('created')
            updated_time = new_item.get('updated')
            
            if created_time and updated_time and int(created_time) != int(updated_time):
                # 有更新，同时显示上架和更新时间
                created_dt = datetime.fromtimestamp(int(created_time))
                updated_dt = datetime.fromtimestamp(int(updated_time))
                time_type = f"📅 {self._get_time_ago(created_dt)} • 🔄 {self._get_time_ago(updated_dt)}"
                item_time = updated_dt  # 使用更新时间作为主要时间
            elif created_time:
                # 无更新，使用created时间
                item_time = datetime.fromtimestamp(int(created_time))
                time_type = f"📅 {self._get_time_ago(item_time)}"
            else:
                # 无时间信息，使用当前时间
                item_time = current_time
                time_type = "🔍 发现"
                
            self.notifier.send(
                title=f"{keyword_name} ¥{price:,}",
                message=f"{new_item['name']}",
                details=new_item,
                timestamp=item_time,
                time_type=time_type,
            )

        # 降价通知
        for dropped_item in processed_results.get("price_drop", []):
            try:
                old_price = int(dropped_item.get('old_price', 0))
                current_price = int(dropped_item.get('price', 0))
            except (ValueError, TypeError):
                old_price = 0
                current_price = 0
            # 降价商品时间处理
            updated_time = dropped_item.get('updated')
            created_time = dropped_item.get('created')
            
            if created_time and updated_time and int(created_time) != int(updated_time):
                # 有更新，同时显示上架和更新时间
                created_dt = datetime.fromtimestamp(int(created_time))
                updated_dt = datetime.fromtimestamp(int(updated_time))
                time_type = f"📅 {self._get_time_ago(created_dt)} • 🔄 {self._get_time_ago(updated_dt)}"
                item_time = updated_dt  # 使用更新时间作为主要时间
            elif created_time:
                # 无更新，使用created时间
                item_time = datetime.fromtimestamp(int(created_time))
                time_type = f"📅 {self._get_time_ago(item_time)}"
            else:
                # 无时间信息，使用当前时间
                item_time = current_time
                time_type = "🔍 发现"
                
            self.notifier.send(
                title=f"{keyword_name} ¥{current_price:,}",
                message=f"{dropped_item['name']} (¥{old_price:,} → ¥{current_price:,})",
                details=dropped_item,
                timestamp=item_time,
                time_type=time_type,
            )

        # 状态变化通知
        for status_change in processed_results.get("status_changes", []):
            try:
                price = int(status_change.get('price', 0))
            except (ValueError, TypeError):
                price = 0
            old_status = status_change.get('old_status', '未知')
            new_status = status_change.get('new_status', '未知')
            # 状态变化商品时间处理
            updated_time = status_change.get('updated')
            created_time = status_change.get('created')
            
            if created_time and updated_time and int(created_time) != int(updated_time):
                # 有更新，同时显示上架和更新时间
                created_dt = datetime.fromtimestamp(int(created_time))
                updated_dt = datetime.fromtimestamp(int(updated_time))
                time_type = f"📅 {self._get_time_ago(created_dt)} • 🔄 {self._get_time_ago(updated_dt)}"
                item_time = updated_dt  # 使用更新时间作为主要时间
            elif created_time:
                # 无更新，使用created时间
                item_time = datetime.fromtimestamp(int(created_time))
                time_type = f"📅 {self._get_time_ago(item_time)}"
            else:
                # 无时间信息，使用当前时间
                item_time = current_time
                time_type = "🔍 发现"
                
            self.notifier.send(
                title=f"{keyword_name} ¥{price:,}",
                message=f"{status_change['name']} ({old_status} → {new_status})",
                details=status_change,
                timestamp=item_time,
                time_type=time_type,
            )

    def _get_time_ago(self, dt: datetime) -> str:
        """计算相对时间字符串"""
        now = datetime.now()
        diff = now - dt
        
        if diff.total_seconds() < 60:
            return f"{int(diff.total_seconds())}秒前"
        elif diff.total_seconds() < 3600:
            return f"{int(diff.total_seconds() // 60)}分钟前"
        elif diff.total_seconds() < 86400:
            return f"{int(diff.total_seconds() // 3600)}小时前"
        else:
            return f"{int(diff.total_seconds() // 86400)}天前"

    def _get_check_interval(self, force_refresh: bool = False) -> int:
        """获取检查间隔时间"""
        if force_refresh:
            return 1
        return random.randint(self.min_interval, self.max_interval)

    def run_in_thread(self):
        """在一个新线程中启动监控循环"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("监控已经在运行中，先停止现有监控...")
            self.stop()
            # 等待线程完全停止
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=3)
        
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self.run, daemon=True)
        self.monitor_thread.start()
        logger.info("🚀 Mercari 监控线程已启动")

    def update_config(self, keywords: list, page_size: int, min_interval: int, max_interval: int, link_type: str, notifier=None):
        """热更新监控器配置"""
        # 将配置更新放入队列，由监控线程处理
        config_update = {
            'keywords': keywords.copy(),
            'page_size': page_size,
            'min_interval': min_interval,
            'max_interval': max_interval,
            'link_type': link_type,
            'notifier': notifier
        }
        try:
            self.config_queue.put(config_update, block=False)
            logger.info(f"🔄 配置更新已排队: {keywords}")
        except queue.Full:
            logger.warning("配置更新队列已满，跳过此次更新")

    def stop(self):
        """设置停止标志，请求监控线程退出"""
        if not self.monitor_thread or not self.monitor_thread.is_alive():
            logger.warning("监控未在运行。")
            return
            
        logger.info("🛑 正在请求停止监控线程...")
        self.stop_event.set()
        # 等待线程结束，但设置超时避免无限等待
        try:
            self.monitor_thread.join(timeout=5)
            if self.monitor_thread.is_alive():
                logger.warning("监控线程未能在5秒内停止")
            else:
                logger.info("✅ 监控线程已成功停止")
        except Exception as e:
            logger.error(f"停止监控线程时发生错误: {e}")

    def run(self):
        """运行监控器"""
        logger.info("🚀 Mercari监控器启动")
        
        # 在监控线程中创建数据库连接
        self.db_conn = self._init_database()

        while not self.stop_event.is_set():
            try:
                logger.info("--- 开始新一轮检查 ---")

                # 检查配置更新队列
                try:
                    while not self.config_queue.empty():
                        config_update = self.config_queue.get_nowait()
                        self.keywords = config_update['keywords']
                        self.page_size = config_update['page_size']
                        self.min_interval = config_update['min_interval']
                        self.max_interval = config_update['max_interval']
                        self.link_type = config_update['link_type']
                        
                        # 如果传入了新的notifier就使用，否则重新创建
                        if config_update.get('notifier') is not None:
                            self.notifier = config_update['notifier']
                        else:
                            # 重新创建notifier以使用新的link_type
                            old_link_type = getattr(self.notifier, 'link_type', 'unknown')
                            config_parser = self._load_configparser_for_notifier_only()
                            self.notifier = notifier_factory(config_parser, self.link_type, self.log_queue)
                            
                        logger.info(f"⚙️ 配置已更新 - 关键词: {self.keywords}, 链接类型: {self.link_type}")
                except queue.Empty:
                    pass

                # 检查凭据
                if not self._load_or_refresh_credentials():
                    logger.error("❌ 无法获取凭据，程序退出")
                    break

                # 同步当前关键词到数据库
                logger.info(f"📝 开始同步关键词到数据库: {self.keywords}")
                database.sync_keywords(self.db_conn, self.keywords)
                logger.info(f"📝 关键词同步完成")

                # 获取活跃关键词
                keywords_data = database.get_active_keywords_with_ids(self.db_conn)
                if not keywords_data:
                    logger.error("🚨 没有活跃的关键词，程序退出")
                    break

                # 处理每个关键词
                for keyword_id, keyword_name in keywords_data:
                    success = self._process_keyword(keyword_id, keyword_name)
                    if not success:
                        logger.error(f"处理关键词 '{keyword_name}' 失败，跳过")
                        continue

                # 计算下次检查间隔
                check_interval = self._get_check_interval()
                logger.info(f"--- 本轮检查结束，休眠 {check_interval} 秒 ---")
                
                # 使用更短的睡眠间隔来检查停止标志
                for _ in range(check_interval):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)

            except KeyboardInterrupt:
                logger.info("收到中断信号，正在退出...")
                break
            except Exception as e:
                logger.error(f"主循环发生未预期错误: {e}")
                # 错误后等待10秒再继续，但也要检查停止标志
                for _ in range(10):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)

        # 清理资源
        if self.db_conn:
            self.db_conn.close()
        logger.info("👋 Mercari监控器已退出")


def main():
    """主函数"""
    # 从配置文件加载默认设置
    config = AppConfig(
        min_interval=30,
        max_interval=60,
        page_size=10,
        keywords=[]
    )
    monitor = MercariMonitor(
        keywords=config.keywords,
        page_size=config.page_size,
        min_interval=config.min_interval,
        max_interval=config.max_interval,
        link_type="mercari"  # 默认使用煤炉链接
    )
    monitor.run()


if __name__ == "__main__":
    main()