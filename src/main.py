import time
import sqlite3
import configparser
from pathlib import Path
import random
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import sys

import database
from token_manager import load_credentials, save_credentials
from token_gen import get_new_tokens
from mercari_api import fetch_mercari_items, InvalidTokenError
from notifier import notifier_factory

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mercari_bot.log", encoding="utf-8"),
    ],
)
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("webdriver_manager").setLevel(logging.WARNING)
logging.getLogger("seleniumwire").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

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

    def __init__(self):
        self.config = self._load_config()
        self.notifier = notifier_factory(self._load_configparser())
        self.db_conn = self._init_database()
        self.credentials: Optional[Dict] = None

    def _load_configparser(self) -> configparser.ConfigParser:
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
        database.sync_keywords(conn, self.config.keywords)
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
                page_size=self.config.page_size,
            )

            if not items_data or "items" not in items_data:
                logger.warning(f"关键词 '{keyword_name}' 未获取到数据")
                return True

            # 清理数据
            cleaned_items = self._clean_items_data(items_data["items"])

            # 处理数据并获取变化
            processed_results = database.process_items_batch(
                self.db_conn, cleaned_items, keyword_id
            )

            # 发送通知
            self._send_notifications(keyword_name, processed_results)

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
                    }
                )
            except (KeyError, ValueError) as e:
                logger.warning(f"跳过无效商品数据: {e}")
                continue

        return cleaned_list

    def _send_notifications(self, keyword_name: str, processed_results: Dict):
        """发送通知"""
        # 新商品通知
        for new_item in processed_results.get("new", []):
            self.notifier.send(
                title=f"🔍 关键词: {keyword_name}",
                message=f"发现新商品: {new_item['name']} - {new_item['price']}円",
                details=new_item,
            )

        # 降价通知
        for dropped_item in processed_results.get("price_drop", []):
            drop_message = f"降价: {dropped_item['name']} - {dropped_item.get('old_price', '')} → {dropped_item['price']}円"
            self.notifier.send(
                title=f"🔻 关键词: {keyword_name}",
                message=drop_message,
                details=dropped_item,
            )

        # 状态变化通知
        for status_change in processed_results.get("status_changes", []):
            status_message = f"状态变化: {status_change['name']} - {status_change.get('old_status', '')} → {status_change['new_status']}"
            self.notifier.send(
                title=f"🔄 关键词: {keyword_name}",
                message=status_message,
                details=status_change,
            )

    def _get_check_interval(self, force_refresh: bool = False) -> int:
        """获取检查间隔时间"""
        if force_refresh:
            return 1
        return random.randint(self.config.min_interval, self.config.max_interval)

    def run(self):
        """运行监控器"""
        logger.info("🚀 Mercari监控器启动")

        while True:
            try:
                logger.info("--- 开始新一轮检查 ---")

                # 检查凭据
                if not self._load_or_refresh_credentials():
                    logger.error("❌ 无法获取凭据，程序退出")
                    break

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
                time.sleep(check_interval)

            except KeyboardInterrupt:
                logger.info("收到中断信号，正在退出...")
                break
            except Exception as e:
                logger.error(f"主循环发生未预期错误: {e}")
                time.sleep(10)  # 错误后等待10秒再继续

        # 清理资源
        if self.db_conn:
            self.db_conn.close()
        logger.info("👋 Mercari监控器已退出")


def main():
    """主函数"""
    monitor = MercariMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
