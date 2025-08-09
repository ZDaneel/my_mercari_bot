import time
from token_manager import load_credentials, save_credentials
from token_gen import get_new_tokens
from mercari_api import fetch_mercari_items, InvalidTokenError
import configparser
from pathlib import Path

def load_config():
    ROOT_DIR = Path(__file__).resolve().parent.parent
    config_file_path = ROOT_DIR / "config.ini"
    
    config = configparser.ConfigParser()
    config.read(config_file_path)

    check_interval = config.getint('settings', 'check_interval_seconds', fallback=60)
    keywords_to_monitor = list(config['keywords'].values())
    page_size = config.getint('settings', 'page_size', fallback=20)

    return check_interval, keywords_to_monitor, page_size

def main():
    check_interval, keywords_to_monitor, page_size = load_config()

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
        for keyword in keywords_to_monitor:
            try:
                items_data = fetch_mercari_items(
                    keyword=keyword, 
                    dpop_token=credentials["dpop_token"], 
                    laplace_uuid=credentials["laplace_uuid"],
                    page_size=page_size
                )
                
                if items_data and 'items' in items_data:
                    print(f"✔️ 成功获取到 {len(items_data['items'])} 个 '{keyword}' 的商品。")
                    print(items_data)
                
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