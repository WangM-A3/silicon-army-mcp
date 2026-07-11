"""
供应商查找工具 (Supplier Tools)
抓取阿里巴巴公开搜索页面解析供应商信息。
不需要 API Key，使用 httpx 抓取公开页面。
"""

import re
import httpx
from typing import Optional

# Alibaba 搜索 URL
ALIBABA_SEARCH_URL = "https://www.alibaba.com/trade/search"

# 从搜索结果页面提取供应商信息的正则
COMPANY_NAME_PATTERN = re.compile(
    r'"companyName"\s*:\s*"([^"]+)"', re.IGNORECASE
)
SUPPLIER_PATTERN = re.compile(
    r'data-role="supplierCard"', re.IGNORECASE
)

# 备用: 从 JSON-LD 或 meta 标签提取
TITLE_PATTERN = re.compile(r'<title>([^<]+)</title>', re.IGNORECASE)


async def find_suppliers_by_product_impl(
    product_keyword: str,
    country: str = "China",
) -> list:
    """
    从阿里巴巴公开搜索页面查找供应商。

    通过 httpx 抓取 Alibaba 搜索结果页面，解析 HTML 提取供应商信息。
    无需 API Key，但可能受反爬限制；失败时返回空列表并附带提示。
    """
    params = {
        "SearchText": product_keyword,
        "indexArea": "company_en",
        "country": country,
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    suppliers = []

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(ALIBABA_SEARCH_URL, params=params, headers=headers)

            if resp.status_code != 200:
                return [
                    {
                        "success": False,
                        "error": f"Alibaba returned HTTP {resp.status_code}",
                        "hint": "Alibaba may be blocking automated requests. Try again later or use Google Custom Search as fallback.",
                    }
                ]

            html = resp.text

            # 提取公司名
            company_names = COMPANY_NAME_PATTERN.findall(html)

            if company_names:
                # 去重
                seen = set()
                for name in company_names[:10]:
                    if name not in seen:
                        seen.add(name)
                        suppliers.append({
                            "name": name,
                            "location": country,
                            "source": "alibaba.com",
                            "alibaba_url": f"https://www.alibaba.com/company/{name.replace(' ', '-').lower()}.html",
                        })
            else:
                # 如果正则未匹配到，返回提示
                return [
                    {
                        "success": False,
                        "error": "No supplier data could be extracted from Alibaba search results.",
                        "hint": "Alibaba may have changed its page structure. Consider using Google Custom Search to find suppliers instead.",
                        "search_url": f"https://www.alibaba.com/trade/search?SearchText={product_keyword}",
                    }
                ]

    except httpx.TimeoutException:
        return [
            {
                "success": False,
                "error": "Request to Alibaba timed out.",
                "hint": "Try again later or use find_suppliers_by_product with a different approach.",
            }
        ]
    except Exception as e:
        return [
            {
                "success": False,
                "error": str(e),
                "hint": "Network error when accessing Alibaba. Check internet connection.",
            }
        ]

    return suppliers if suppliers else [
        {
            "success": False,
            "error": "No suppliers found.",
            "hint": f"No supplier results for '{product_keyword}' on Alibaba. Try a broader keyword.",
        }
    ]
