import sqlite3
from pathlib import Path
import time
from data_processor import translate_text

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_FILE = ROOT_DIR / "data" / "mercari_monitor.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


def setup_database(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS keywords (
        id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, is_active BOOLEAN DEFAULT 1
    )"""
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS items (
        item_mercari_id TEXT PRIMARY KEY,
        keyword_id INTEGER,
        name TEXT,
        name_cn TEXT,
        price INTEGER,
        image_url TEXT,
        first_seen_timestamp INTEGER,
        last_seen_timestamp INTEGER,
        status TEXT,
        FOREIGN KEY (keyword_id) REFERENCES keywords (id)
    )"""
    )
    conn.commit()


def sync_keywords(conn, config_keywords: list):
    cursor = conn.cursor()
    cursor.execute("UPDATE keywords SET is_active = 0")
    for keyword in config_keywords:
        cursor.execute("INSERT OR IGNORE INTO keywords (name) VALUES (?)", (keyword,))
        cursor.execute("UPDATE keywords SET is_active = 1 WHERE name = ?", (keyword,))
    conn.commit()


def get_active_keywords_with_ids(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM keywords WHERE is_active = 1")
    return cursor.fetchall()


def process_items_batch(conn, items_list: list, keyword_id: int):
    cursor = conn.cursor()
    new_items = []
    price_drops = []
    status_changes = []

    for item in items_list:
        mercari_id = item["id"]
        price_value = item.get("price")
        current_status = item.get("status")

        if isinstance(price_value, (int, float)):
            current_price = int(price_value)
        else:
            price_str = str(price_value)
            digits = "".join(ch for ch in price_str if ch.isdigit())
            if not digits:
                # 跳过无法解析价格的条目
                continue
            current_price = int(digits)

        cursor.execute(
            "SELECT price, name_cn, status FROM items WHERE item_mercari_id = ?",
            (mercari_id,),
        )
        result = cursor.fetchone()

        if result is None:
            translated_name = translate_text(item["name"])
            item["status"] = current_status
            item["name_cn"] = translated_name
            new_items.append(item)
            cursor.execute(
                """INSERT INTO items (item_mercari_id, keyword_id, name, name_cn, price, image_url, first_seen_timestamp, last_seen_timestamp, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    mercari_id,
                    keyword_id,
                    item["name"],
                    item["name_cn"],
                    current_price,
                    item["image_url"],
                    int(time.time()),
                    int(time.time()),
                    "ON_SALE",
                ),
            )
        else:
            stored_price, stored_name_cn, stored_status = result
            needs_update = False
            if current_price < stored_price:
                item["old_price"] = f"¥{stored_price}"
                item["name_cn"] = stored_name_cn or item["name"]
                price_drops.append(item)
                cursor.execute(
                    "UPDATE items SET price = ?, last_seen_timestamp = ? WHERE item_mercari_id = ?",
                    (current_price, int(time.time()), mercari_id),
                )
                needs_update = True
            if stored_status != current_status:
                item["old_status"] = stored_status
                item["new_status"] = current_status
                item["name_cn"] = stored_name_cn or item["name"]
                status_changes.append(item)
                # 更新状态
                cursor.execute(
                    "UPDATE items SET status = ? WHERE item_mercari_id = ?",
                    (current_status, mercari_id),
                )
                needs_update = True
            if needs_update:
                cursor.execute(
                    "UPDATE items SET last_seen_timestamp = ? WHERE item_mercari_id = ?",
                    (int(time.time()), mercari_id),
                )
            else:
                cursor.execute(
                    "UPDATE items SET last_seen_timestamp = ? WHERE item_mercari_id = ?",
                    (int(time.time()), mercari_id),
                )

    conn.commit()
    return {"new": new_items, "price_drop": price_drops, "status_changes": status_changes}
