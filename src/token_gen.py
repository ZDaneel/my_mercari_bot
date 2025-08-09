import time
import json
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def get_new_tokens():
    print("🚀 开始启动浏览器以获取 dpop 令牌...")

    options = Options()

    options.add_argument("--headless=new")

    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

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

    if dpop_token and laplace_uuid:
        return dpop_token, laplace_uuid
    else:
        return None, None


if __name__ == "__main__":
    get_new_tokens()
