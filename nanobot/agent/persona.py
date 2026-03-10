"""Agent persona management — 每个 agent 拥有独立的人格、记忆和经验积累。

人格文件存储在 workspace/personas/{persona_name}/ 目录下：
- PERSONA.md   — 人格定义（角色描述、行为准则、专长领域）
- MEMORY.md    — 长期记忆（经验、偏好、学到的教训）
- HISTORY.md   — 历史日志（可 grep 搜索的执行记录）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.memory import MemoryStore
from nanobot.utils.helpers import ensure_dir


class AgentPersona:
    """单个 agent 的人格管理器，封装人格定义 + 独立记忆。

    支持两种模式：
    - 本地模式（默认）：人格和记忆都在本地管理
    - 受管模式：人格定义只读（来自 CP），记忆整理后触发上报
    """

    def __init__(self, name: str, workspace: Path, managed_client=None):
        self.name = name
        self.persona_dir = ensure_dir(workspace / "personas" / name)
        self.persona_file = self.persona_dir / "PERSONA.md"
        self.memory = MemoryStore(self.persona_dir)
        self._managed_client = managed_client  # 非 None 表示受管模式
        self._node_id: str = ""  # 受管模式下的节点 ID

    def read_persona(self) -> str:
        """读取人格定义文件。"""
        if self.persona_file.exists():
            return self.persona_file.read_text(encoding="utf-8")
        return ""

    def write_persona(self, content: str) -> None:
        """写入人格定义文件。受管模式下禁止本地修改。"""
        if self._managed_client:
            logger.warning("Persona [{}] 受管模式下人格定义只读，跳过写入", self.name)
            return
        self.persona_file.write_text(content, encoding="utf-8")

    def get_full_context(self) -> str:
        """构建完整的人格上下文（人格 + 记忆），用于注入 system prompt。"""
        parts: list[str] = []

        persona = self.read_persona()
        if persona:
            parts.append(f"# Persona: {self.name}\n\n{persona}")

        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")

        return "\n\n---\n\n".join(parts)

    async def consolidate_experience(
        self,
        messages: list[dict[str, Any]],
        provider: Any,
        model: str,
        task_summary: str = "",
    ) -> bool:
        """将本次执行的对话整理为经验，写入长期记忆。

        复用 MemoryStore 的 LLM 整理逻辑，但用更聚焦的 prompt。
        """
        if not messages:
            return True

        lines: list[str] = []
        for m in messages:
            content = m.get("content")
            if not content or not isinstance(content, str):
                continue
            role = m.get("role", "?").upper()
            lines.append(f"{role}: {content[:500]}")

        if not lines:
            return True

        current_memory = self.memory.read_long_term()

        persona_content = self.read_persona()
        persona_constraint = ""
        if persona_content:
            persona_constraint = f"""
## 人格定义（只读，整理记忆时必须遵守）
{persona_content}

## 人格一致性检查要求
- 不得记录任何与上述人格定义矛盾的行为模式或偏好
- 如果本次对话中出现了偏离人格的行为，记录为"需要改进"而非"经验"
- 记忆内容必须强化而非削弱人格定义中的角色定位和行为准则
"""

        prompt = f"""你是 {self.name} 的记忆整理模块。请整理本次任务执行中获得的经验和教训。
{persona_constraint}
## 当前长期记忆
{current_memory or "(空)"}

## 本次任务
{task_summary}

## 本次对话记录
{chr(10).join(lines[-30:])}

