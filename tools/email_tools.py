"""
邮件相关工具 (Email Tools)
对接 Resend API (https://resend.com) — 免费 3000 封/月
API Key 从环境变量 RESEND_API_KEY 读取
发件人地址从环境变量 RESEND_FROM_EMAIL 读取
"""

import os
import time
import httpx
from typing import Optional

# ──────────────────────────────────────────────
# 环境变量
# ──────────────────────────────────────────────
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
RESEND_API_URL = "https://api.resend.com/emails"

# ──────────────────────────────────────────────
# 邮件模板
# ──────────────────────────────────────────────
EMAIL_TEMPLATES = {
    "dev_letter": (
        "<div style='font-family:Arial,sans-serif;max-width:600px;margin:0 auto'>"
        "<h2 style='color:#1a1a1a'>Hello {name},</h2>"
        "<p>We are a manufacturer specializing in {product}. "
        "We'd love to explore a partnership with your company.</p>"
        "<p>Best regards,<br/>Silicon Army Team</p>"
        "</div>"
    ),
    "follow_up": (
        "<div style='font-family:Arial,sans-serif;max-width:600px;margin:0 auto'>"
        "<h2 style='color:#1a1a1a'>Hi {name},</h2>"
        "<p>Following up on my previous email about {product}. "
        "Would you be available for a quick call this week?</p>"
        "<p>Best regards,<br/>Silicon Army Team</p>"
        "</div>"
    ),
    "product_intro": (
        "<div style='font-family:Arial,sans-serif;max-width:600px;margin:0 auto'>"
        "<h2 style='color:#1a1a1a'>Introducing our {product}</h2>"
        "{content}"
        "<p>For more details, please visit our website.</p>"
        "<p>Best regards,<br/>Silicon Army Team</p>"
        "</div>"
    ),
}


def _get_template(template_type: str, **kwargs) -> str:
    """根据模板类型生成邮件HTML"""
    tpl = EMAIL_TEMPLATES.get(template_type, EMAIL_TEMPLATES["dev_letter"])
    return tpl.format(**kwargs)


async def send_email_impl(
    to_address: str,
    subject: str,
    content: str,
    template_type: str = "dev_letter",
) -> dict:
    """
    通过 Resend API 发送邮件。

    Returns:
        发送结果，包含 email_id 和 tracking 信息
    """
    if not RESEND_API_KEY:
        return {
            "success": False,
            "error": "RESEND_API_KEY not set. Please configure environment variable RESEND_API_KEY.",
            "hint": "Get your free API key at https://resend.com/api-keys",
        }

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    # 如果 content 是模板类型，应用模板
    if template_type in EMAIL_TEMPLATES and "{" in EMAIL_TEMPLATES[template_type]:
        html_body = _get_template(template_type, name="", product="", content=content)
    else:
        html_body = content

    payload = {
        "from": RESEND_FROM_EMAIL,
        "to": [to_address],
        "subject": subject,
        "html": html_body,
        "tags": [{"name": "template_type", "value": template_type}],
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = client.post(RESEND_API_URL, json=payload, headers=headers) if False else await client.post(RESEND_API_URL, json=payload, headers=headers)
            data = resp.json()

            if resp.status_code == 200:
                return {
                    "success": True,
                    "email_id": data.get("id", ""),
                    "status": "sent",
                    "to": to_address,
                    "subject": subject,
                    "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "tracking_url": f"https://resend.com/emails/{data.get('id', '')}",
                }
            else:
                return {
                    "success": False,
                    "error": data.get("message", f"HTTP {resp.status_code}"),
                    "to": to_address,
                    "status_code": resp.status_code,
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "to": to_address,
            "hint": "Network error. Check your internet connection and API key.",
        }


async def batch_send_emails_impl(
    recipients: list,
    subject: str,
    content: str,
    template_type: str = "dev_letter",
) -> dict:
    """
    通过 Resend Batch API 批量发送邮件。
    """
    if not RESEND_API_KEY:
        return {
            "success": False,
            "error": "RESEND_API_KEY not set. Please configure environment variable RESEND_API_KEY.",
            "hint": "Get your free API key at https://resend.com/api-keys",
        }

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    # 构建批量邮件
    batch_payload = []
    for r in recipients:
        addr = r if isinstance(r, str) else r.get("address", "")
        name = r.get("name", "") if isinstance(r, dict) else ""
        html_body = _get_template(template_type, name=name, product="", content=content)
        batch_payload.append({
            "from": RESEND_FROM_EMAIL,
            "to": [addr],
            "subject": subject,
            "html": html_body,
            "tags": [{"name": "template_type", "value": template_type}],
        })

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://api.resend.com/emails/batch",
                json=batch_payload,
                headers=headers,
            )
            data = resp.json()

            if resp.status_code == 200:
                email_ids = [item.get("id", "") for item in data] if isinstance(data, list) else [data.get("id", "")]
                return {
                    "success": True,
                    "total": len(recipients),
                    "sent": len(email_ids),
                    "failed": len(recipients) - len(email_ids),
                    "email_ids": email_ids,
                    "message": f"Successfully sent {len(email_ids)}/{len(recipients)} emails via Resend Batch API",
                }
            else:
                return {
                    "success": False,
                    "error": data.get("message", f"HTTP {resp.status_code}"),
                    "total": len(recipients),
                    "sent": 0,
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "total": len(recipients),
            "sent": 0,
        }


async def get_email_tracking_impl(email_id: str) -> dict:
    """
    通过 Resend API 获取邮件追踪信息。
    """
    if not RESEND_API_KEY:
        return {
            "success": False,
            "error": "RESEND_API_KEY not set.",
            "hint": "Get your free API key at https://resend.com/api-keys",
        }

    headers = {"Authorization": f"Bearer {RESEND_API_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"https://api.resend.com/emails/{email_id}", headers=headers)
            data = resp.json()

            if resp.status_code == 200:
                return {
                    "success": True,
                    "email_id": email_id,
                    "status": data.get("status", "unknown"),
                    "to": data.get("to", []),
                    "subject": data.get("subject", ""),
                    "created_at": data.get("created_at", ""),
                    "last_event": data.get("last_event", ""),
                }
            else:
                return {
                    "success": False,
                    "error": data.get("message", f"HTTP {resp.status_code}"),
                    "email_id": email_id,
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "email_id": email_id,
        }
