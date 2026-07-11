# 外贸硅基军团 MCP Server v2.0

> 面向跨境电商和外贸企业的 AI Agent 工具集 — 从 Mock 升级为生产就绪架构

[![MCP Protocol](https://img.shields.io/badge/MCP-2025--03--26-blue)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-green)](https://python.org)
[![Version](https://img.shields.io/badge/version-2.0.0-orange)]()

## 概述

外贸硅基军团 MCP Server v2.0 是基于 MCP (Model Context Protocol) 协议的外贸工具服务，提供从客户发现到成交转化的全链路外贸能力。v2.0 从全 Mock 数据架构升级为生产就绪架构，引入确定性优先层、真实 API 对接、并行工具调用和成本控制机制。

### v2.0 核心改进

| 改进项 | 说明 |
|--------|------|
| **确定性优先层** | HS编码/国家代码/邮箱/电话等高频简单请求走规则表/正则，零LLM成本 |
| **真实API对接** | 邮件发送对接 Resend API、客户发现对接 Google Custom Search、供应商查找抓取阿里巴巴 |
| **并行工具调用** | `batch_execute` 工具支持 asyncio 并行执行多个独立调用 |
| **成本控制** | MAX_LOOPS 限制 + COST_BUDGET 预算 + Replan-not-retry 失败处理 |
| **Tool Use Examples** | 每个工具 docstring 包含 ≥2 个使用范例，提升AI模型选择准确性 |
| **PII自动脱敏** | 返回结果中的邮箱/电话自动脱敏 |
| **核心数据锚定** | 海关数据标注 `data_source: demo`，区分真实与演示数据 |

## 架构

```
┌──────────────────────────────────────────────────────┐
│                   MCP Client (AI)                     │
│         Claude / Cursor / CodeBuddy / 元宝            │
└──────────────────┬───────────────────────────────────┘
                   │ MCP Protocol (Streamable HTTP)
┌──────────────────▼───────────────────────────────────┐
│                  server.py (MCP协议层)                 │
│           工具注册 + Tool Use Examples + PII脱敏        │
├────────────┬──────────────┬──────────────────────────┤
│            │              │                          │
│  ┌─────────▼─────────┐  │  ┌──────────────────────┐ │
│  │ deterministic.py   │  │  │   batch_tools.py     │ │
│  │ (确定性优先层)      │  │  │  (并行调度层)         │ │
│  │ - HS编码验证        │  │  │ - asyncio 并行       │ │
│  │ - 国家代码映射      │  │  │ - MAX_LOOPS 控制    │ │
│  │ - 汇率缓存         │  │  │ - COST_BUDGET 预算  │ │
│  │ - 邮箱/电话验证     │  │  │ - Replan-not-retry  │ │
│  └───────────────────┘  │  └──────────────────────┘ │
│                         │                            │
│  ┌──────────────────────▼────────────────────────┐   │
│  │              tools/ (工具实现层)                │   │
│  ├──────────────┬──────────────┬─────────────────┤   │
│  │ email_tools  │customer_tools│  customs_tools  │   │
│  │ (Resend API) │(Google CSE)  │  (Demo模式)     │   │
│  ├──────────────┼──────────────┼─────────────────┤   │
│  │whatsapp_tools│supplier_tools│                 │   │
│  │  (Demo模式)  │ (Alibaba)    │                 │   │
│  └──────────────┴──────────────┴─────────────────┘   │
└──────────────────────────────────────────────────────┘
```

## 文件结构

```
github_repo/
├── server.py              # 主MCP Server入口 (16个工具 + 2个资源)
├── deterministic.py       # 确定性优先层 (正则/查表/缓存)
├── batch_tools.py         # 并行工具调用 + 成本控制
├── tools/
│   ├── __init__.py
│   ├── email_tools.py     # 邮件工具 (Resend API)
│   ├── customer_tools.py  # 客户发现 (Google CSE)
│   ├── customs_tools.py   # 海关数据 (Demo)
│   ├── whatsapp_tools.py  # WhatsApp (Demo)
│   └── supplier_tools.py  # 供应商查找 (Alibaba)
├── requirements.txt
├── mcp.json               # MCP协议元数据
├── Dockerfile
├── LICENSE
└── README.md
```

## 工具列表

### 业务工具 (11个)

| 工具名 | 功能 | 数据源 | 需要 API Key |
|--------|------|--------|-------------|
| `discover_customers` | 发现潜在外贸客户 | Google Custom Search | ✅ |
| `search_company_info` | 查询公司详细信息 | Google Custom Search | ✅ |
| `send_email` | 发送外贸开发信 | Resend API | ✅ |
| `batch_send_emails` | 批量发送邮件 | Resend Batch API | ✅ |
| `get_email_tracking` | 邮件追踪数据 | Resend API | ✅ |
| `send_whatsapp_message` | 发送WhatsApp消息 | Demo | ❌ |
| `send_whatsapp_product_card` | 发送产品卡片 | Demo | ❌ |
| `get_whatsapp_message_status` | WhatsApp消息状态 | Demo | ❌ |
| `query_import_data` | 进口海关数据 | Demo | ❌ |
| `query_export_data` | 出口海关数据 | Demo | ❌ |
| `find_suppliers_by_product` | 供应商查找 | Alibaba.com | ❌ |

### 确定性工具 (4个) — 零LLM成本

| 工具名 | 功能 |
|--------|------|
| `validate_hs_code_tool` | HS编码格式验证 |
| `lookup_country_code` | 国家代码中英文/ISO互查 |
| `validate_email_tool` | 邮箱格式验证 |
| `validate_phone_tool` | 国际电话号码验证 |

### 并行调度工具 (1个)

| 工具名 | 功能 |
|--------|------|
| `batch_execute` | 并行执行多个工具调用，含成本控制 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 邮件发送 (Resend — 免费3000封/月)
export RESEND_API_KEY="re_xxxxxxxxxxxx"
export RESEND_FROM_EMAIL="your-verified@yourdomain.com"
# 获取: https://resend.com/api-keys

# 客户发现 (Google Custom Search — 免费100次/天)
export GOOGLE_SEARCH_API_KEY="your-api-key"
export GOOGLE_SEARCH_CSE_ID="your-cse-id"
# 获取: https://developers.google.com/custom-search/v1/overview
# 创建CSE: https://programmablesearchengine.google.com/

# 成本控制 (可选)
export MAX_LOOPS=5            # 每轮最大工具调用数
export COST_BUDGET=0.10       # 每轮成本预算上限(USD)，0或空=无限制
```

> **注意**: 未配置 API Key 时，对应工具会返回引导信息而非崩溃。确定性工具和 Demo 工具无需配置。

### 3. 启动服务

```bash
python server.py
# 服务启动在 http://localhost:8000/mcp
```

### 4. MCP 客户端配置

```json
{
  "mcpServers": {
    "silicon-army": {
      "url": "http://localhost:8000/mcp",
      "type": "streamable-http"
    }
  }
}
```

## 确定性优先层

确定性优先层在调用真实工具前先检查是否能通过规则/正则/查表直接回答：

```
用户请求 → 确定性检查 → 命中？→ 直接返回(零成本)
                       ↓ 未命中
                    调用真实工具/API
```

- **HS编码验证**: 正则匹配 4-10 位数字，自动去除点号/空格
- **国家代码查询**: 50+ 常用国家中英文/ISO2/ISO3 互查，O(1) 查表
- **邮箱格式验证**: RFC 兼容正则
- **电话格式验证**: E.164 国际格式 + 国家代码提取
- **汇率缓存**: 从 `open.er-api.com` 免费获取，1小时本地缓存

## 并行工具调用

使用 `batch_execute` 工具并行执行多个独立调用：

```python
# 同时查询进口数据 + 查找供应商 + 搜索客户
batch_execute(calls=[
    {"tool": "query_import_data", "arguments": {"hs_code": "854140", "country": "德国"}},
    {"tool": "find_suppliers_by_product", "arguments": {"product_keyword": "LED lighting"}},
    {"tool": "discover_customers", "arguments": {"keyword": "LED lighting", "market": "德国"}}
])
```

**成本控制机制**:
- `MAX_LOOPS`: 限制每轮工具调用数（默认5）
- `COST_BUDGET`: 限制每轮预估成本（默认无限制）
- `Replan-not-retry`: 步骤失败时返回当前状态 + 重新规划建议，而非盲目重试

## PII 脱敏

返回结果中的邮箱和电话号码自动脱敏：
- 邮箱: `contact@acme.com` → `c***@acme.com`
- 电话: `+8613800138000` → `+86****00`

## Docker 部署

```bash
docker build -t silicon-army-mcp .
docker run -p 8000:8000 \
  -e RESEND_API_KEY="re_xxx" \
  -e RESEND_FROM_EMAIL="noreply@yourdomain.com" \
  -e GOOGLE_SEARCH_API_KEY="xxx" \
  -e GOOGLE_SEARCH_CSE_ID="xxx" \
  silicon-army-mcp
```

## 使用 MCP Inspector 测试

```bash
npx -y @modelcontextprotocol/inspector
# 连接到 http://localhost:8000/mcp
```

## 环境变量一览

| 变量名 | 用途 | 必需 | 默认值 |
|--------|------|------|--------|
| `RESEND_API_KEY` | Resend 邮件 API | 邮件功能必需 | - |
| `RESEND_FROM_EMAIL` | 发件人邮箱 | 否 | `onboarding@resend.dev` |
| `GOOGLE_SEARCH_API_KEY` | Google CSE API Key | 客户发现必需 | - |
| `GOOGLE_SEARCH_CSE_ID` | Google CSE Engine ID | 客户发现必需 | - |
| `WHATSAPP_TOKEN` | WhatsApp Business API (预留) | 否 | - |
| `WHATSAPP_PHONE_ID` | WhatsApp Phone ID (预留) | 否 | - |
| `MAX_LOOPS` | 每轮最大工具调用数 | 否 | 5 |
| `COST_BUDGET` | 每轮成本预算(USD) | 否 | 无限制 |

## 适用场景

- 🎯 **跨境电商客户开发**: AI自动发现潜在买家 → 发送开发信 → 追踪 → 跟进
- 📊 **海关数据分析**: 进出口数据查询、市场趋势分析、竞品监控
- 📧 **多渠道营销触达**: 邮件(Resend) + WhatsApp 双渠道，批量发送 + 追踪
- 🔍 **供应商查找**: 按产品关键词从阿里巴巴筛选供应商
- ⚡ **高效并行查询**: 一次调用同时执行多个独立工具，降低延迟

## 技术架构

- **框架**: FastMCP (Python) — MCP 2025-03-26 协议
- **传输**: Streamable HTTP
- **并行**: asyncio + 信号量(并发度5)
- **缓存**: 汇率本地缓存(TTL 1小时)
- **安全**: PII自动脱敏 + 环境变量管理密钥
- **部署**: Docker 容器化

## License

MIT License - 详见 [LICENSE](LICENSE)

## 关于

**杭州云旅科技有限公司** — 专注AI+外贸领域的智能体产品研发

- 邮箱: wxy13336021626@foxmail.com
- 品牌矩阵: 云旅AI（公司品牌）/ 外贸硅基军团（产品线）/ 百雀AI（产品名）
