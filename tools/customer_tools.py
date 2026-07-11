"""
客户发现工具 (Customer Discovery Tools)
使用 Google Custom Search API 搜索潜在客户信息。
API Key 从环境变量 GOOGLE_SEARCH_API_KEY 和 GOOGLE_SEARCH_CSE_ID 读取
"""

import os
import re
import httpx
from typing import Optional

GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_CSE_ID = os.getenv("GOOGLE_SEARCH_CSE_ID", "")

# 用于从网页 snippet / title 中提取联系信息
EMAIL_EXTRACT_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_EXTRACT_PATTERN = re.compile(r"\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")


def _is_api_configured() -> bool:
    """检查 Google Custom Search API 是否已配置"""
    return bool(GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CSE_ID)


async def _google_search(query: str, num: int = 10) -> list[dict]:
    """执行 Google Custom Search 并返回结构化结果"""
    if not _is_api_configured():
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_SEARCH_API_KEY,
        "cx": GOOGLE_SEARCH_CSE_ID,
        "q": query,
        "num": min(num, 10),
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            if "items" in data:
                return data["items"]
    except Exception:
        pass
    return []


async def discover_customers_impl(
    keyword: str,
    market: str,
    product_info: str = "",
    limit: int = 10,
) -> dict:
    """
    使用 Google Custom Search 发现潜在外贸客户。
    构造搜索查询: "importer|distributor|wholesaler" + keyword + market

    如果未配置 API，返回引导信息。
    """
    if not _is_api_configured():
        return {
            "success": False,
            "error": "Google Custom Search API not configured.",
            "hint": "Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CSE_ID environment variables. "
                    "Get free API key at https://developers.google.com/custom-search/v1/overview "
                    "and create CSE at https://programmablesearchengine.google.com/",
            "data": [],
            "total": 0,
        }

    # 构造搜索查询
    search_query = f'"{keyword}" importer OR distributor OR wholesaler "{market}"'
    if product_info:
        search_query += f' "{product_info}"'

    items = await _google_search(search_query, num=limit)

    # 解析搜索结果
    customers = []
    for item in items[:limit]:
        title = item.get("title", "")
        link = item.get("link", "")
        snippet = item.get("snippet", "")
        display_link = item.get("displayLink", "")

        # 尝试从 snippet 中提取邮箱
        emails = EMAIL_EXTRACT_PATTERN.findall(snippet)
        phones = PHONE_EXTRACT_PATTERN.findall(snippet)

        customers.append({
            "company": title,
            "website": link,
            "domain": display_link,
            "contact": emails[0] if emails else "",
            "phone": phones[0] if phones else "",
            "country": market,
            "description": snippet,
            "source": "google_custom_search",
        })

    return {
        "success": True,
        "data": customers,
        "total": len(customers),
        "search_query": search_query,
        "message": f"Found {len(customers)} potential customers for '{keyword}' in {market}",
    }


async def search_company_info_impl(company_name: str) -> dict:
    """
    使用 Google Custom Search 搜索公司信息。
    构造查询: company_name + about/contact/website
    """
    if not _is_api_configured():
        return {
            "success": False,
            "error": "Google Custom Search API not configured.",
            "hint": "Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CSE_ID environment variables.",
            "data": {},
        }

    # 搜索公司网站和基本信息
    search_query = f'"{company_name}" about contact company info'
    items = await _google_search(search_query, num=5)

    if not items:
        return {
            "success": False,
            "error": f"No results found for company: {company_name}",
            "data": {},
        }

    # 取第一个结果作为主要信息源
    primary = items[0]
    snippet = primary.get("snippet", "")
    emails = EMAIL_EXTRACT_PATTERN.findall(snippet + " " + primary.get("title", ""))

    return {
        "success": True,
        "data": {
            "name": company_name,
            "website": primary.get("link", ""),
            "domain": primary.get("displayLink", ""),
            "title": primary.get("title", ""),
            "email": emails[0] if emails else "",
            "description": snippet,
            "additional_results": [
                {"title": it.get("title", ""), "link": it.get("link", ""), "snippet": it.get("snippet", "")}
                for it in items[1:]
            ],
            "source": "google_custom_search",
        },
    }
