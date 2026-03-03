"""竞争式多 Agent 流水线：支持并行竞争和投票选择"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from nanobot.agent.pipeline import AgentPipeline, PipelineStage


@dataclass
class CompetitiveResult:
    """竞争式执行结果"""
    agent_id: str
    result: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class CompetitivePipeline(AgentPipeline):
    """
    竞争式流水线：支持多个 agent 并行执行同一任务，然后选择最优结果
    
    适用场景：
    - 创意设计（多个设计方案选最佳）
    - 算法优化（多种实现方式对比）
    - 问题求解（多角度思考）
    """

    async def execute_competitive(
        self,
        task: str,
        stage: PipelineStage,
        num_agents: int = 3,
        selection_strategy: str = "llm_judge",
    ) -> CompetitiveResult:
        """
        竞争式执行单个阶段
        
        Args:
            task: 任务描述
            stage: 要执行的阶段
            num_agents: 并行 agent 数量
            selection_strategy: 选择策略（llm_judge/voting/first）
        
        Returns:
            最优结果
        """
        logger.info(
            "Starting competitive execution with {} agents for stage '{}'",
            num_agents,
            stage.name,
        )
        
        # 并行执行多个 agent
        tasks = []
        for i in range(num_agents):
            agent_task = self._execute_competitive_agent(
                agent_id=f"agent_{i+1}",
                task=task,
                stage=stage,
            )
            tasks.append(agent_task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤失败的结果
        valid_results = [
            r for r in results
            if isinstance(r, CompetitiveResult)
        ]
        
        if not valid_results:
            raise RuntimeError("All competitive agents failed")
        
        # 选择最优结果
        if selection_strategy == "llm_judge":
            best = await self._select_by_llm_judge(task, valid_results)
        elif selection_strategy == "voting":
            best = await self._select_by_voting(valid_results)
        else:  # first
            best = valid_results[0]
        
        logger.info(
            "Selected result from {} (score: {:.2f})",
            best.agent_id,
            best.score,
        )
        
        return best

    async def _execute_competitive_agent(
        self,
        agent_id: str,
        task: str,
        stage: PipelineStage,
    ) -> CompetitiveResult:
        """执行单个竞争 agent"""
        try:
            from nanobot.agent.pipeline import PipelineContext
            
            context = PipelineContext(task=task)
            result = await self._execute_stage(stage, context, agent_id)
            
            return CompetitiveResult(
                agent_id=agent_id,
                result=result,
            )
        except Exception as e:
            logger.error("Agent {} failed: {}", agent_id, e)
            raise

    async def _select_by_llm_judge(
        self,
        task: str,
        results: list[CompetitiveResult],
    ) -> CompetitiveResult:
        """使用 LLM 作为评委选择最优结果"""
        # 构建评审提示
        candidates = "\n\n".join([
            f"=== Candidate {r.agent_id} ===\n{r.result}"
            for r in results
        ])
        
        judge_prompt = f"""你是一个专业的评审员。请评估以下候选方案，选出最优的一个。

任务: {task}

候选方案:
{candidates}

请分析每个方案的优缺点，然后选择最佳方案。
输出格式：
最佳方案: agent_X
理由: [简要说明]
评分: [1-10]"""

        messages = [
            {"role": "system", "content": "你是一个公正的评审员。"},
            {"role": "user", "content": judge_prompt},
        ]
        
        response = await self.provider.chat(
            messages=messages,
            tools=[],
            model=self.model,
            temperature=0.3,
        )
        
        # 解析评审结果
        content = response.content or ""
        
        # 简单解析（实际应该更健壮）
        for result in results:
            if result.agent_id in content:
                # 尝试提取评分
                import re
                score_match = re.search(r'评分[：:]\s*(\d+)', content)
                if score_match:
                    result.score = float(score_match.group(1))
                else:
                    result.score = 8.0  # 默认分数
                
                result.metadata["judge_reasoning"] = content
                return result
        
        # 如果解析失败，返回第一个
        results[0].score = 7.0
        return results[0]

    async def _select_by_voting(
        self,
        results: list[CompetitiveResult],
    ) -> CompetitiveResult:
        """通过投票选择（每个 agent 为其他 agent 投票）"""
        votes = {r.agent_id: 0 for r in results}
        
        # 每个 agent 作为评委为其他 agent 投票
        for voter_result in results:
            candidates = [r for r in results if r.agent_id != voter_result.agent_id]
            
            vote_prompt = f"""请从以下方案中选择最佳的一个（不能选择自己）：

{chr(10).join([f"{i+1}. {r.agent_id}: {r.result[:200]}..." for i, r in enumerate(candidates)])}

