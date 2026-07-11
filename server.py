"""
外贸硅基军团 MCP Server (Production-Ready)
使用 FastMCP 框架构建 MCP 协议服务

架构分层:
  1. 确定性优先层 (deterministic.py) — 规则/正则/查表，零LLM成本
  2. 工具实现层 (tools/) — 真实API对接 / Demo数据
  3. 并行调度层 (batch_tools.py) — asyncio 并行执行 + 成本控制
  4. MCP协议层 (server.py) — 工具注册 + Streamable HTTP 传输

环境变量:
  RESEND_API_KEY         — Resend邮件API密钥 (https://resend.com/api-keys)
  RESEND_FROM_EMAIL      — 发件人邮箱地址 (默认: onboarding@resend.dev)
  GOOGLE_SEARCH_API_KEY  — Google Custom Search API密钥
  GOOGLE_SEARCH_CSE_ID   — Google Custom Search Engine ID
  MAX_LOOPS              — 每轮最大工具调用数 (默认: 5)
  COST_BUDGET            — 每轮成本预算上限USD (默认: 无限制)
"""

import os
import asyncio
import functools
from mcp.server.fastmcp import FastMCP

from deterministic import try_deterministic, validate_hs_code, lookup_country, validate_email, validate_phone, mask_pii
from batch_tools import execute_batch
from tools.email_tools import send_email_impl, batch_send_emails_impl, get_email_tracking_impl
from tools.customer_tools import discover_customers_impl, search_company_info_impl
from tools.customs_tools import query_import_data_impl, query_export_data_impl
from tools.whatsapp_tools import (
    send_whatsapp_message_impl,
    send_whatsapp_product_card_impl,
    get_whatsapp_message_status_impl,
)
from tools.supplier_tools import find_suppliers_by_product_impl

# ──────────────────────────────────────────────
# 成本控制参数
# ──────────────────────────────────────────────
MAX_LOOPS = int(os.getenv("MAX_LOOPS", "5"))
COST_BUDGET = float(os.getenv("COST_BUDGET", "0")) if os.getenv("COST_BUDGET") else None

# 创建 MCP Server 实例
mcp = FastMCP(
    "SiliconArmy-ForeignTrade",
    json_response=True,
    dependencies=["fastapi", "uvicorn", "httpx", "resend"],
)


