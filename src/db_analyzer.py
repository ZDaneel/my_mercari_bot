import sqlite3
import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_FILE = ROOT_DIR / "data" / "mercari_monitor.db"


def format_timestamp(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def analyze_database():
    if not DB_FILE.exists():
        print(f"❌ 错误: 数据库文件不存在于 {DB_FILE}")
        return

    print(f"正在分析数据库: {DB_FILE}\n")
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()

    print("=" * 50)
    print("📊 总体概览")
    print("=" * 50)

    cursor.execute("SELECT COUNT(*) FROM keywords WHERE is_active = 1")
    active_keywords_count = cursor.fetchone()[0]
    print(f" ▸ 正在监控的活跃关键词数量: {active_keywords_count}")

    cursor.execute("SELECT COUNT(*) FROM keywords WHERE is_active = 0")
    inactive_keywords_count = cursor.fetchone()[0]
    print(f" ▸ 已停用的不活跃关键词数量: {inactive_keywords_count}")

    cursor.execute("SELECT COUNT(*) FROM items")
    total_items_found = cursor.fetchone()[0]
    print(f" ▸ 数据库中累计发现的商品总数: {total_items_found}")
    print("-" * 50)

    print("\n" + "=" * 50)
    print("📈 各关键词详情分析")
    print("=" * 50)

    cursor.execute("SELECT id, name FROM keywords WHERE is_active = 1")
    active_keywords = cursor.fetchall()

    for kid, name in active_keywords:
        print(f"\n关键词: 【{name}】")
        cursor.execute(
            "SELECT COUNT(*), AVG(price), MIN(price), MAX(price) FROM items WHERE keyword_id = ?",
            (kid,),
        )
        stats = cursor.fetchone()
        count, avg_price, min_price, max_price = stats

        print(f"  - 已发现商品数量: {count or 0}")
        if avg_price:  # 使用日元符号
            print(f"  - 平均价格: {avg_price:,.2f}円")
            print(f"  - 最低价格: {min_price:,}円")
            print(f"  - 最高价格: {max_price:,}円")

        print("  - 最新发现的商品:")
        cursor.execute(
            "SELECT name, price, first_seen_timestamp FROM items WHERE keyword_id = ? ORDER BY first_seen_timestamp DESC LIMIT 3",
            (kid,),
        )
        latest_items = cursor.fetchall()
        if not latest_items:
            print("    - 暂无商品记录")
        for item_name, price, ts in latest_items:
            print(f"    - [{format_timestamp(ts)}] {item_name} - {price:,}円")

    print("\n" + "=" * 50)
    print("🆕 全局最新发现的10个商品")
    print("=" * 50)

    cursor.execute(
        """
        SELECT i.name, i.price, i.first_seen_timestamp, k.name 
        FROM items i
        JOIN keywords k ON i.keyword_id = k.id
        ORDER BY i.first_seen_timestamp DESC 
        LIMIT 10
    """
    )
    global_latest = cursor.fetchall()
    for item_name, price, ts, keyword_name in global_latest:
        print(f"[{format_timestamp(ts)}] [{keyword_name}] {item_name} - {price:,}円")

    conn.close()


if __name__ == "__main__":
    analyze_database()
