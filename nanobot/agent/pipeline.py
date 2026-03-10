"""Multi-agent pipeline orchestrator for collaborative task execution."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from nanobot.agent.persona import AgentPersona, PersonaManager
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import ExecToolConfig
from nanobot.providers.base import LLMProvider


class AgentRole(str, Enum):
    """预定义的 Agent 角色"""
    PLANNER = "planner"  # 规划者：分解任务
    RESEARCHER = "researcher"  # 研究者：信息收集
    CODER = "coder"  # 编码者：代码实现
    REVIEWER = "reviewer"  # 审查者：代码审查
    TESTER = "tester"  # 测试者：测试验证
    INTEGRATOR = "integrator"  # 集成者：整合结果


@dataclass
class PipelineStage:
    """流水线阶段定义"""
    name: str
    role: AgentRole
    prompt_template: str
    tools: list[str] = field(default_factory=list)  # 允许使用的工具名称
    max_iterations: int = 10
    depends_on: list[str] = field(default_factory=list)  # 依赖的前置阶段
    persona: str | None = None  # 人格名称，None 则使用 role.value 作为默认人格


@dataclass
class PipelineContext:
    """流水线执行上下文"""
    task: str
    stage_results: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentPipeline:
    """
    多 Agent 流水线编排器
    
    每个 agent 拥有独立的人格（PERSONA.md）和持久化记忆（MEMORY.md），
    执行任务后自动整理经验，使 agent 随着使用越来越有经验。
    """

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        reasoning_effort: str | None = None,
        brave_api_key: str | None = None,
        web_proxy: str | None = None,
        exec_config: ExecToolConfig | None = None,
        restrict_to_workspace: bool = False,
    ):
        from nanobot.config.schema import ExecToolConfig
        
        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.brave_api_key = brave_api_key
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        
        self._running_pipelines: dict[str, asyncio.Task] = {}
        self._all_tools = self._build_all_tools()
        
        # 人格管理器 — 确保默认人格文件存在
        self.persona_manager = PersonaManager(workspace)
        self.persona_manager.ensure_default_personas()

    def _build_all_tools(self) -> ToolRegistry:
        """构建完整的工具集"""
        tools = ToolRegistry()
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        
        tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        tools.register(WriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        tools.register(EditFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))
        tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
            path_append=self.exec_config.path_append,
        ))
        tools.register(WebSearchTool(api_key=self.brave_api_key, proxy=self.web_proxy))
        tools.register(WebFetchTool(proxy=self.web_proxy))
        
        return tools

    def _build_stage_tools(self, allowed_tools: list[str]) -> ToolRegistry:
        """为特定阶段构建受限的工具集"""
        tools = ToolRegistry()
        
        for tool_name in allowed_tools:
            if tool := self._all_tools.get(tool_name):
                tools.register(tool)
        
        return tools

    def _get_stage_persona(self, stage: PipelineStage) -> AgentPersona:
        """获取阶段对应的人格，优先使用 stage.persona，否则用 role.value"""
        persona_name = stage.persona or stage.role.value
        return self.persona_manager.get(persona_name)

    def _build_stage_prompt(
        self,
        stage: PipelineStage,
        context: PipelineContext,
    ) -> str:
        """构建阶段提示词 — 包含人格定义、长期记忆和任务上下文"""
        persona = self._get_stage_persona(stage)
        parts: list[str] = []

        # 加载人格上下文（人格定义 + 长期记忆）
        persona_context = persona.get_full_context()
        if persona_context:
            parts.append(persona_context)
        else:
            # 没有人格文件时的 fallback
            parts.append(f"# Role: {stage.role.value.title()}\n")
            role_descriptions = {
                AgentRole.PLANNER: "你负责分析任务并制定详细的执行计划。将复杂任务分解为可执行的步骤。",
                AgentRole.RESEARCHER: "你负责收集信息和研究。使用搜索工具查找相关资料和最佳实践。",
                AgentRole.CODER: "你负责编写代码实现。根据计划和研究结果编写高质量的代码。",
                AgentRole.REVIEWER: "你负责代码审查。检查代码质量、安全性和最佳实践。",
                AgentRole.TESTER: "你负责测试验证。编写和执行测试，确保功能正确性。",
                AgentRole.INTEGRATOR: "你负责整合所有结果。汇总各阶段输出，生成最终交付物。",
            }
            parts.append(role_descriptions.get(stage.role, ""))
        
        # 运行时上下文
        from nanobot.agent.context import ContextBuilder
        runtime_ctx = ContextBuilder._build_runtime_context(None, None)
        parts.append(runtime_ctx)

        # workspace 信息
        parts.append(f"## Workspace\n{self.workspace}")
        
        # 任务描述
        parts.append(f"\n## Task\n{context.task}")
        
        # 前置阶段的结果
        if stage.depends_on:
            parts.append("\n## Previous Stage Results\n")
            for dep_stage in stage.depends_on:
                if result := context.stage_results.get(dep_stage):
                    parts.append(f"### {dep_stage}\n{result}\n")
        
        # 阶段特定指令
        parts.append(f"\n## Instructions\n{stage.prompt_template}")
        
        return "\n".join(parts)

    async def _execute_stage(
        self,
        stage: PipelineStage,
        context: PipelineContext,
        pipeline_id: str,
    ) -> str:
        """执行单个流水线阶段，完成后自动整理经验到长期记忆"""
        persona = self._get_stage_persona(stage)
        logger.info(
            "Pipeline [{}] executing stage '{}' (persona: '{}')",
            pipeline_id,
            stage.name,
            persona.name,
        )
        
        # 构建该阶段的工具集
        tools = self._build_stage_tools(stage.tools)
        
        # 构建提示词
        system_prompt = self._build_stage_prompt(stage, context)
        
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请开始执行 {stage.role.value} 的任务。"},
        ]
        
        # 执行 agent 循环
        iteration = 0
        final_result: str | None = None
        
        while iteration < stage.max_iterations:
            iteration += 1
            
            response = await self.provider.chat(
                messages=messages,
                tools=tools.get_definitions() if tools else [],
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                reasoning_effort=self.reasoning_effort,
            )
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in response.tool_calls
                ]
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": tool_call_dicts,
                })
                
                for tool_call in response.tool_calls:
                    logger.debug(
                        "Pipeline [{}] stage '{}' executing tool: {}",
                        pipeline_id,
                        stage.name,
                        tool_call.name,
                    )
                    result = await tools.execute(tool_call.name, tool_call.arguments)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": result,
                    })
            else:
                final_result = response.content
                break
        
        if final_result is None:
            final_result = f"Stage '{stage.name}' completed but no final response was generated."
        
        logger.info("Pipeline [{}] stage '{}' completed", pipeline_id, stage.name)
        
        # 异步整理经验到长期记忆（不阻塞主流程）
        asyncio.create_task(
            persona.consolidate_experience(
                messages=messages,
                provider=self.provider,
                model=self.model,
                task_summary=f"[Pipeline {pipeline_id}] Stage: {stage.name} | Task: {context.task}",
            )
        )
        
        return final_result

    async def execute(
        self,
        task: str,
        stages: list[PipelineStage],
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        on_stage_complete: Callable[[str, str], None] | None = None,
    ) -> str:
        """执行多 agent 流水线"""
        pipeline_id = str(uuid.uuid4())[:8]
        logger.info("Starting pipeline [{}] with {} stages", pipeline_id, len(stages))
        
        context = PipelineContext(task=task)
        
        try:
            for stage in stages:
                for dep in stage.depends_on:
                    if dep not in context.stage_results:
                        raise ValueError(
                            f"Stage '{stage.name}' depends on '{dep}' which hasn't been executed"
                        )
                
                result = await self._execute_stage(stage, context, pipeline_id)
                context.stage_results[stage.name] = result
                
                if on_stage_complete:
                    on_stage_complete(stage.name, result)
            
            final_report = self._generate_final_report(context, stages)
            
            logger.info("Pipeline [{}] completed successfully", pipeline_id)
            
            await self._announce_result(
                pipeline_id,
                task,
                final_report,
                {"channel": origin_channel, "chat_id": origin_chat_id},
                "ok",
            )
            
            return final_report
            
        except Exception as e:
            error_msg = f"Pipeline execution failed: {str(e)}"
            logger.error("Pipeline [{}] failed: {}", pipeline_id, e)
            
            await self._announce_result(
                pipeline_id,
                task,
                error_msg,
                {"channel": origin_channel, "chat_id": origin_chat_id},
                "error",
            )
            
            return error_msg

    def _generate_final_report(
        self,
        context: PipelineContext,
        stages: list[PipelineStage],
    ) -> str:
        """生成最终报告"""
        parts = [f"# Pipeline Execution Report\n\n## Task\n{context.task}\n"]
        
        parts.append("## Stage Results\n")
        for stage in stages:
            result = context.stage_results.get(stage.name, "No result")
            parts.append(f"### {stage.name} ({stage.role.value})\n{result}\n")
        
        return "\n".join(parts)

    async def _announce_result(
        self,
        pipeline_id: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
    ) -> None:
        """通知主 agent 流水线执行结果"""
        status_text = "completed successfully" if status == "ok" else "failed"
        
        announce_content = f"""[Multi-agent pipeline {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user."""
        
        msg = InboundMessage(
            channel="system",
            sender_id="pipeline",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
        )
        
        await self.bus.publish_inbound(msg)
        logger.debug("Pipeline [{}] announced result", pipeline_id)

    async def spawn_pipeline(
        self,
        task: str,
        stages: list[PipelineStage],
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
    ) -> str:
        """在后台启动流水线执行"""
        pipeline_id = str(uuid.uuid4())[:8]
        
        bg_task = asyncio.create_task(
            self.execute(task, stages, origin_channel, origin_chat_id)
        )
        self._running_pipelines[pipeline_id] = bg_task
        
        def _cleanup(_: asyncio.Task) -> None:
            self._running_pipelines.pop(pipeline_id, None)
        
        bg_task.add_done_callback(_cleanup)
        
        logger.info("Spawned pipeline [{}] with {} stages", pipeline_id, len(stages))
        return f"Multi-agent pipeline started (id: {pipeline_id}). I'll notify you when it completes."


# 预定义的流水线模板
def create_software_development_pipeline() -> list[PipelineStage]:
    """创建软件开发流水线"""
    return [
        PipelineStage(
            name="planning",
            role=AgentRole.PLANNER,
            prompt_template="分析需求，制定详细的开发计划。列出需要实现的功能模块和技术选型。",
            tools=["read_file", "list_dir"],
            max_iterations=5,
        ),
        PipelineStage(
            name="research",
            role=AgentRole.RESEARCHER,
            prompt_template="根据计划，研究相关技术和最佳实践。查找示例代码和文档。",
            tools=["web_search", "web_fetch"],
            max_iterations=8,
            depends_on=["planning"],
        ),
        PipelineStage(
            name="coding",
            role=AgentRole.CODER,
            prompt_template="根据计划和研究结果，编写代码实现。确保代码清晰、模块化。",
            tools=["read_file", "write_file", "edit_file", "list_dir"],
            max_iterations=15,
            depends_on=["planning", "research"],
        ),
        PipelineStage(
            name="review",
            role=AgentRole.REVIEWER,
            prompt_template="审查代码质量、安全性和最佳实践。提出改进建议。",
            tools=["read_file", "list_dir"],
            max_iterations=8,
            depends_on=["coding"],
        ),
        PipelineStage(
            name="testing",
            role=AgentRole.TESTER,
            prompt_template="编写测试用例并执行测试。验证功能正确性。",
            tools=["read_file", "write_file", "exec"],
            max_iterations=10,
            depends_on=["coding", "review"],
        ),
        PipelineStage(
            name="integration",
            role=AgentRole.INTEGRATOR,
            prompt_template="整合所有结果，生成最终交付物和文档。",
            tools=["read_file", "write_file", "list_dir"],
            max_iterations=5,
            depends_on=["planning", "research", "coding", "review", "testing"],
        ),
    ]


def create_research_pipeline() -> list[PipelineStage]:
    """创建研究分析流水线"""
    return [
        PipelineStage(
            name="topic_analysis",
            role=AgentRole.PLANNER,
            prompt_template="分析研究主题，确定研究范围和关键问题。",
            tools=["read_file"],
            max_iterations=5,
        ),
        PipelineStage(
            name="information_gathering",
            role=AgentRole.RESEARCHER,
            prompt_template="收集相关信息、论文、文档和数据。",
            tools=["web_search", "web_fetch"],
            max_iterations=15,
            depends_on=["topic_analysis"],
        ),
        PipelineStage(
            name="analysis",
            role=AgentRole.REVIEWER,
            prompt_template="分析收集的信息，提取关键见解和结论。",
            tools=["read_file", "write_file"],
            max_iterations=10,
            depends_on=["information_gathering"],
        ),
        PipelineStage(
            name="report_generation",
            role=AgentRole.INTEGRATOR,
            prompt_template="生成完整的研究报告，包含摘要、分析和结论。",
            tools=["read_file", "write_file"],
            max_iterations=8,
            depends_on=["topic_analysis", "information_gathering", "analysis"],
        ),
    ]
