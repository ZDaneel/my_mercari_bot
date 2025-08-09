import time
import json
from seleniumwire import webdriver 
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def get_dpop_token():
    """
    启动一个带监控的浏览器来获取 dpop 令牌。
    """
    print("🚀 开始启动浏览器以获取 dpop 令牌...")
    
    options = Options()
    options.add_argument('--headless')  # 使用无头模式，不在屏幕上显示浏览器窗口
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')

    # selenium-wire 的配置
    sw_options = {
        'disable_capture': True  # 先禁用捕获，需要时再开启
    }

    # 使用 webdriver-manager 自动管理 ChromeDriver
    service = Service(ChromeDriverManager().install())
    
    # 初始化带有 selenium-wire 功能的 driver
    driver = webdriver.Chrome(service=service, chrome_options=options, seleniumwire_options=sw_options)

    print("🌐 正在访问 Mercari 网站...")
    # 开始监控请求
    del driver.requests
    
    # 访问一个任意的搜索页面来触发 API 调用
    driver.get('https://jp.mercari.com/search?keyword=nintendo')

    print("⏳ 等待 API 请求完成...")
    # 等待几秒钟，确保后台的 API 请求已经发出并被捕获
    time.sleep(8) # 等待时间可能需要根据网络情况调整

    dpop_token = None
    # 遍历所有捕获到的请求
    for request in driver.requests:
        # 我们只关心对搜索 API 的请求
        if "api.mercari.jp/v2/entities:search" in request.url:
            print("🎯 成功捕获到目标 API 请求！")
            # 从这个请求的请求头中提取 dpop 令牌
            if 'dpop' in request.headers:
                dpop_token = request.headers['dpop']
                print("🎉 成功找到 dpop 令牌！")
                break
    
    driver.quit() # 关闭浏览器

    if dpop_token:
        print("\n" + "="*50)
        print("✅ DPOP 令牌获取成功！请复制下面的完整令牌：")
        print(dpop_token)
        print("="*50 + "\n")
    else:
        print("\n❌ 未能获取 dpop 令牌。请检查网络或增加等待时间再试一次。\n")
        
    return dpop_token

if __name__ == "__main__":
    get_dpop_token()