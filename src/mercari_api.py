import requests
import json
import uuid

class InvalidTokenError(Exception):
    pass

API_URL = "https://api.mercari.jp/v2/entities:search"

def fetch_mercari_items(keyword: str, dpop_token: str, laplace_uuid: str, page_size: int = 20):
    headers = {
        "content-type": "application/json",
        "dpop": dpop_token,
        "x-platform": "web",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    }
    
    payload = {
        "pageSize": page_size,
        "searchCondition": {
            "keyword": keyword,
            "sort": "SORT_CREATED_TIME", 
            "order": "ORDER_DESC",
            "status": [],
            "excludeKeyword": "",
            "sizeId": [],
            "categoryId": [],
            "brandId": [],
            "sellerId": [],
            "priceMin": 0,
            "priceMax": 0,
            "itemConditionId": [],
            "shippingPayerId": [],
            "shippingFromArea": [],
            "shippingMethod": [],
            "colorId": [],
            "hasCoupon": False,
            "attributes": [],
            "itemTypes": [],
            "skuIds": [],
            "shopIds": [],
            "excludeShippingMethodIds": []
        },
        "source": "BaseSerp",
        "serviceFrom": "suruga",
        "withItemBrand": True,
        "withItemPromotions": True,
        "withItemSizes": True,
        "withAuction": True,
        "laplaceDeviceUuid": laplace_uuid,
        "searchSessionId": uuid.uuid4().hex
    }

    print(f"🔍 正在为关键词 '{keyword}' 请求商品信息...")
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=15)

        if response.status_code == 401:
            raise InvalidTokenError("DPOP 令牌已过期或无效。")

        response.raise_for_status()
        
        print("✅ 请求成功！")
        return response.json()

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 错误发生: {e}")
        print("--- 服务器返回的详细信息 ---")
        try:
            print(json.dumps(e.response.json(), indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(e.response.text)
        print("--------------------------")
        return None 
    
    except requests.exceptions.RequestException as e:
        raise e