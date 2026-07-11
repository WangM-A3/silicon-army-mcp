"""
海关数据工具 (Customs Data Tools)
进出口海关数据查询 — 当前为 demo 模式，返回结构化示例数据。
数据源标注 "data_source: demo"，后续可对接真实海关数据API。
"""

import time
from typing import Optional


# 时间范围映射
TIME_RANGE_MAP = {
    "last_month": "最近1个月",
    "last_quarter": "最近1个季度",
    "last_year": "最近1年",
}


async def query_import_data_impl(
    hs_code: str,
    country: str,
    time_range: str = "last_year",
) -> dict:
    """
    查询进口海关数据 (Demo模式)。

    返回更真实的数据结构，标注 data_source: demo。
    后续可通过接入海关数据API升级为真实数据。
    """
    time_desc = TIME_RANGE_MAP.get(time_range, time_range)

    return {
        "success": True,
        "data_source": "demo",
        "query": {
            "hs_code": hs_code,
            "country": country,
            "time_range": time_range,
            "time_description": time_desc,
        },
        "data": {
            "import_volume": {
                "value": 10000,
                "unit": "tons",
                "period": time_desc,
            },
            "import_value_usd": {
                "value": 5000000,
                "currency": "USD",
                "period": time_desc,
            },
            "average_unit_price": {
                "value": 500,
                "currency": "USD/ton",
            },
            "top_exporters": [
                {"country": "China", "share": "35%", "volume": 3500},
                {"country": "Vietnam", "share": "20%", "volume": 2000},
                {"country": "Germany", "share": "15%", "volume": 1500},
            ],
            "monthly_trend": [
                {"month": "Jan", "volume": 800},
                {"month": "Feb", "volume": 750},
                {"month": "Mar", "volume": 920},
                {"month": "Apr", "volume": 880},
                {"month": "May", "volume": 950},
                {"month": "Jun", "volume": 1020},
            ],
            "trend_summary": "同比上升 15%，环比上升 3%",
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "This is demo data. Connect a real customs data API for production use.",
    }


async def query_export_data_impl(
    hs_code: str,
    country: str,
    time_range: str = "last_year",
) -> dict:
    """
    查询出口海关数据 (Demo模式)。

    返回更真实的数据结构，标注 data_source: demo。
    """
    time_desc = TIME_RANGE_MAP.get(time_range, time_range)

    return {
        "success": True,
        "data_source": "demo",
        "query": {
            "hs_code": hs_code,
            "country": country,
            "time_range": time_range,
            "time_description": time_desc,
        },
        "data": {
            "export_volume": {
                "value": 15000,
                "unit": "tons",
                "period": time_desc,
            },
            "export_value_usd": {
                "value": 7500000,
                "currency": "USD",
                "period": time_desc,
            },
            "average_unit_price": {
                "value": 500,
                "currency": "USD/ton",
            },
            "top_importers": [
                {"country": "USA", "share": "30%", "volume": 4500},
                {"country": "UK", "share": "18%", "volume": 2700},
                {"country": "Japan", "share": "15%", "volume": 2250},
            ],
            "monthly_trend": [
                {"month": "Jan", "volume": 1200},
                {"month": "Feb", "volume": 1100},
                {"month": "Mar", "volume": 1380},
                {"month": "Apr", "volume": 1320},
                {"month": "May", "volume": 1425},
                {"month": "Jun", "volume": 1530},
            ],
            "trend_summary": "同比上升 20%，环比上升 5%",
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "This is demo data. Connect a real customs data API for production use.",
    }
