"""任务调度器 — 根据用户消息自动选择 persona 或 pipeline 模式。

收到用户消息后，用一次轻量 LLM 调用分析任务，决定：
- direct: 不需要特定 persona，裸模型直接回复
- single: 匹配到一个最合适的 persona
- pipeline: 需要多个 persona 协作，自动编排 pipeline
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class DispatchDecision:
    """调度决策结果"""
    mode: str  # "direct" | "single" | "pipeline"
    persona_name: str = ""  # single 模式下使用的 persona
    pipeline_stages: list[dict[str, str]] = field(default_factory=list)  # pipeline 模式
    reason: str = ""  # 决策理由


_DISPATCH_SYSTEM = "你是一个任务调度器，负责分析用户任务并选择最合适的执行方式。只输出 JSON，不要任何解释。"


def _build_dispatch_prompt(message: str, personas: list[dict[str, str]]) -> str:
    """构建调度 LLM 的 prompt。

    Args:
        message: 用户消息
        personas: 可用 persona 列表，每项包含 name 和 description
    """
    persona_list = "\n".join(
        f"- {p['name']}: {p['description']}" for p in personas
    )

    return f"""分析以下用户任务，从可用的 Agent 列表中选择最合适的执行方式。

## 可用 Agent
{persona_list}

## 用户任务
{message}

## 决策规则
1. 如果任务简单（闲聊、简单问答、翻译等），选 "direct"
2. 如果任务明确属于某个 Agent 的专长，选 "single"
3. 如果任务复杂，需要多个 Agent 协作（如：先调研再编码再审查），选 "pipeline"
4. pipeline 的 stages 按执行顺序排列，每个 stage 指定 persona 和该阶段的具体任务

## 输出格式（严格 JSON）
单 Agent 示例:
{{"mode":"single","persona":"coder","reason":"代码开发任务"}}

多 Agent 协作示例:
{{"mode":"pipeline","stages":[{{"persona":"researcher","task":"调研技术方案"}},{{"persona":"coder","task":"实现代码"}},{{"persona":"reviewer","task":"审查代码质量"}}],"reason":"复杂开发任务需要多阶段协作"}}

直接回复示例:
{{"mode":"direct","reason":"简单问答"}}"""


def parse_dispatch_response(text: str) -> DispatchDecision:
    """解析 LLM 返回的调度决策 JSON。"""
    # 尝试提取 JSON
    text = text.strip()
    if text.startswith("```"):
        # 去掉 markdown code block
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 尝试从文本中提取第一个 JSON 对象
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                logger.warning("Dispatcher: 无法解析 LLM 响应，fallback to direct")
                return DispatchDecision(mode="direct", reason="parse error")
        else:
            return DispatchDecision(mode="direct", reason="parse error")

    mode = data.get("mode", "direct")
    reason = data.get("reason", "")

    if mode == "single":
        persona = data.get("persona", "")
        return DispatchDecision(mode="single", persona_name=persona, reason=reason)
    elif mode == "pipeline":
        stages = data.get("stages", [])
        return DispatchDecision(mode="pipeline", pipeline_stages=stages, reason=reason)
    else:
        return DispatchDecision(mode="direct", reason=reason)


async def dispatch_task(
    message: str,
    personas: list[dict[str, str]],
    provider: Any,
    model: str,
) -> DispatchDecision:
    """调度入口：分析用户消息，决定执行方式。

    Args:
        message: 用户消息内容
        personas: 可用 persona 列表 [{"name": ..., "description": ...}]
        provider: LLM provider
        model: 模型名称

    Returns:
        DispatchDecision
    """
    if not personas:
        return DispatchDecision(mode="direct", reason="no personas available")

    # 只有一个 persona 时，简化判断
    if len(personas) == 1:
        return DispatchDecision(
            mode="single",
            persona_name=personas[0]["name"],
            reason=f"仅有一个可用 Agent: {personas[0]['name']}",
        )

    prompt = _build_dispatch_prompt(message, personas)

    try:
        response = await provider.chat(
            messages=[
                {"role": "system", "content": _DISPATCH_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=0.0,
            max_tokens=512,
        )
        decision = parse_dispatch_response(response.content or "")

        # 验证 persona 名称有效
        valid_names = {p["name"] for p in personas}
        if decision.mode == "single" and decision.persona_name not in valid_names:
            logger.warning("Dispatcher: persona '{}' 不在可用列表中，fallback to direct",
                           decision.persona_name)
            return DispatchDecision(mode="direct", reason="invalid persona name")

        if decision.mode == "pipeline":
            # 过滤无效的 stage persona
            valid_stages = [s for s in decision.pipeline_stages if s.get("persona") in valid_names]
            if not valid_stages:
                return DispatchDecision(mode="direct", reason="no valid pipeline stages")
            decision.pipeline_stages = valid_stages

        logger.info("Dispatcher 决策: mode={} persona={} stages={} reason={}",
                     decision.mode, decision.persona_name,
                     len(decision.pipeline_stages), decision.reason)
        return decision

    except Exception:
        logger.exception("Dispatcher LLM 调用失败，fallback to direct")
        return DispatchDecision(mode="direct", reason="dispatcher error")
