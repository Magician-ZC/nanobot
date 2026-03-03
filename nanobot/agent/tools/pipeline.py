"""Pipeline tool for multi-agent collaboration."""

from typing import Any

from nanobot.agent.pipeline import (
    AgentPipeline,
    PipelineStage,
    create_research_pipeline,
    create_software_development_pipeline,
)
from nanobot.agent.tools.base import Tool


class PipelineTool(Tool):
    """
    启动多 agent 协作流水线
    
    支持三种模式：
    1. 流水线模式（pipeline）：顺序协作，适合结构化任务
    2. 竞争模式（competitive）：并行竞争，适合创意任务
    3. 混合模式（hybrid）：部分阶段竞争，部分阶段流水线
    """

    def __init__(self, manager: AgentPipeline):
        self.manager = manager
        self._channel = "cli"
        self._chat_id = "direct"

    @property
    def name(self) -> str:
        return "pipeline"

    @property
    def description(self) -> str:
        return """启动多 agent 协作流水线处理复杂任务。

支持三种模式：
- pipeline（流水线）：顺序协作，成本低，适合软件开发、研究分析
- competitive（竞争）：并行竞争选最优，成本高，适合创意设计、算法优化
- hybrid（混合）：关键阶段竞争，其他阶段流水线，平衡成本和质量"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "要执行的任务描述",
                },
                "mode": {
                    "type": "string",
                    "enum": ["pipeline", "competitive", "hybrid"],
                    "description": "执行模式：pipeline（流水线，成本低）、competitive（竞争，质量高）、hybrid（混合，平衡）",
                    "default": "pipeline",
                },
                "pipeline_type": {
                    "type": "string",
                    "enum": ["software_development", "research", "creative_development", "algorithm_optimization", "custom"],
                    "description": "流水线类型",
                },
                "num_competitors": {
                    "type": "integer",
                    "description": "竞争模式下的 agent 数量（默认 3）",
                    "default": 3,
                },
                "competitive_stages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "混合模式下需要竞争执行的阶段名称列表",
                },
                "custom_stages": {
                    "type": "array",
                    "description": "自定义流水线阶段（仅当 pipeline_type 为 custom 时使用）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "阶段名称"},
                            "role": {
                                "type": "string",
                                "enum": ["planner", "researcher", "coder", "reviewer", "tester", "integrator"],
                                "description": "Agent 角色",
                            },
                            "prompt": {"type": "string", "description": "阶段提示词"},
                            "tools": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "允许使用的工具列表",
                            },
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "依赖的前置阶段名称",
                            },
                        },
                        "required": ["name", "role", "prompt"],
                    },
                },
            },
            "required": ["task", "pipeline_type"],
        }

    def set_context(self, channel: str, chat_id: str) -> None:
        """设置当前会话上下文"""
        self._channel = channel
        self._chat_id = chat_id

    async def execute(
        self,
        task: str,
        pipeline_type: str,
        mode: str = "pipeline",
        num_competitors: int = 3,
        competitive_stages: list[str] | None = None,
        custom_stages: list[dict] | None = None,
    ) -> str:
        """执行流水线"""
        # 选择流水线模板
        if pipeline_type == "software_development":
            stages = create_software_development_pipeline()
            comp_stages = []
        elif pipeline_type == "research":
            stages = create_research_pipeline()
            comp_stages = []
        elif pipeline_type == "creative_development":
            from nanobot.agent.competitive_pipeline import create_creative_development_pipeline
            stages, comp_stages = create_creative_development_pipeline()
        elif pipeline_type == "algorithm_optimization":
            from nanobot.agent.competitive_pipeline import create_algorithm_optimization_pipeline
            stages, comp_stages = create_algorithm_optimization_pipeline()
        elif pipeline_type == "custom":
            if not custom_stages:
                return "Error: custom_stages is required when pipeline_type is 'custom'"
            stages = self._parse_custom_stages(custom_stages)
            comp_stages = competitive_stages or []
        else:
            return f"Error: Unknown pipeline_type '{pipeline_type}'"

        # 根据模式执行
        if mode == "competitive":
            # 竞争模式：所有阶段都竞争
            from nanobot.agent.competitive_pipeline import CompetitivePipeline
            if not isinstance(self.manager, CompetitivePipeline):
                return "Error: Competitive mode requires CompetitivePipeline manager"
            
            return await self.manager.execute_hybrid(
                task=task,
                stages=stages,
                competitive_stages=[s.name for s in stages],
                num_competitors=num_competitors,
            )
        
        elif mode == "hybrid":
            # 混合模式：部分阶段竞争
            from nanobot.agent.competitive_pipeline import CompetitivePipeline
            if not isinstance(self.manager, CompetitivePipeline):
                return "Error: Hybrid mode requires CompetitivePipeline manager"
            
            comp_stages = competitive_stages or comp_stages
            return await self.manager.execute_hybrid(
                task=task,
                stages=stages,
                competitive_stages=comp_stages,
                num_competitors=num_competitors,
            )
        
        else:  # pipeline mode
            # 流水线模式：顺序执行
            return await self.manager.spawn_pipeline(
                task=task,
                stages=stages,
                origin_channel=self._channel,
                origin_chat_id=self._chat_id,
            )

    def _parse_custom_stages(self, custom_stages: list[dict]) -> list[PipelineStage]:
        """解析自定义流水线阶段"""
        from nanobot.agent.pipeline import AgentRole
        
        stages = []
        for stage_dict in custom_stages:
            stage = PipelineStage(
                name=stage_dict["name"],
                role=AgentRole(stage_dict["role"]),
                prompt_template=stage_dict["prompt"],
                tools=stage_dict.get("tools", []),
                depends_on=stage_dict.get("depends_on", []),
            )
            stages.append(stage)
        
        return stages
