import time
import json
import sqlite3
import configparser
from pathlib import Path

import database
from token_manager import load_credentials, save_credentials
from token_gen import get_new_tokens
from mercari_api import fetch_mercari_items, InvalidTokenError
from notifier import notifier_factory


def init_database():
    conn = database.get_connection()
    database.setup_database(conn)
    return conn


def load_config():
    ROOT_DIR = Path(__file__).resolve().parent.parent
    config_file_path = ROOT_DIR / "config.ini"

    config = configparser.ConfigParser()
    config.read(config_file_path)

    return config


def main():
    config = load_config()
    check_interval = config.getint("settings", "check_interval_seconds", fallback=60)
    page_size = config.getint("settings", "page_size", fallback=20)
    keywords_to_monitor = list(config["keywords"].values())
    notifier = notifier_factory(config)

    db_conn = init_database()
    database.sync_keywords(db_conn, keywords_to_monitor)

    credentials = load_credentials()
    if not credentials:
        print("首次运行或凭据文件无效，开始获取新凭据...")
        dpop, laplace = get_new_tokens()
        if not (dpop and laplace):
            print("❌ 无法获取初始凭据，程序退出。")
            return
        credentials = {"dpop_token": dpop, "laplace_uuid": laplace}
        save_credentials(dpop, laplace)

    while True:
        print("\n--- 开始新一轮检查 ---")
        keywords_data = database.get_active_keywords_with_ids(db_conn)
        if not keywords_data:
            print("🚨 没有活跃的关键词，程序退出。")
            return

        for kid, name in keywords_data:
            print(f"🔍 开始监控关键词: {name}")
            try:
                items_data = fetch_mercari_items(
                    keyword=name,
                    dpop_token=credentials["dpop_token"],
                    laplace_uuid=credentials["laplace_uuid"],
                    page_size=page_size,
                )

                if items_data and "items" in items_data:
                    cleaned_list = []
                    for item in items_data["items"]:
                        cleaned_list.append(
                            {
                                "id": item["id"],
                                "name": item["name"],
                                "price": int(item["price"]),
                                "image_url": (
                                    item["thumbnails"][0]
                                    if item.get("thumbnails")
                                    else None
                                ),
                            }
                        )
                    processed_results = database.process_items_batch(
                        db_conn, cleaned_list, kid
                    )
                    # 发送“新上架”通知
                    for new_item in processed_results.get("new", []):
                        notifier.send(
                            title=f"🔍 关键词: {name}",
                            message=f"发现新商品: {new_item['name']} - {new_item['price']}円",
                            details=new_item,
                        )
                    # 发送“降价”通知
                    for dropped_item in processed_results.get("price_drop", []):
                        drop_message = (
                            f"降价: {dropped_item['name']} - {dropped_item.get('old_price', '')} → {dropped_item['price']}円"
                        )
                        notifier.send(
                            title=f"🔻 关键词: {name}",
                            message=drop_message,
                            details=dropped_item,
                        )
                    # 发送“状态变化”通知
                    for status_change in processed_results.get("status_changes", []):
                        status_message = (
                            f"状态变化: {status_change['name']} - {status_change.get('old_status', '')} → {status_change['new_status']}"
                        )
                        notifier.send(
                            title=f"🔄 关键词: {name}",
                            message=status_message,
                            details=status_change,
                        )

            except InvalidTokenError:
                print("🚨 检测到令牌已失效！开始执行刷新流程...")
                dpop, laplace = get_new_tokens()

                if dpop and laplace:
                    print("✨ 成功获取到新令牌，更新并保存。")
                    credentials = {"dpop_token": dpop, "laplace_uuid": laplace}
                    save_credentials(dpop, laplace)
                else:
                    print("❌ 刷新令牌失败，将在下次循环中再次尝试。")

            except Exception as e:
                print(f"An unexpected error occurred: {e}")

        print(f"--- 本轮检查结束，休眠 {check_interval} 秒 ---")
        time.sleep(check_interval)


if __name__ == "__main__":
    main()
