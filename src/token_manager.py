import json
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT_DIR / "data" / "dpop_token.json"


def save_credentials(dpop_token: str, laplace_uuid: str):
    print("💾 正在将新凭据保存到文件...")
    credentials = {
        "dpop_token": dpop_token,
        "laplace_uuid": laplace_uuid,
        "last_update": int(time.time()),
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(credentials, f, indent=2)
        print("✅ 凭据已成功保存。")
    except IOError as e:
        print(f"❌ 错误：无法将凭据写入文件 {CONFIG_FILE}。错误信息: {e}")


def load_credentials() -> dict | None:
    print("📂 正在尝试从文件加载凭据...")
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            credentials = json.load(f)
            if (
                credentials.get("dpop_token")
                and credentials.get("laplace_uuid")
                and credentials.get("last_update")
            ):
                print("✅ 成功从文件加载凭据。")
                return credentials
            else:
                print("🤔 配置文件不完整。")
                return None
    except (FileNotFoundError, json.JSONDecodeError):
        print("🤔 凭据文件不存在或格式错误。")
        return None