# ──────────────────────────────────────────────
# 装饰器: 确定性优先 + PII脱敏
# ──────────────────────────────────────────────
def deterministic_wrapper(tool_name: str):
    """
    工具装饰器: 先尝试确定性回答，再走真实实现。
    对返回结果中的PII自动脱敏。
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 1. 确定性优先检查
            det_result = try_deterministic(tool_name, kwargs)
            if det_result is not None:
                return {"success": True, "source": "deterministic", "data": det_result}

            # 2. 走真实实现
            result = await func(*args, **kwargs)

            # 3. PII脱敏 (对返回结果中的邮箱/电话做脱敏)
            if isinstance(result, dict):
                _mask_pii_in_dict(result)

            return result
        return wrapper
    return decorator


def _mask_pii_in_dict(d: dict) -> None:
    """递归对字典中的PII字段脱敏"""
    pii_keys = {"email", "contact", "to", "to_address", "phone", "phone_number"}
    for k, v in d.items():
        if isinstance(v, str) and k in pii_keys:
            d[k] = mask_pii(v)
        elif isinstance(v, dict):
            _mask_pii_in_dict(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    _mask_pii_in_dict(item)


# ═══════════════════════════════════════════════
# 工具注册
# ═══════════════════════════════════════════════

@mcp.tool()
async def discover_customers(
    keyword: str,
    market: str,
    product_info: str = "",
    limit: int = 10,
) -> dict:
    """
    发现潜在外贸客户 — 使用 Google Custom Search 搜索进口商/分销商。

    Args:
        keyword: 产品关键词 (如 "LED lighting")
        market: 目标市场国家 (如 "德国" 或 "Germany")
        product_info: 产品描述（可选，用于细化搜索）
        limit: 返回数量上限，默认10

    Returns:
        包含客户列表的字典，每个客户含公司名/网站/邮箱/电话等

    Examples:
        # 场景1: 搜索德国LED照明进口商
        discover_customers(keyword="LED lighting", market="德国")

        # 场景2: 搜索美国太阳能板分销商，限制5条
        discover_customers(keyword="solar panel", market="USA", product_info="monocrystalline 400W", limit=5)
    """
    return await discover_customers_impl(keyword, market, product_info, limit)


@mcp.tool()
async def search_company_info(company_name: str) -> dict:
    """
    查询公司详细信息 — 通过 Google 搜索获取公司网站/联系方式/简介。

    Args:
        company_name: 公司名称 (如 "Siemens AG")

    Returns:
        公司详情字典，含网站/域名/邮箱/描述等

    Examples:
        # 场景1: 查询某德国公司信息
        search_company_info(company_name="Siemens AG")

        # 场景2: 查询某美国公司
        search_company_info(company_name="ACME Industries Inc")
    """
    return await search_company_info_impl(company_name)


@mcp.tool()
async def send_email(
    to_address: str,
    subject: str,
    content: str,
    template_type: str = "dev_letter",
) -> dict:
    """
    发送外贸开发信 — 通过 Resend API 真实发送邮件。

    需要: 环境变量 RESEND_API_KEY 和 RESEND_FROM_EMAIL

    Args:
        to_address: 收件人邮箱 (如 "buyer@company.com")
        subject: 邮件主题 (如 "Best Price for LED Lighting from China")
        content: 邮件内容，支持HTML (如 "<strong>Our products...</strong>")
        template_type: 模板类型，可选值:
            - "dev_letter" (默认): 开发信模板
            - "follow_up": 跟进邮件模板
            - "product_intro": 产品介绍模板

    Returns:
        发送结果，含 email_id / status / tracking_url

    Examples:
        # 场景1: 发送标准开发信
        send_email(to_address="buyer@acme.com", subject="LED Lighting Supplier Inquiry", content="<p>We are a manufacturer of LED lighting...</p>")

        # 场景2: 使用产品介绍模板发送
        send_email(to_address="info@company.de", subject="Product Introduction", content="<p>Product details here</p>", template_type="product_intro")
    """
    return await send_email_impl(to_address, subject, content, template_type)


@mcp.tool()
async def batch_send_emails(
    recipients: list,
    subject: str,
    content: str,
    template_type: str = "dev_letter",
) -> dict:
    """
    批量发送邮件 — 通过 Resend Batch API 一次性发送多封邮件。

    需要: 环境变量 RESEND_API_KEY

    Args:
        recipients: 收件人列表，每项为 {"address": "...", "name": "..."} 或纯邮箱字符串
        subject: 邮件主题
        content: 邮件内容，支持HTML
        template_type: 模板类型 (dev_letter/follow_up/product_intro)

    Returns:
        批量发送统计，含 total/sent/failed/email_ids

    Examples:
        # 场景1: 批量发送给3个收件人
        batch_send_emails(
            recipients=[
                {"address": "buyer1@acme.com", "name": "John"},
                {"address": "buyer2@acme.com", "name": "Sarah"},
                {"address": "buyer3@acme.com", "name": "Mike"}
            ],
            subject="Special Offer: LED Lighting",
            content="<p>Limited time offer...</p>"
        )

        # 场景2: 纯邮箱地址列表（无姓名）
        batch_send_emails(
            recipients=["a@example.com", "b@example.com"],
            subject="Product Update",
            content="<p>Check our new products</p>",
            template_type="product_intro"
        )
    """
    return await batch_send_emails_impl(recipients, subject, content, template_type)


@mcp.tool()
async def get_email_tracking(email_id: str) -> dict:
    """
    获取邮件追踪信息 — 通过 Resend API 查询邮件状态。

    需要: 环境变量 RESEND_API_KEY

    Args:
        email_id: 邮件ID (从 send_email 或 batch_send_emails 返回结果获取)

    Returns:
        追踪数据，含 status/created_at/last_event 等

    Examples:
        # 场景1: 查询单封邮件状态
        get_email_tracking(email_id="a1b2c3d4-1234-5678-abcd-1234567890ab")

        # 场景2: 查询批量发送中某一封的状态
        get_email_tracking(email_id="09876543-abcd-ef01-2345-678901234567")
    """
    return await get_email_tracking_impl(email_id)


@mcp.tool()
async def send_whatsapp_message(
    phone_number: str,
    message: str,
    message_type: str = "text",
) -> dict:
    """
    发送 WhatsApp 消息 (Demo模式 — 返回模拟结果)。

    注意: 当前为demo模式。配置 WHATSAPP_TOKEN 和 WHATSAPP_PHONE_ID 后可升级为真实发送。

    Args:
        phone_number: 电话号码，格式: +国家代码+号码 (如 "+8613800138000" 或 "whatsapp:+491701234567")
        message: 消息内容
        message_type: 消息类型，可选值:
            - "text" (默认): 纯文本消息
            - "image": 图片消息
            - "document": 文档消息

    Returns:
        发送结果，含 message_id / status / data_source

    Examples:
        # 场景1: 发送文本消息
        send_whatsapp_message(phone_number="+491701234567", message="Hello! We are a LED lighting manufacturer from China.")

        # 场景2: 使用 whatsapp: 前缀格式
        send_whatsapp_message(phone_number="whatsapp:+8613800138000", message="Product catalog attached", message_type="document")
    """
    return await send_whatsapp_message_impl(phone_number, message, message_type)


@mcp.tool()
async def send_whatsapp_product_card(
    phone_number: str,
    product_name: str,
    product_image: str = "",
    price: str = "",
    description: str = "",
) -> dict:
    """
    发送产品卡片到 WhatsApp (Demo模式)。

    Args:
        phone_number: 电话号码 (如 "+491701234567")
        product_name: 产品名称 (如 "LED Panel Light 60x60")
        product_image: 产品图片 URL (可选，如 "https://example.com/product.jpg")
        price: 价格 (可选，如 "$5.99/pc")
        description: 产品描述 (可选)

    Returns:
        发送结果，含 message_id / card 内容 / data_source

    Examples:
        # 场景1: 发送带完整信息的产品卡片
        send_whatsapp_product_card(
            phone_number="+491701234567",
            product_name="LED Panel Light 60x60",
            product_image="https://example.com/panel.jpg",
            price="$5.99/pc",
            description="40W, 4000K, CE certified, 5-year warranty"
        )

        # 场景2: 仅发送产品名和价格（无图片）
        send_whatsapp_product_card(
            phone_number="+8613800138000",
            product_name="Solar Panel 400W",
            price="$120/pc"
        )
    """
    return await send_whatsapp_product_card_impl(phone_number, product_name, product_image, price, description)


@mcp.tool()
async def get_whatsapp_message_status(message_id: str) -> dict:
    """
    获取 WhatsApp 消息状态 (Demo模式)。

    Args:
        message_id: 消息ID (从 send_whatsapp_message 或 send_whatsapp_product_card 返回结果获取)

    Returns:
        消息状态，含 status / delivered_at / read

    Examples:
        # 场景1: 查询消息发送状态
        get_whatsapp_message_status(message_id="wa_a1b2c3d4e5f6")

        # 场景2: 查询产品卡片消息状态
        get_whatsapp_message_status(message_id="wa_card_0987654321ab")
    """
    return await get_whatsapp_message_status_impl(message_id)


@mcp.tool()
async def query_import_data(
    hs_code: str,
    country: str,
    time_range: str = "last_year",
) -> dict:
    """
    查询进口海关数据 (Demo模式 — 返回结构化示例数据)。

    数据源标注 "data_source: demo"，后续可对接真实海关数据API。

    Args:
        hs_code: HS编码 (4-10位数字，如 "854140" 或 "85414000")
        country: 目的国 (如 "德国" 或 "Germany" 或 "DE")
        time_range: 时间范围，可选值:
            - "last_month": 最近1个月
            - "last_quarter": 最近1个季度
            - "last_year" (默认): 最近1年

    Returns:
        进口数据，含进口量/金额/主要出口国/月度趋势等

    Examples:
        # 场景1: 查询德国去年LED芯片进口数据
        query_import_data(hs_code="854140", country="德国")

        # 场景2: 查询美国最近一季度的太阳能板进口数据
        query_import_data(hs_code="85414300", country="USA", time_range="last_quarter")
    """
    return await query_import_data_impl(hs_code, country, time_range)


@mcp.tool()
async def query_export_data(
    hs_code: str,
    country: str,
    time_range: str = "last_year",
) -> dict:
    """
    查询出口海关数据 (Demo模式 — 返回结构化示例数据)。

    数据源标注 "data_source: demo"，后续可对接真实海关数据API。

    Args:
        hs_code: HS编码 (4-10位数字)
        country: 出口国
        time_range: 时间范围 (last_month/last_quarter/last_year)

    Returns:
        出口数据，含出口量/金额/主要进口国/月度趋势等

    Examples:
        # 场景1: 查询中国去年LED芯片出口数据
        query_export_data(hs_code="854140", country="中国")

        # 场景2: 查询越南最近一个月的纺织品出口
        query_export_data(hs_code="6109", country="越南", time_range="last_month")
    """
    return await query_export_data_impl(hs_code, country, time_range)


@mcp.tool()
async def find_suppliers_by_product(
    product_keyword: str,
    country: str = "China",
) -> list:
    """
    按产品关键词查找供应商 — 抓取阿里巴巴公开搜索页面。

    无需API Key，直接抓取 Alibaba.com 搜索结果页面解析供应商信息。

    Args:
        product_keyword: 产品关键词 (如 "LED lighting" 或 "solar panel")
        country: 供应商所在国家 (默认: "China")

    Returns:
        供应商列表，每项含公司名/位置/来源/阿里巴巴链接

    Examples:
        # 场景1: 查找中国LED照明供应商
        find_suppliers_by_product(product_keyword="LED lighting")

        # 场景2: 查找越南纺织品供应商
        find_suppliers_by_product(product_keyword="cotton fabric", country="Vietnam")
    """
    return await find_suppliers_by_product_impl(product_keyword, country)


# ═══════════════════════════════════════════════
# 确定性工具 (无需LLM，直接规则回答)
# ═══════════════════════════════════════════════

@mcp.tool()
def validate_hs_code_tool(code: str) -> dict:
    """
    验证HS编码格式 — 确定性工具，零LLM成本。

    Args:
        code: HS编码 (可能含点号/空格，如 "8541.40" 或 "854140")

    Returns:
        验证结果，含 valid/normalized/length/level

    Examples:
        # 场景1: 验证6位HS编码
        validate_hs_code_tool(code="854140")

        # 场景2: 验证带点号的编码（自动去除点号）
        validate_hs_code_tool(code="8541.40.00")
    """
    return validate_hs_code(code)


@mcp.tool()
def lookup_country_code(query: str) -> dict:
    """
    查询国家代码 — 确定性工具，支持中英文/ISO2/ISO3互查。

    Args:
        query: 国家名称或代码 (如 "德国" / "Germany" / "DE" / "DEU")

    Returns:
        国家信息，含 cn/iso2/iso3/en

    Examples:
        # 场景1: 中文查国家代码
        lookup_country_code(query="德国")

        # 场景2: ISO2代码反查中文名
        lookup_country_code(query="US")
    """
    return lookup_country(query)


@mcp.tool()
def validate_email_tool(email: str) -> dict:
    """
    验证邮箱格式 — 确定性工具。

    Args:
        email: 邮箱地址 (如 "contact@acme.com")

    Returns:
        验证结果，含 valid/email

    Examples:
        # 场景1: 验证有效邮箱
        validate_email_tool(email="buyer@company.com")

        # 场景2: 验证无效邮箱
        validate_email_tool(email="bad-email")
    """
    return validate_email(email)


@mcp.tool()
def validate_phone_tool(phone: str) -> dict:
    """
    验证国际电话号码格式 — 确定性工具。

    Args:
        phone: 电话号码，支持 E.164 格式或 whatsapp: 前缀

    Returns:
        验证结果，含 valid/phone/country_code

    Examples:
        # 场景1: 验证中国手机号
        validate_phone_tool(phone="+8613800138000")

        # 场景2: 验证 whatsapp 前缀格式
        validate_phone_tool(phone="whatsapp:+491701234567")
    """
    return validate_phone(phone)


# ═══════════════════════════════════════════════
# 并行批量工具调用
# ═══════════════════════════════════════════════

@mcp.tool()
async def batch_execute(
    calls: list,
    max_loops: int = 0,
    cost_budget: float = 0,
) -> dict:
    """
    并行执行多个独立工具调用 — 降低整体延迟，含成本控制。

    内置成本控制:
    - MAX_LOOPS: 每轮最多工具调用数 (环境变量 MAX_LOOPS，默认5)
    - COST_BUDGET: 成本预算上限USD (环境变量 COST_BUDGET，默认无限制)
    - Replan-not-retry: 步骤失败时返回当前状态和重新规划建议

    Args:
        calls: 调用列表，每项格式 {"tool": "工具名", "arguments": {...}}
        max_loops: 覆盖默认最大调用数 (0=使用环境变量默认值)
        cost_budget: 覆盖默认成本预算 (0=使用环境变量默认值)

    Returns:
        批量执行结果，含 results/total_calls/succeeded/failed/estimated_cost/replan_hint

    Examples:
        # 场景1: 同时查询进口数据和查找供应商
        batch_execute(calls=[
            {"tool": "query_import_data", "arguments": {"hs_code": "854140", "country": "德国"}},
            {"tool": "find_suppliers_by_product", "arguments": {"product_keyword": "LED lighting"}}
        ])

        # 场景2: 同时搜索客户 + 查询公司信息 + 查询出口数据
        batch_execute(calls=[
            {"tool": "discover_customers", "arguments": {"keyword": "LED lighting", "market": "德国"}},
            {"tool": "search_company_info", "arguments": {"company_name": "Siemens AG"}},
            {"tool": "query_export_data", "arguments": {"hs_code": "854140", "country": "中国"}}
        ])

        # 场景3: 自定义成本控制
        batch_execute(calls=[...], max_loops=3, cost_budget=0.05)
    """
    # 构建工具注册表
    tool_registry = {
        "discover_customers": discover_customers,
        "search_company_info": search_company_info,
        "send_email": send_email,
        "batch_send_emails": batch_send_emails,
        "get_email_tracking": get_email_tracking,
        "send_whatsapp_message": send_whatsapp_message,
        "send_whatsapp_product_card": send_whatsapp_product_card,
        "get_whatsapp_message_status": get_whatsapp_message_status,
        "query_import_data": query_import_data,
        "query_export_data": query_export_data,
        "find_suppliers_by_product": find_suppliers_by_product,
        "validate_hs_code_tool": validate_hs_code_tool,
        "lookup_country_code": lookup_country_code,
        "validate_email_tool": validate_email_tool,
        "validate_phone_tool": validate_phone_tool,
    }

    # 使用参数覆盖环境变量默认值
    effective_max_loops = max_loops if max_loops > 0 else MAX_LOOPS
    effective_budget = cost_budget if cost_budget > 0 else COST_BUDGET

    return await execute_batch(
        tool_registry=tool_registry,
        calls=calls,
        max_loops=effective_max_loops,
        cost_budget=effective_budget,
    )


# ═══════════════════════════════════════════════
# 资源 (Resources)
# ═══════════════════════════════════════════════

@mcp.resource("template:///{template_type}")
def get_email_template(template_type: str):
    """获取邮件模板"""
    templates = {
        "dev_letter": "Dear [Name],\n\nI am reaching out from Silicon Army. We specialize in [Product].\nWe'd love to explore a partnership.\n\nBest regards,\nSilicon Army Team",
        "follow_up": "Dear [Name],\n\nFollowing up on my previous email about [Product].\nWould you be available for a quick call?\n\nBest regards,\nSilicon Army Team",
        "product_intro": "Dear [Name],\n\nIntroducing our new [Product]:\n- Feature 1\n- Feature 2\n- Feature 3\n\nFor details, please visit our website.\n\nBest regards,\nSilicon Army Team",
    }
    return templates.get(template_type, "Template not found. Available: dev_letter, follow_up, product_intro")


@mcp.resource("guide:///{guide_type}")
def get_user_guide(guide_type: str):
    """获取用户指南"""
    guides = {
        "getting-started": "# Getting Started\n\n1. Configure environment variables (RESEND_API_KEY, GOOGLE_SEARCH_API_KEY)\n2. Start the server: python server.py\n3. Connect your MCP client to http://localhost:8000/mcp",
        "best-practices": "# Best Practices\n\n- Use batch_execute for parallel calls\n- Use deterministic tools (validate_hs_code_tool, etc.) for simple queries\n- Set MAX_LOOPS and COST_BUDGET for cost control\n- Always validate email/phone before sending",
        "troubleshooting": "# Troubleshooting\n\n- Email sending fails: Check RESEND_API_KEY\n- Customer search returns empty: Check GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CSE_ID\n- Alibaba search blocked: Try later or use Google Custom Search fallback\n- Rate limits: Reduce limit parameter or use batch with max_loops",
    }
    return guides.get(guide_type, "Guide not found. Available: getting-started, best-practices, troubleshooting")


# ═══════════════════════════════════════════════
# 启动服务器
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