只需回答方案编号（1-{len(candidates)}）"""

            messages = [
                {"role": "user", "content": vote_prompt},
            ]
            
            response = await self.provider.chat(
                messages=messages,
                tools=[],
                model=self.model,
                temperature=0.3,
            )
            
            # 解析投票
            content = response.content or "1"
            try:
                choice_idx = int(content.strip()[0]) - 1
                if 0 <= choice_idx < len(candidates):
                    votes[candidates[choice_idx].agent_id] += 1
            except (ValueError, IndexError):
                pass
        
        # 选择得票最多的
        best_id = max(votes, key=votes.get)
        best = next(r for r in results if r.agent_id == best_id)
        best.score = votes[best_id]
        best.metadata["votes"] = votes
        
        return best

    async def execute_hybrid(
        self,
        task: str,
        stages: list[PipelineStage],
        competitive_stages: list[str] | None = None,
        num_competitors: int = 3,
    ) -> str:
        """
        混合模式：部分阶段使用竞争式，其他阶段使用流水线式
        
        Args:
            task: 任务描述
            stages: 所有阶段
            competitive_stages: 需要竞争执行的阶段名称列表
            num_competitors: 竞争阶段的 agent 数量
        
        Returns:
            最终结果
        """
        from nanobot.agent.pipeline import PipelineContext
        
        competitive_stages = competitive_stages or []
        context = PipelineContext(task=task)
        
        logger.info(
            "Starting hybrid pipeline: {} stages ({} competitive)",
            len(stages),
            len(competitive_stages),
        )
        
        for stage in stages:
            # 检查依赖
            for dep in stage.depends_on:
                if dep not in context.stage_results:
                    raise ValueError(
                        f"Stage '{stage.name}' depends on '{dep}' which hasn't been executed"
                    )
            
            # 判断是否使用竞争模式
            if stage.name in competitive_stages:
                logger.info("Stage '{}' using competitive mode", stage.name)
                competitive_result = await self.execute_competitive(
                    task=context.task,
                    stage=stage,
                    num_agents=num_competitors,
                )
                result = competitive_result.result
                context.metadata[f"{stage.name}_competitive"] = {
                    "winner": competitive_result.agent_id,
                    "score": competitive_result.score,
                }
            else:
                logger.info("Stage '{}' using pipeline mode", stage.name)
                result = await self._execute_stage(
                    stage,
                    context,
                    f"pipeline_{stage.name}",
                )
            
            context.stage_results[stage.name] = result
        
        # 生成最终报告
        return self._generate_final_report(context, stages)


# 预定义混合流水线模板
def create_creative_development_pipeline() -> tuple[list[PipelineStage], list[str]]:
    """
    创意开发流水线：设计阶段使用竞争模式，实现阶段使用流水线模式
    
    Returns:
        (stages, competitive_stage_names)
    """
    from nanobot.agent.pipeline import AgentRole, PipelineStage
    
    stages = [
        PipelineStage(
            name="requirement_analysis",
            role=AgentRole.PLANNER,
            prompt_template="分析需求，明确目标和约束条件",
            tools=["read_file"],
            max_iterations=5,
        ),
        PipelineStage(
            name="creative_design",
            role=AgentRole.PLANNER,
            prompt_template="设计创意方案，提出独特的解决思路",
            tools=["read_file", "web_search"],
            max_iterations=8,
            depends_on=["requirement_analysis"],
        ),
        PipelineStage(
            name="implementation",
            role=AgentRole.CODER,
            prompt_template="根据选定的设计方案实现代码",
            tools=["read_file", "write_file", "edit_file"],
            max_iterations=15,
            depends_on=["creative_design"],
        ),
        PipelineStage(
            name="testing",
            role=AgentRole.TESTER,
            prompt_template="测试实现的功能",
            tools=["read_file", "exec"],
            max_iterations=10,
            depends_on=["implementation"],
        ),
    ]
    
    # 设计阶段使用竞争模式
    competitive_stages = ["creative_design"]
    
    return stages, competitive_stages


def create_algorithm_optimization_pipeline() -> tuple[list[PipelineStage], list[str]]:
    """
    算法优化流水线：多种算法实现并行竞争
    
    Returns:
        (stages, competitive_stage_names)
    """
    from nanobot.agent.pipeline import AgentRole, PipelineStage
    
    stages = [
        PipelineStage(
            name="problem_analysis",
            role=AgentRole.PLANNER,
            prompt_template="分析问题，确定性能指标和约束",
            tools=["read_file"],
            max_iterations=5,
        ),
        PipelineStage(
            name="algorithm_design",
            role=AgentRole.CODER,
            prompt_template="设计算法实现，追求最优性能",
            tools=["read_file", "write_file", "web_search"],
            max_iterations=12,
            depends_on=["problem_analysis"],
        ),
        PipelineStage(
            name="benchmark",
            role=AgentRole.TESTER,
            prompt_template="对算法进行性能测试和对比",
            tools=["read_file", "exec"],
            max_iterations=10,
            depends_on=["algorithm_design"],
        ),
    ]
    
    # 算法设计阶段使用竞争模式
    competitive_stages = ["algorithm_design"]
    
    return stages, competitive_stages
