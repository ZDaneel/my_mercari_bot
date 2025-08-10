import sqlite3
from pathlib import Path
import time
import sys

ROOT_DIR = ""
# 判断程序是否被打包
if getattr(sys, 'frozen', False):
    # 如果是打包后的 .exe 文件，根目录是 .exe 文件所在的目录
    ROOT_DIR = Path(sys.executable).parent
else:
    # 如果是正常运行的 .py 脚本，根目录是 src 的上一级
    ROOT_DIR = Path(__file__).resolve().parent.parent
DB_FILE = ROOT_DIR / "data" / "mercari_monitor.db"


def get_connection():
    """获取数据库连接，在连接前确保父目录存在。"""
    
    db_directory = DB_FILE.parent
    db_directory.mkdir(parents=True, exist_ok=True)

    return sqlite3.connect(str(DB_FILE))


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
        price INTEGER,
        image_url TEXT,
        first_seen_timestamp INTEGER,
        last_seen_timestamp INTEGER,
        mercari_created_timestamp INTEGER,
        mercari_updated_timestamp INTEGER,
        status TEXT,
        sold_timestamp INTEGER,
        FOREIGN KEY (keyword_id) REFERENCES keywords (id)
    )"""
    )
    
    # 检查是否需要添加sold_timestamp字段（向后兼容）
    cursor.execute("PRAGMA table_info(items)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'sold_timestamp' not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN sold_timestamp INTEGER")
        print("✅ 已添加 sold_timestamp 字段到 items 表")
    
    conn.commit()


def sync_keywords(conn, config_keywords: list):
    cursor = conn.cursor()
    
    # 获取同步前的活跃关键词
    cursor.execute("SELECT name FROM keywords WHERE is_active = 1")
    old_active_keywords = [row[0] for row in cursor.fetchall()]
    
    # 将所有关键词设为非活跃
    cursor.execute("UPDATE keywords SET is_active = 0")
    
    # 处理新的关键词列表
    for keyword in config_keywords:
        cursor.execute("INSERT OR IGNORE INTO keywords (name) VALUES (?)", (keyword,))
        cursor.execute("UPDATE keywords SET is_active = 1 WHERE name = ?", (keyword,))
    
    conn.commit()
    
    # 获取同步后的活跃关键词
    cursor.execute("SELECT name FROM keywords WHERE is_active = 1")
    new_active_keywords = [row[0] for row in cursor.fetchall()]
    
    # 记录同步结果
    from .logger import get_logger
    logger = get_logger("database")
    logger.info(f"🔄 数据库关键词同步:")
    logger.info(f"   同步前活跃关键词: {old_active_keywords}")
    logger.info(f"   配置中的关键词: {config_keywords}")
    logger.info(f"   同步后活跃关键词: {new_active_keywords}")


def get_active_keywords_with_ids(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM keywords WHERE is_active = 1")
    active_keywords = cursor.fetchall()
    
    # 记录获取的活跃关键词
    from .logger import get_logger
    logger = get_logger("database")
    logger.info(f"📋 获取活跃关键词: {[kw[1] for kw in active_keywords]}")
    
    return active_keywords


def process_items_batch(conn, items_list: list, keyword_id: int):
    cursor = conn.cursor()
    new_items = []
    price_drops = []
    status_changes = []

    # 记录处理开始
    from .logger import get_logger
    logger = get_logger("database")
    logger.info(f"🔄 开始处理 {len(items_list)} 个商品")

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
                logger.warning(f"⚠️ 跳过无法解析价格的商品: {mercari_id}")
                continue
            current_price = int(digits)

        cursor.execute(
            "SELECT price, status, mercari_created_timestamp, mercari_updated_timestamp FROM items WHERE item_mercari_id = ?",
            (mercari_id,),
        )
        result = cursor.fetchone()

        if result is None:
            # 新商品
            current_timestamp = int(time.time())
            mercari_created = item.get("created")
            mercari_updated = item.get("updated")
            
            item["status"] = current_status
            new_items.append(item)
            # 移除重复的日志输出，避免与控制台通知器重复
            # logger.info(f"🆕 发现新商品: {item['name']} (ID: {mercari_id})")
            cursor.execute(
                """INSERT INTO items (item_mercari_id, keyword_id, name, price, image_url, first_seen_timestamp, last_seen_timestamp, mercari_created_timestamp, mercari_updated_timestamp, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    mercari_id,
                    keyword_id,
                    item["name"],
                    current_price,
                    item["image_url"],
                    current_timestamp,  # 我们第一次看到的时间
                    current_timestamp,  # 我们最后看到的时间
                    int(mercari_created) if mercari_created else None,  # Mercari创建时间
                    int(mercari_updated) if mercari_updated else None,  # Mercari更新时间
                    current_status,
                ),
            )
        else:
            stored_price, stored_status, stored_created, stored_updated = result
            needs_update = False
            
            # 检查价格变化
            if current_price < stored_price:
                current_timestamp = int(time.time())
                mercari_updated = item.get("updated")
                item["old_price"] = f"¥{stored_price}"
                price_drops.append(item)
                # 移除重复的日志输出，避免与控制台通知器重复
                # logger.info(f"🔻 发现降价商品: {item['name']} {stored_price} → {current_price}円")
                cursor.execute(
                    "UPDATE items SET price = ?, last_seen_timestamp = ?, mercari_updated_timestamp = ? WHERE item_mercari_id = ?",
                    (current_price, current_timestamp, int(mercari_updated) if mercari_updated else None, mercari_id),
                )
                needs_update = True
            
            # 检查状态变化
            if stored_status != current_status:
                current_timestamp = int(time.time())
                mercari_updated = item.get("updated")
                item["old_status"] = stored_status
                item["new_status"] = current_status
                status_changes.append(item)
                
                # 检查是否是从在售状态变为交易中状态（售出）
                is_sold = (stored_status in ['on_sale', 'ITEM_STATUS_ON_SALE'] and 
                          current_status in ['trading', 'ITEM_STATUS_TRADING', 'sold_out'])
                
                # 更新状态和售出时间
                if is_sold:
                    logger.info(f"💰 商品已售出: {item['name']} {stored_status} → {current_status}")
                    cursor.execute(
                        "UPDATE items SET status = ?, last_seen_timestamp = ?, mercari_updated_timestamp = ?, sold_timestamp = ? WHERE item_mercari_id = ?",
                        (current_status, current_timestamp, int(mercari_updated) if mercari_updated else None, current_timestamp, mercari_id),
                    )
                else:
                    # 移除重复的日志输出，避免与控制台通知器重复
                    # logger.info(f"🔄 发现状态变化: {item['name']} {stored_status} → {current_status}")
                    cursor.execute(
                        "UPDATE items SET status = ?, last_seen_timestamp = ?, mercari_updated_timestamp = ? WHERE item_mercari_id = ?",
                        (current_status, current_timestamp, int(mercari_updated) if mercari_updated else None, mercari_id),
                    )
                needs_update = True
            
            # 更新最后看到时间和Mercari时间戳
            current_timestamp = int(time.time())
            mercari_updated = item.get("updated")
            
            if needs_update:
                # 已经在上面更新过了，这里只需要更新last_seen_timestamp
                cursor.execute(
                    "UPDATE items SET last_seen_timestamp = ? WHERE item_mercari_id = ?",
                    (current_timestamp, mercari_id),
                )
            else:
                # 没有变化，只更新我们最后看到的时间和Mercari更新时间
                cursor.execute(
                    "UPDATE items SET last_seen_timestamp = ?, mercari_updated_timestamp = ? WHERE item_mercari_id = ?",
                    (current_timestamp, int(mercari_updated) if mercari_updated else stored_updated, mercari_id),
                )

    conn.commit()
    
    # 记录处理结果
    logger.info(f"📊 处理完成 - 新商品: {len(new_items)}, 降价: {len(price_drops)}, 状态变化: {len(status_changes)}")
    
    return {
        "new": new_items,
        "price_drop": price_drops,
        "status_changes": status_changes,
    }
