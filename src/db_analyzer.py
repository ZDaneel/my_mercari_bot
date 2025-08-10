import sqlite3
import datetime
from pathlib import Path
from collections import defaultdict, Counter
import statistics
import re
import time

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_FILE = ROOT_DIR / "data" / "mercari_monitor.db"


def format_timestamp(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds):
    """格式化时间间隔"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        return f"{seconds // 60}分钟"
    elif seconds < 86400:
        return f"{seconds // 3600}小时"
    else:
        return f"{seconds // 86400}天"


def extract_keywords_from_name(name):
    """从商品名称中提取关键词"""
    # 移除特殊字符和数字
    cleaned = re.sub(r'[【】()（）0-9]+', ' ', name)
    # 分割并过滤短词
    words = [word.strip() for word in cleaned.split() if len(word.strip()) > 1]
    return words


def classify_item_type(name):
    """根据商品名称分类商品类型"""
    name_lower = name.lower()
    
    # 吧唧/缶バッジ
    if any(keyword in name_lower for keyword in ['缶バッジ', '缶バ', '吧唧', 'バッジ']):
        return '缶バッジ'
    
    # 亚克力/アクリル
    elif any(keyword in name_lower for keyword in ['アクリル', '亚克力', 'アクスタ']):
        return 'アクリルスタンド'
    
    # 卡片/カード
    elif any(keyword in name_lower for keyword in ['カード', '卡片', 'card']):
        return 'カード'
    
    # 特典/特典
    elif any(keyword in name_lower for keyword in ['特典', '特典', '特典']):
        return '特典'
    
    # 贴纸/ステッカー
    elif any(keyword in name_lower for keyword in ['ステッカー', '贴纸', 'シール']):
        return 'ステッカー'
    
    # 海报/ポスター
    elif any(keyword in name_lower for keyword in ['ポスター', '海报']):
        return 'ポスター'
    
    # 手办/フィギュア
    elif any(keyword in name_lower for keyword in ['フィギュア', '手办', 'figure']):
        return 'フィギュア'
    
    # 其他
    else:
        return 'その他'


def analyze_database():
    if not DB_FILE.exists():
        print(f"❌ 错误: 数据库文件不存在于 {DB_FILE}")
        return

    print(f"正在分析数据库: {DB_FILE}\n")
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()

    # 基础统计
    print("=" * 60)
    print("📊 总体概览")
    print("=" * 60)

    cursor.execute("SELECT COUNT(*) FROM keywords WHERE is_active = 1")
    active_keywords_count = cursor.fetchone()[0]
    print(f" ▸ 正在监控的活跃关键词数量: {active_keywords_count}")

    cursor.execute("SELECT COUNT(*) FROM keywords WHERE is_active = 0")
    inactive_keywords_count = cursor.fetchone()[0]
    print(f" ▸ 已停用的不活跃关键词数量: {inactive_keywords_count}")

    cursor.execute("SELECT COUNT(*) FROM items")
    total_items_found = cursor.fetchone()[0]
    print(f" ▸ 数据库中累计发现的商品总数: {total_items_found}")

    # 已售出商品统计
    cursor.execute("SELECT COUNT(*) FROM items WHERE status = 'sold_out'")
    sold_items_count = cursor.fetchone()[0]
    print(f" ▸ 已售出商品数量: {sold_items_count}")

    if total_items_found > 0:
        sold_rate = (sold_items_count / total_items_found) * 100
        print(f" ▸ 商品售出率: {sold_rate:.1f}%")

    print("-" * 60)

    # 商品类型分析
    print("\n" + "=" * 60)
    print("🏷️ 商品类型分析")
    print("=" * 60)

    cursor.execute("SELECT name FROM items")
    all_items = cursor.fetchall()
    
    if all_items:
        # 按类型分类商品
        type_stats = defaultdict(list)
        for (name,) in all_items:
            item_type = classify_item_type(name)
            type_stats[item_type].append(name)
        
        print("📊 商品类型分布:")
        for item_type, items in sorted(type_stats.items(), key=lambda x: len(x[1]), reverse=True):
            percentage = (len(items) / len(all_items)) * 100
            print(f"  - {item_type}: {len(items)}件 ({percentage:.1f}%)")

    # 热门商品分析
    print("\n" + "=" * 60)
    print("🔥 热门商品分析")
    print("=" * 60)

    # 分析商品名称中的热门词汇
    cursor.execute("SELECT name FROM items WHERE status = 'sold_out'")
    sold_item_names = cursor.fetchall()
    
    if sold_item_names:
        # 提取商品名称中的关键词
        keywords = []
        for (name,) in sold_item_names:
            keywords.extend(extract_keywords_from_name(name))
        
        keyword_counts = Counter(keywords)
        top_keywords = keyword_counts.most_common(10)
        
        print("📈 最热门的商品关键词（基于已售出商品）:")
        for keyword, count in top_keywords:
            print(f"  - {keyword}: {count}次")

    # 分析所有商品的热门词汇
    cursor.execute("SELECT name FROM items")
    all_item_names = cursor.fetchall()
    
    if all_item_names:
        all_keywords = []
        for (name,) in all_item_names:
            all_keywords.extend(extract_keywords_from_name(name))
        
        all_keyword_counts = Counter(all_keywords)
        top_all_keywords = all_keyword_counts.most_common(15)
        
        print("\n📊 所有商品中最常出现的关键词:")
        for keyword, count in top_all_keywords:
            print(f"  - {keyword}: {count}次")

    # 按关键词和类型分析
    print("\n" + "=" * 60)
    print("📈 按关键词和商品类型的详细分析")
    print("=" * 60)

    cursor.execute("SELECT id, name FROM keywords WHERE is_active = 1")
    active_keywords = cursor.fetchall()

    for kid, keyword_name in active_keywords:
        print(f"\n关键词: 【{keyword_name}】")
        
        # 获取该关键词的所有商品
        cursor.execute("""
            SELECT i.name, i.price, i.status, i.first_seen_timestamp
            FROM items i
            WHERE i.keyword_id = ? AND i.price > 0
        """, (kid,))
        
        items = cursor.fetchall()
        
        if not items:
            print("  - 暂无数据")
            continue
        
        # 按类型分类
        type_data = defaultdict(list)
        for name, price, status, first_seen in items:
            item_type = classify_item_type(name)
            type_data[item_type].append((name, price, status, first_seen))
        
        print(f"  📊 商品类型分布:")
        for item_type, type_items in sorted(type_data.items(), key=lambda x: len(x[1]), reverse=True):
            sold_count = len([item for item in type_items if item[2] == 'sold_out'])
            total_count = len(type_items)
            sold_rate = (sold_count / total_count) * 100 if total_count > 0 else 0
            
            prices = [item[1] for item in type_items]
            avg_price = statistics.mean(prices) if prices else 0
            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 0
            
            print(f"    - {item_type}: {total_count}件 (售出率: {sold_rate:.1f}%)")
            print(f"      价格范围: {min_price:,}円 - {max_price:,}円")
            print(f"      平均价格: {avg_price:,.0f}円")
            
            # 显示该类型中最便宜的几个商品
            cheap_items = sorted(type_items, key=lambda x: x[1])[:3]
            print(f"      最便宜商品:")
            for name, price, status, first_seen in cheap_items:
                status_emoji = "✅" if status == 'sold_out' else "🛒"
                print(f"        {status_emoji} {name} - {price:,}円")
            print()

    # 销售速度分析
    print("\n" + "=" * 60)
    print("⚡ 销售速度分析")
    print("=" * 60)

    cursor.execute("""
        SELECT i.name, i.price, i.first_seen_timestamp, i.last_seen_timestamp, 
               i.mercari_created_timestamp, i.mercari_updated_timestamp, k.name as keyword_name
        FROM items i
        JOIN keywords k ON i.keyword_id = k.id
        WHERE i.status = 'sold_out' AND i.first_seen_timestamp IS NOT NULL
        ORDER BY (i.last_seen_timestamp - i.first_seen_timestamp) ASC
    """)
    
    sold_items = cursor.fetchall()
    
    if sold_items:
        print("🚀 最快售出的商品（从发现到售出）:")
        fastest_sold = sold_items[:5]
        for name, price, first_seen, last_seen, mercari_created, mercari_updated, keyword in fastest_sold:
            duration = last_seen - first_seen
            item_type = classify_item_type(name)
            print(f"  - {name}")
            print(f"    💰 价格: {price:,}円")
            print(f"    🏷️ 类型: {item_type}")
            print(f"    ⏱️  售出时间: {format_duration(duration)}")
            print(f"    🔍 关键词: {keyword}")
            print()

        # 计算平均售出时间
        durations = [item[3] - item[2] for item in sold_items if item[3] and item[2]]
        if durations:
            avg_duration = statistics.mean(durations)
            median_duration = statistics.median(durations)
            print(f"📊 平均售出时间: {format_duration(avg_duration)}")
            print(f"📊 中位数售出时间: {format_duration(median_duration)}")

    # 时间趋势分析
    print("\n" + "=" * 60)
    print("⏰ 时间趋势分析")
    print("=" * 60)

    # 分析最近24小时的商品发现情况
    current_time = int(time.time())
    day_ago = current_time - 86400  # 24小时前
    
    cursor.execute("""
        SELECT COUNT(*), AVG(price), k.name
        FROM items i
        JOIN keywords k ON i.keyword_id = k.id
        WHERE i.first_seen_timestamp >= ?
        GROUP BY k.id, k.name
    """, (day_ago,))
    
    recent_stats = cursor.fetchall()
    
    if recent_stats:
        print("📊 最近24小时的商品发现情况:")
        for count, avg_price, keyword in recent_stats:
            print(f"  - {keyword}: 发现{count}件商品", end="")
            if avg_price:
                print(f", 平均价格: {avg_price:,.0f}円")
            else:
                print()

    # 最新商品动态
    print("\n" + "=" * 60)
    print("🆕 最新发现的商品")
    print("=" * 60)

    cursor.execute("""
        SELECT i.name, i.price, i.first_seen_timestamp, k.name, i.status
        FROM items i
        JOIN keywords k ON i.keyword_id = k.id
        ORDER BY i.first_seen_timestamp DESC 
        LIMIT 10
    """)
    
    latest_items = cursor.fetchall()
    for name, price, ts, keyword, status in latest_items:
        status_emoji = "✅" if status == 'sold_out' else "🛒"
        item_type = classify_item_type(name)
        print(f"{status_emoji} [{format_timestamp(ts)}] [{keyword}] [{item_type}] {name} - {price:,}円")

    # 商品推荐
    print("\n" + "=" * 60)
    print("💡 商品推荐")
    print("=" * 60)

    for kid, keyword_name in active_keywords:
        print(f"\n关键词: 【{keyword_name}】")
        
        cursor.execute("""
            SELECT i.name, i.price, i.status, i.first_seen_timestamp
            FROM items i
            WHERE i.keyword_id = ? AND i.price > 0 AND i.status != 'sold_out'
            ORDER BY i.price ASC
        """, (kid,))
        
        available_items = cursor.fetchall()
        
        if not available_items:
            print("  - 暂无在售商品")
            continue
        
        # 按类型分组推荐
        type_recommendations = defaultdict(list)
        for name, price, status, first_seen in available_items:
            item_type = classify_item_type(name)
            type_recommendations[item_type].append((name, price, first_seen))
        
        print("  🎯 各类型商品推荐:")
        for item_type, items in type_recommendations.items():
            print(f"    📍 {item_type}:")
            # 显示该类型中最便宜的3个商品
            cheap_items = sorted(items, key=lambda x: x[1])[:3]
            for name, price, first_seen in cheap_items:
                print(f"      💰 {price:,}円 - {name}")
            print()

    # 市场洞察
    print("\n" + "=" * 60)
    print("🔍 市场洞察")
    print("=" * 60)

    # 分析哪些类型的商品更受欢迎
    cursor.execute("SELECT name, status FROM items")
    all_items_with_status = cursor.fetchall()
    
    if all_items_with_status:
        type_popularity = defaultdict(lambda: {'total': 0, 'sold': 0})
        
        for name, status in all_items_with_status:
            item_type = classify_item_type(name)
            type_popularity[item_type]['total'] += 1
            if status == 'sold_out':
                type_popularity[item_type]['sold'] += 1
        
        print("📊 各类型商品受欢迎程度:")
        for item_type, stats in sorted(type_popularity.items(), 
                                     key=lambda x: x[1]['sold']/x[1]['total'] if x[1]['total'] > 0 else 0, 
                                     reverse=True):
            sold_rate = (stats['sold'] / stats['total']) * 100 if stats['total'] > 0 else 0
            print(f"  - {item_type}: {stats['sold']}/{stats['total']} ({sold_rate:.1f}%)")

    conn.close()


if __name__ == "__main__":
    analyze_database()
