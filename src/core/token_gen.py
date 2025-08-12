import time
import json
import sys
from pathlib import Path
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ..utils.logger import get_resource_path


def get_new_tokens(test_mode: bool = False, proxy: str = None):
    print("🚀 开始启动浏览器以获取 dpop 令牌...")

    options = Options()
    options.add_argument("--window-size=1920,1080")
    #options.add_argument("--headless=new")

    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 设置代理
    if proxy and proxy.strip():
        print(f"🔗 使用代理: {proxy.strip()}")
        options.add_argument(f'--proxy-server={proxy.strip()}')

    # 使用通用的资源路径查找函数
    driver_path = get_resource_path("driver/chromedriver.exe")

    if not driver_path.exists():
        print(f"❌ 错误: 未在以下路径找到 chromedriver.exe -> {driver_path}")
        print(f"   已尝试的路径:")
        if getattr(sys, 'frozen', False):
            from ..utils.logger import get_project_root
            base_path = get_project_root()
            print(f"   - {base_path / '_internal' / 'driver' / 'chromedriver.exe'}")
            print(f"   - {base_path / 'driver' / 'chromedriver.exe'}")
        else:
            print(f"   - {driver_path}")
        return None, None
    
    service = Service(executable_path=str(driver_path))

    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        },
    )

    print("🌐 正在访问 Mercari 网站...")
    driver.get("https://jp.mercari.com/")

    try:
        print("⏳ 等待页面加载并寻找搜索框...")
        search_box = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'input[placeholder="なにをお探しですか？"]')
            )
        )
        print("✅ 搜索框已找到。")

        search_box.send_keys("nintendo")
        search_box.submit()
        print("🔍 已提交搜索，等待 API 响应...")

        def request_interceptor(request):
            pass

        driver.request_interceptor = request_interceptor

        request = driver.wait_for_request("/v2/entities:search", timeout=20)
        dpop_token = request.headers.get("dpop")
        laplace_uuid = None

        if request.body:
            try:
                body_data = json.loads(request.body.decode("utf-8"))
                laplace_uuid = body_data.get("laplaceDeviceUuid")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"解析请求体失败: {e}")

    except Exception as e:
        print(f"\n❌ 在执行过程中发生错误: {e}")
        print(
            "   可能是页面结构已改变，或等待超时。请尝试在非无头模式下运行以进行调试。"
        )
        dpop_token = None
    finally:
        driver.quit()

    if test_mode:
        print(f"dpop_token: {dpop_token}")
        print(f"laplace_uuid: {laplace_uuid}")

    if dpop_token and laplace_uuid:
        return dpop_token, laplace_uuid
    else:
        return None, None


if __name__ == "__main__":
    get_new_tokens(test_mode=True)
