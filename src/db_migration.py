import sqlite3
from pathlib import Path
import sys
import os

# 更智能的路径检测
def get_root_dir():
    """获取项目根目录"""
    # 方法1: 检查是否在打包环境中
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    
    # 方法2: 检查当前工作目录
    current_dir = Path.cwd()
    if (current_dir / "data").exists() and (current_dir / "src").exists():
        return current_dir
    
    # 方法3: 检查脚本所在目录的上级目录
    script_dir = Path(__file__).resolve().parent
    parent_dir = script_dir.parent
    if (parent_dir / "data").exists() and (parent_dir / "src").exists():
        return parent_dir
    
    # 方法4: 检查环境变量
    if 'MERCARI_BOT_ROOT' in os.environ:
        return Path(os.environ['MERCARI_BOT_ROOT'])
    
    # 方法5: 默认使用脚本所在目录的上级目录
    return script_dir.parent

ROOT_DIR = get_root_dir()
DB_FILE = ROOT_DIR / "data" / "mercari_monitor.db"


def migrate_database():
    """迁移数据库，添加sold_timestamp字段并更新现有数据"""
    
    print(f"🔍 检测到的根目录: {ROOT_DIR}")
    print(f"🔍 数据库文件路径: {DB_FILE}")
    
    # 确保data目录存在
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if not DB_FILE.exists():
        print(f"❌ 数据库文件不存在: {DB_FILE}")
        print("💡 提示: 首次运行时会自动创建数据库文件")
        # 创建空的数据库文件
        conn = sqlite3.connect(str(DB_FILE))
        conn.close()
        print("✅ 已创建新的数据库文件")
    
    print(f"🔄 开始数据库迁移: {DB_FILE}")
    
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    
    try:
        # 1. 检查sold_timestamp字段是否存在
        cursor.execute("PRAGMA table_info(items)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'sold_timestamp' not in columns:
            print("📝 添加 sold_timestamp 字段...")
            cursor.execute("ALTER TABLE items ADD COLUMN sold_timestamp INTEGER")
            print("✅ sold_timestamp 字段已添加")
        else:
            print("✅ sold_timestamp 字段已存在")
        
        # 2. 为现有的已售出商品设置sold_timestamp
        print("🔄 更新现有已售出商品的sold_timestamp...")
        
        # 获取所有已售出但没有sold_timestamp的商品
        cursor.execute("""
            SELECT item_mercari_id, last_seen_timestamp 
            FROM items 
            WHERE status = 'sold_out' AND sold_timestamp IS NULL
        """)
        
        sold_items = cursor.fetchall()
        print(f"📊 找到 {len(sold_items)} 个需要更新的已售出商品")
        
        updated_count = 0
        for item_id, last_seen in sold_items:
            if last_seen:
                cursor.execute(
                    "UPDATE items SET sold_timestamp = ? WHERE item_mercari_id = ?",
                    (last_seen, item_id)
                )
                updated_count += 1
        
        print(f"✅ 已更新 {updated_count} 个商品的sold_timestamp")
        
        # 3. 提交更改
        conn.commit()
        print("✅ 数据库迁移完成")
        
        # 4. 显示统计信息
        cursor.execute("SELECT COUNT(*) FROM items WHERE sold_timestamp IS NOT NULL")
        sold_with_timestamp = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM items WHERE status = 'sold_out'")
        total_sold = cursor.fetchone()[0]
        
        print(f"📊 迁移后统计:")
        print(f"  - 有售出时间戳的商品: {sold_with_timestamp}")
        print(f"  - 总已售出商品: {total_sold}")
        
    except Exception as e:
        print(f"❌ 迁移过程中发生错误: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()
