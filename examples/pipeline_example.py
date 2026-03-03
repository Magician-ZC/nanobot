"""多 Agent 流水线使用示例"""

import asyncio
from pathlib import Path

from nanobot.agent.pipeline import (
    AgentPipeline,
    AgentRole,
    PipelineStage,
    create_research_pipeline,
    create_software_development_pipeline,
)
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import Config
from nanobot.providers.factory import create_provider


async def example_software_development():
    """示例：使用软件开发流水线"""
    print("=== 软件开发流水线示例 ===\n")
    
    # 初始化配置
    config = Config()
    workspace = Path.home() / ".nanobot" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    
    # 创建提供商和消息总线
    provider = create_provider(config, config.agents.defaults.model)
    bus = MessageBus()
    
    # 创建流水线管理器
    pipeline = AgentPipeline(
        provider=provider,
        workspace=workspace,
        bus=bus,
        model=config.agents.defaults.model,
    )
    
    # 使用预定义的软件开发流水线
    stages = create_software_development_pipeline()
    
    # 定义阶段完成回调
    def on_stage_complete(stage_name: str, result: str):
        print(f"\n✓ 阶段 '{stage_name}' 完成")
        print(f"结果预览: {result[:200]}...\n")
    
    # 执行流水线
    task = "创建一个简单的 Python HTTP 服务器，支持 GET 和 POST 请求"
    print(f"任务: {task}\n")
    print(f"流水线阶段数: {len(stages)}\n")
    
    result = await pipeline.execute(
        task=task,
        stages=stages,
        on_stage_complete=on_stage_complete,
    )
    
    print("\n=== 最终结果 ===")
    print(result)


async def example_research():
    """示例：使用研究分析流水线"""
    print("\n\n=== 研究分析流水线示例 ===\n")
    
    config = Config()
    workspace = Path.home() / ".nanobot" / "workspace"
    
    provider = create_provider(config, config.agents.defaults.model)
    bus = MessageBus()
    
    pipeline = AgentPipeline(
        provider=provider,
        workspace=workspace,
        bus=bus,
        model=config.agents.defaults.model,
    )
    
    # 使用预定义的研究流水线
    stages = create_research_pipeline()
    
    task = "研究 Rust 语言在 Web 开发中的应用和优势"
    print(f"任务: {task}\n")
    print(f"流水线阶段数: {len(stages)}\n")
    
    result = await pipeline.execute(
        task=task,
        stages=stages,
    )
    
    print("\n=== 最终结果 ===")
    print(result)


async def example_custom_pipeline():
    """示例：自定义流水线"""
    print("\n\n=== 自定义流水线示例 ===\n")
    
    config = Config()
    workspace = Path.home() / ".nanobot" / "workspace"
    
    provider = create_provider(config, config.agents.defaults.model)
    bus = MessageBus()
    
    pipeline = AgentPipeline(
        provider=provider,
        workspace=workspace,
        bus=bus,
        model=config.agents.defaults.model,
    )
    
    # 自定义流水线：竞品分析
    stages = [
        PipelineStage(
            name="competitor_identification",
            role=AgentRole.RESEARCHER,
            prompt_template="识别主要竞争对手，列出前 5 名及其官网",
            tools=["web_search", "web_fetch"],
            max_iterations=8,
        ),
        PipelineStage(
            name="feature_analysis",
            role=AgentRole.REVIEWER,
            prompt_template="分析每个竞品的核心功能、定价和目标用户",
            tools=["web_search", "web_fetch"],
            max_iterations=10,
            depends_on=["competitor_identification"],
        ),
        PipelineStage(
            name="swot_analysis",
            role=AgentRole.PLANNER,
            prompt_template="对每个竞品进行 SWOT 分析（优势、劣势、机会、威胁）",
            tools=["read_file"],
            max_iterations=5,
            depends_on=["feature_analysis"],
        ),
        PipelineStage(
            name="report_generation",
            role=AgentRole.INTEGRATOR,
            prompt_template="生成完整的竞品分析报告，包含对比表格和结论建议",
            tools=["write_file"],
            max_iterations=5,
            depends_on=["competitor_identification", "feature_analysis", "swot_analysis"],
        ),
    ]
    
    task = "分析 AI 代码助手市场的主要竞品（如 GitHub Copilot、Cursor 等）"
    print(f"任务: {task}\n")
    print(f"自定义流水线阶段:")
    for i, stage in enumerate(stages, 1):
        deps = f" (依赖: {', '.join(stage.depends_on)})" if stage.depends_on else ""
        print(f"  {i}. {stage.name} - {stage.role.value}{deps}")
    print()
    
    result = await pipeline.execute(
        task=task,
        stages=stages,
    )
    
    print("\n=== 最终结果 ===")
    print(result)


async def main():
    """运行所有示例"""
    # 注意：这些示例需要配置有效的 API key
    # 请确保 ~/.nanobot/config.json 中已配置 LLM 提供商
    
    try:
        # 示例 1: 软件开发流水线
        await example_software_development()
        
        # 示例 2: 研究分析流水线
        # await example_research()
        
        # 示例 3: 自定义流水线
        # await example_custom_pipeline()
        
    except Exception as e:
        print(f"\n错误: {e}")
        print("\n请确保:")
        print("1. 已运行 'nanobot onboard' 初始化配置")
        print("2. 在 ~/.nanobot/config.json 中配置了有效的 API key")


if __name__ == "__main__":
    asyncio.run(main())
