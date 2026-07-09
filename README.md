# 云旅AI外贸硅基军团 MCP Server

> 面向跨境电商和外贸企业的AI Agent工具集MCP服务

[![MCP Protocol](https://img.shields.io/badge/MCP-2025--03--26-blue)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-green)](https://python.org)

## 概述

云旅AI外贸硅基军团 MCP Server 是一个基于 MCP (Model Context Protocol) 协议的外贸工具服务，提供从客户发现到成交转化的全链路外贸能力。任何兼容MCP的AI客户端（如 Claude、CodeBuddy、Cursor、腾讯元宝等）均可一键接入。

## 工具列表

| 工具名 | 功能 | 关键参数 |
|--------|------|----------|
| `discover_customers` | 发现潜在外贸客户 | keyword, market, product_info, limit |
| `search_company_info` | 查询公司详细信息 | company_name |
| `send_email` | 发送外贸开发信 | to_address, subject, content, template_type |
| `batch_send_emails` | 批量发送邮件 | recipients, subject, content, template_type |
| `get_email_tracking` | 邮件追踪数据 | email_id |
| `send_whatsapp_message` | 发送WhatsApp消息 | phone_number, message, message_type |
| `send_whatsapp_product_card` | 发送产品卡片 | phone_number, product_name, price, description |
| `get_whatsapp_message_status` | WhatsApp消息状态 | message_id |
| `query_import_data` | 进口海关数据查询 | hs_code, country, time_range |
| `query_export_data` | 出口海关数据查询 | hs_code, country, time_range |
| `find_suppliers_by_product` | 供应商查找 | product_keyword, country |

## 快速开始

### 安装依赖

```bash
pip install "mcp[cli]" fastapi uvicorn
```

### 启动服务

```bash
# Streamable HTTP 模式（推荐，适合云托管）
python server.py

# 服务启动在 http://localhost:8000/mcp
```

### MCP客户端配置

在支持MCP的客户端中添加以下配置：

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

### 使用MCP Inspector测试

```bash
npx -y @modelcontextprotocol/inspector
# 连接到 http://localhost:8000/mcp
```

## 适用场景

- 🎯 **跨境电商客户开发**：AI自动发现潜在买家、发送开发信、跟进转化
- 📊 **海关数据分析**：进出口数据查询、市场趋势分析
- 📧 **多渠道营销触达**：邮件+WhatsApp双渠道，批量发送+追踪
- 🔍 **供应商查找**：按产品关键词筛选优质供应商

## 技术架构

- **框架**: FastMCP (Python)
- **协议**: MCP 2025-03-26
- **传输**: Streamable HTTP / SSE
- **部署**: 支持 Docker 容器化部署

## Docker部署

```bash
docker build -t silicon-army-mcp .
docker run -p 8000:8000 silicon-army-mcp
```

## 关于

**杭州云旅科技有限公司** - 专注AI+外贸领域的智能体产品研发

- 邮箱: wxy13336021626@foxmail.com
- 品牌矩阵: 云旅AI（公司品牌）/ 外贸硅基军团（产品线）/ 百雀AI（产品名）

## License

MIT License - 详见 [LICENSE](LICENSE)
