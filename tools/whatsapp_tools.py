"""
WhatsApp 工具 (WhatsApp Tools)
当前为 demo 模式 — 保留 mock 但改进返回结构。
后续可通过接入 WhatsApp Business API 升级为真实发送。

注意: WhatsApp Business API 需要 Meta Business 账号，
不在免费范围内，因此暂保留 demo 模式。
"""

import os
import time
import uuid
from typing import Optional

# 环境变量（未来对接 WhatsApp Business API 时使用）
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")


def _generate_message_id(prefix: str = "wa") -> str:
    """生成唯一消息ID"""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


async def send_whatsapp_message_impl(
    phone_number: str,
    message: str,
    message_type: str = "text",
) -> dict:
    """
    发送 WhatsApp 消息 (Demo模式)。
    未来可通过 WhatsApp Business API 升级。
    """
    msg_id = _generate_message_id("wa")

    return {
        "success": True,
        "data_source": "demo",
        "message_id": msg_id,
        "status": "queued",
        "to": phone_number,
        "type": message_type,
        "content_preview": message[:100] + "..." if len(message) > 100 else message,
        "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "Demo mode. Configure WHATSAPP_TOKEN and WHATSAPP_PHONE_ID for real WhatsApp Business API.",
    }


async def send_whatsapp_product_card_impl(
    phone_number: str,
    product_name: str,
    product_image: str = "",
    price: str = "",
    description: str = "",
) -> dict:
    """
    发送产品卡片到 WhatsApp (Demo模式)。
    """
    msg_id = _generate_message_id("wa_card")

    return {
        "success": True,
        "data_source": "demo",
        "message_id": msg_id,
        "status": "queued",
        "to": phone_number,
        "card": {
            "product_name": product_name,
            "product_image": product_image or None,
            "price": price or None,
            "description": description or None,
        },
        "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "Demo mode. Configure WHATSAPP_TOKEN and WHATSAPP_PHONE_ID for real WhatsApp Business API.",
    }


async def get_whatsapp_message_status_impl(message_id: str) -> dict:
    """
    获取 WhatsApp 消息状态 (Demo模式)。
    """
    return {
        "success": True,
        "data_source": "demo",
        "message_id": message_id,
        "status": "delivered",
        "delivered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "read": False,
        "note": "Demo mode. Configure WHATSAPP_TOKEN for real WhatsApp Business API.",
    }
