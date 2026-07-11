"""
并行工具调用支持 (Batch Tools)
支持同时执行多个独立工具调用，降低整体延迟。
"""

import asyncio
from typing import Any, Callable

# 最大并行度
MAX_CONCURRENCY = 5


async def execute_batch(
    tool_registry: dict[str, Callable],
    calls: list[dict],
    max_loops: int = 5,
    cost_budget: float | None = None,
    cost_per_call: float = 0.01,
) -> dict:
    """
    并行执行多个独立工具调用。

    Args:
        tool_registry: 工具名 -> 可调用函数的映射
        calls: 调用列表, 每项 {"tool": "tool_name", "arguments": {...}}
        max_loops: 每轮最多工具调用次数（成本控制）
        cost_budget: 总成本预算上限（可选），None表示无限制
        cost_per_call: 每次工具调用的估算成本（默认$0.01）
        replan_on_failure: 步骤失败时是否返回重新规划建议

    Returns:
        {
            "results": [...],
            "total_calls": int,
            "succeeded": int,
            "failed": int,
            "estimated_cost": float,
            "budget_exceeded": bool,
            "replan_hint": str | None,
        }

    Examples:
        >>> calls = [
        ...     {"tool": "query_import_data", "arguments": {"hs_code": "854140", "country": "德国"}},
        ...     {"tool": "find_suppliers_by_product", "arguments": {"product_keyword": "LED lighting"}},
        ... ]
        >>> result = await execute_batch(registry, calls)
    """
    # 成本控制: 检查调用数量
    total_calls = len(calls)
    if total_calls > max_loops:
        return {
            "results": [],
            "total_calls": total_calls,
            "succeeded": 0,
            "failed": 0,
            "estimated_cost": 0,
            "budget_exceeded": False,
            "max_loops_exceeded": True,
            "replan_hint": (
                f"请求 {total_calls} 次工具调用超过单轮上限 {max_loops} 次。"
                f"建议: 1) 拆分为多轮调用; 2) 使用更精确的查询参数减少调用; 3) 合并相似查询。"
            ),
        }

    # 成本控制: 检查预算
    estimated_cost = total_calls * cost_per_call
    budget_exceeded = cost_budget is not None and estimated_cost > cost_budget

    if budget_exceeded:
        return {
            "results": [],
            "total_calls": total_calls,
            "succeeded": 0,
            "failed": 0,
            "estimated_cost": estimated_cost,
            "budget_exceeded": True,
            "max_loops_exceeded": False,
            "replan_hint": (
                f"预估成本 ${estimated_cost:.2f} 超出预算 ${cost_budget:.2f}。"
                f"建议: 1) 减少调用次数; 2) 调整 cost_budget 参数; 3) 使用确定性优先层处理简单查询。"
            ),
        }

    # 信号量限制并发
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def call_one(call: dict) -> dict:
        async with semaphore:
            tool_name = call.get("tool", "")
            arguments = call.get("arguments", {})

            if tool_name not in tool_registry:
                return {
                    "tool": tool_name,
                    "success": False,
                    "error": f"Unknown tool: {tool_name}",
                    "replan_hint": f"工具 '{tool_name}' 不存在。请检查工具名拼写或使用 list_tools 查看可用工具。",
                }

            try:
                func = tool_registry[tool_name]
                # 支持同步和异步函数
                if asyncio.iscoroutinefunction(func):
                    result = await func(**arguments)
                else:
                    result = func(**arguments)
                return {"tool": tool_name, "success": True, "data": result}
            except Exception as e:
                return {
                    "tool": tool_name,
                    "success": False,
                    "error": str(e),
                    "replan_hint": (
                        f"工具 '{tool_name}' 执行失败: {e}。"
                        f"建议: 检查参数是否正确，或尝试简化查询后重新规划。"
                    ),
                }

    # 并行执行所有调用
    results = await asyncio.gather(*[call_one(c) for c in calls])

    succeeded = sum(1 for r in results if r.get("success"))
    failed = sum(1 for r in results if not r.get("success"))

    # Replan-not-retry: 如果有失败，生成重新规划建议
    replan_hint = None
    if failed > 0:
        failed_tools = [r["tool"] for r in results if not r.get("success")]
        # 收集各失败的具体hint
        hints = [r.get("replan_hint", "") for r in results if not r.get("success") and r.get("replan_hint")]
        replan_hint = (
            f"{failed}/{total_calls} 个工具调用失败 ({', '.join(failed_tools)})。"
            + (" ".join(hints) if hints else "建议: 检查参数后重新规划调用策略。")
        )

    return {
        "results": results,
        "total_calls": total_calls,
        "succeeded": succeeded,
        "failed": failed,
        "estimated_cost": estimated_cost,
        "budget_exceeded": False,
        "max_loops_exceeded": False,
        "replan_hint": replan_hint,
    }