请调用 save_memory 工具保存整理结果。重点记录：
1. 学到的技术经验和最佳实践
2. 遇到的问题和解决方案
3. 对未来类似任务有用的决策模式
4. 更新已有记忆中过时或不准确的信息
5. 删除与人格定义矛盾的旧记忆条目"""

        from nanobot.agent.memory import _SAVE_MEMORY_TOOL

        try:
            response = await provider.chat(
                messages=[
                    {"role": "system", "content": f"你是 {self.name} 的记忆整理助手。调用 save_memory 工具保存整理结果。"},
                    {"role": "user", "content": prompt},
                ],
                tools=_SAVE_MEMORY_TOOL,
                model=model,
            )

            if not response.has_tool_calls:
                logger.warning("Persona [{}] memory consolidation: LLM did not call save_memory", self.name)
                return False

            args = response.tool_calls[0].arguments
            if isinstance(args, str):
                args = json.loads(args)
            if not isinstance(args, dict):
                return False

            if entry := args.get("history_entry"):
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                self.memory.append_history(entry)
            if update := args.get("memory_update"):
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    self.memory.write_long_term(update)

            # 受管模式下上报记忆到 Control Plane
            await self._upload_memory_to_cp()

            logger.info("Persona [{}] memory consolidated successfully", self.name)
            return True
        except Exception:
            logger.exception("Persona [{}] memory consolidation failed", self.name)
            return False

    async def _upload_memory_to_cp(self) -> None:
        """受管模式下将本地记忆上报到 Control Plane"""
        if not self._managed_client:
            return
        try:
            memory_content = self.memory.read_long_term()
            history_file = self.persona_dir / "memory" / "HISTORY.md"
            history_entries = ""
            if history_file.exists():
                history_entries = history_file.read_text(encoding="utf-8").strip()

            if not memory_content:
                return

            await self._managed_client.upload_persona_memory([{
                "persona_name": self.name,
                "memory_content": memory_content,
                "history_entries": history_entries,
            }])
            logger.info("Persona [{}] 记忆已上报到 Control Plane", self.name)
        except Exception:
            logger.exception("Persona [{}] 记忆上报失败", self.name)


class PersonaManager:
    """管理 workspace 下所有 agent 人格。"""

    def __init__(self, workspace: Path, managed_client=None):
        self.workspace = workspace
        self.personas_dir = workspace / "personas"
        self._cache: dict[str, AgentPersona] = {}
        self._managed_client = managed_client

    def get(self, name: str) -> AgentPersona:
        """获取或创建一个 agent 人格（懒加载 + 缓存）。"""
        if name not in self._cache:
            self._cache[name] = AgentPersona(
                name, self.workspace, managed_client=self._managed_client
            )
        return self._cache[name]

    def list_personas(self) -> list[str]:
        """列出所有已有的人格名称。"""
        if not self.personas_dir.exists():
            return []
        return [
            d.name for d in self.personas_dir.iterdir()
            if d.is_dir() and (d / "PERSONA.md").exists()
        ]

    def ensure_default_personas(self) -> None:
        """确保预定义角色的人格文件存在，不存在则创建默认版本。"""
        defaults = _get_default_personas()
        for name, content in defaults.items():
            persona = self.get(name)
            if not persona.persona_file.exists():
                persona.write_persona(content)
                logger.info("Created default persona: {}", name)


def _get_default_personas() -> dict[str, str]:
    """预定义角色的默认人格模板。"""
    return {
        "planner": """# Planner — 架构规划师

## 角色定位
你是一个经验丰富的架构规划师，擅长将复杂需求分解为清晰可执行的计划。

## 行为准则
- 先理解全局再拆分细节
- 考虑技术可行性和风险点
- 输出结构化的计划，包含优先级和依赖关系
- 对不确定的部分明确标注，而不是猜测

## 专长领域
- 需求分析与任务分解
- 技术选型与架构设计
- 风险评估与应对策略
""",
        "researcher": """# Researcher — 技术研究员

## 角色定位
你是一个严谨的技术研究员，擅长快速收集和整理技术信息。

## 行为准则
- 优先查找官方文档和权威来源
- 对比多种方案的优劣
- 提供可验证的信息，附带来源
- 区分事实和观点

## 专长领域
- 技术调研与方案对比
- 最佳实践收集
- API 文档和示例代码查找
""",
        "coder": """# Coder — 高级开发工程师

## 角色定位
你是一个注重代码质量的高级开发工程师，追求简洁、可维护的实现。

## 行为准则
- 先读懂现有代码再动手修改
- 遵循项目已有的代码风格和模式
- 写清晰的注释，但不过度注释
- 优先复用已有逻辑，避免重复代码
- 考虑边界情况和错误处理

## 专长领域
- 代码实现与重构
- 模块化设计
- 性能优化
""",
        "reviewer": """# Reviewer — 代码审查专家

## 角色定位
你是一个细致的代码审查专家，关注代码质量、安全性和可维护性。

## 行为准则
- 从安全性、性能、可读性三个维度审查
- 提出具体的改进建议，而不是泛泛而谈
- 区分必须修复的问题和建议优化的点
- 认可好的实现，不只挑毛病

## 专长领域
- 代码质量审查
- 安全漏洞检测
- 性能瓶颈识别
""",
        "tester": """# Tester — 测试工程师

## 角色定位
你是一个全面的测试工程师，擅长设计测试用例和发现边界问题。

## 行为准则
- 覆盖正常路径和异常路径
- 关注边界条件和极端情况
- 测试用例要可重复执行
- 清晰记录测试结果和发现的问题

## 专长领域
- 单元测试与集成测试
- 边界条件分析
- 回归测试策略
""",
        "integrator": """# Integrator — 集成交付专家

## 角色定位
你是一个注重交付质量的集成专家，擅长汇总各方成果并确保一致性。

## 行为准则
- 确保各阶段成果的一致性和完整性
- 解决阶段间的冲突和遗漏
- 生成清晰的交付物和说明
- 做最终的质量把关

## 专长领域
- 成果整合与冲突解决
- 文档生成
- 交付质量保证
""",
    }
