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
from webdriver_manager.chrome import ChromeDriverManager


def get_new_tokens(test_mode: bool = False, proxy: str = None, headless: bool = True):
    print("🚀 开始启动浏览器以获取 dpop 令牌...")

    options = Options()
    options.add_argument("--window-size=1920,1080")
    if headless:
        options.add_argument("--headless=new")
#
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-features=VizDisplayCompositor")

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 使用webdriver-manager自动管理ChromeDriver
    print("🔧 正在自动下载/更新ChromeDriver...")
    
    # 设置seleniumwire代理
    seleniumwire_options = {}
    if proxy and proxy.strip():
        print(f"🔗 使用代理: {proxy.strip()}")
        proxy_url = proxy.strip()
        if not proxy_url.startswith(('http://', 'https://')):
            proxy_url = 'http://' + proxy_url
        seleniumwire_options = {
            'proxy': {
                'http': proxy_url,
                'https': proxy_url
            }
        }

    # 使用简洁的webdriver-manager语法
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options, 
        seleniumwire_options=seleniumwire_options
    )
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        },
    )

    try:
        print("🌐 正在直接访问搜索页面...")
        driver.get("https://jp.mercari.com/search?keyword=nintendo")
        print("🔍 已访问搜索页面，等待 API 响应...")

        def request_interceptor(request):
            pass

        driver.request_interceptor = request_interceptor

        # 减少超时时间，如果20秒内没有API请求，说明页面可能有问题
        request = driver.wait_for_request("/v2/entities:search", timeout=15)
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
        if headless:
            print(
                "   可能是页面结构已改变，或等待超时。请尝试取消勾选'启用无头模式'以进行调试。"
            )
        else:
            print(
                "   可能是页面结构已改变，或等待超时。请检查浏览器窗口中的页面状态。"
            )
        dpop_token = None
        laplace_uuid = None
    finally:
        try:
            driver.quit()
        except:
            pass

    if test_mode:
        print(f"dpop_token: {dpop_token}")
        print(f"laplace_uuid: {laplace_uuid}")

    if dpop_token and laplace_uuid:
        return dpop_token, laplace_uuid
    else:
        return None, None


if __name__ == "__main__":
    get_new_tokens(test_mode=True)
