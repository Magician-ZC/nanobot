"""Persona API 路由 — 人格管理、记忆上报和跨节点记忆合并"""

from fastapi import APIRouter, Depends, HTTPException, status

from control_plane.auth import get_current_user, require_admin
from control_plane.models import (
    PersonaCreate,
    PersonaGenerate,
    PersonaMemoryBatchUpload,
    PersonaResponse,
    PersonaSyncResponse,
    PersonaUpdate,
)
from control_plane.persona import (
    create_persona,
    delete_persona,
    get_all_node_memories,
    get_global_memory,
    get_persona,
    get_persona_by_name,
    list_personas,
    save_global_memory,
    update_persona,
    upload_node_memory,
)

router = APIRouter()


def _build_persona_gen_prompt(body) -> str:
    """为 openclaw 多 Agent 架构定制的专家级元提示词。
    目标：生成具备深度思维模型和协作接口的高级职业 Persona。
    """
    context_data = {
        "职业/定位": body.profession or "未指定高级专家",
        "核心职责": body.purpose,
        "性格/特质": body.traits or "理性、严谨、结果导向",
        "表观年龄": body.age or "35-45岁（具备深厚行业积淀）",
        "响应语言": body.language,
    }
    context_str = "\n".join([f"- {k}: {v}" for k, v in context_data.items()])

    return f"""# Role: openclaw 系统级提示词架构师

## Task
你正在为 openclaw（一个高并发多 Agent 协同系统）设计一个核心专家节点。
你需要根据以下原始参数，逆向工程出一个具备"专家级灵魂"的 System Prompt。

## Raw Input Data
{context_str}

## Generation Requirements (高级准则)

1. **第一性原理建模**：不要只描述职业，要提取该职业背后的"底层逻辑"和"决策模型"（例如：如果是物流 CTO，必须包含架构可扩展性和成本平衡模型）。
2. **多 Agent 兼容接口**：设定 Agent 如何接收上游数据，以及如何将处理结果标准化的传递给下游。
3. **认知偏见注入**：赋予其特定领域的职业偏见（如：审计员天然怀疑数据真实性，架构师天然排斥冗余），增加角色的深度。
4. **思维链强制执行**：在输出的 Prompt 中必须包含 [Thought Process] 环节。

## Output Template (生成的 Prompt 必须符合以下结构)

# Role: [职业全称]

## Mission
[从行业高度定义该 Agent 的存在意义，以及它在 openclaw 集群中的核心价值]

## Mental Models & Frameworks (核心思维模型)
- **Model 1**: [如：MECE原则/波特五力/PDCA，并说明在此职业中如何应用]
- **Model 2**: ...

## Expertise & Domain Knowledge
- **专业深度**: [详细描述该职业必须掌握的垂直领域知识，需使用行业黑话和术语]
- **决策逻辑**: [描述面对复杂问题时，该角色优先考虑的 3 个维度]

## Rules & Behavioral Constraints
1. **交互协议**: [作为多 Agent 节点，必须遵循的输入/输出契约]
2. **禁区**: [绝对不能犯的行业错误或逻辑漏洞]
3. **输出风格**: [具体的表达特征：如"数据驱动"、"极简主义"、"充满前瞻性"]

## Workflow (执行算法)
- **Step 1: Input Analysis**: [如何解析 openclaw 传递的任务上下文]
- **Step 2: Deep Processing**: [调用哪些思维模型进行拆解]
- **Step 3: Synthesis & Verification**: [如何验证结果的准确性]
- **Step 4: Handoff**: [如何为下游 Agent 准备数据包]

## Tone of Voice
[设定其语气的温度、深度和节奏，确保其像一个真实的行业领袖或专家]

## Initialization
[一句极具职业代表性的开场白，直接触发 Agent 进入工作状态]

---
**注意**：直接输出最终的 System Prompt 内容，禁止任何多余的解释。全文使用 {body.language} 撰写。"""


# ── Persona CRUD（admin 操作）────────────────────────────────────

@router.get("/api/personas")
async def list_personas_endpoint(_user: dict = Depends(get_current_user)):
    """列出所有 Persona"""
    return await list_personas()


@router.post("/api/personas", status_code=status.HTTP_201_CREATED)
async def create_persona_endpoint(
    body: PersonaCreate,
    _admin: dict = Depends(require_admin),
):
    """创建 Persona（仅 admin）"""
    existing = await get_persona_by_name(body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Persona '{body.name}' already exists")
    if not body.persona_content:
        raise HTTPException(status_code=400, detail="persona_content is required")
    return await create_persona(
        name=body.name,
        persona_content=body.persona_content,
        description=body.description,
        max_memory_chars=body.max_memory_chars,
    )


@router.post("/api/personas/generate")
async def generate_persona_endpoint(
    body: PersonaGenerate,
    _admin: dict = Depends(require_admin),
):
    """用 LLM 生成人格定义并创建 Persona（仅 admin）

    输入用途、年龄、职业等参数，LLM 自动生成完整的人格定义。
    """
    from control_plane.llm_helper import llm_chat

    existing = await get_persona_by_name(body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Persona '{body.name}' already exists")

    prompt = _build_persona_gen_prompt(body)
    content = await llm_chat(prompt, system="你是 openclaw 系统的首席 Prompt 架构师，专精于为多 Agent 协同系统设计高保真专家人格。", max_tokens=4096)
    if not content:
        raise HTTPException(status_code=503, detail="LLM 服务不可用，请检查 Key 池配置")

    desc = f"{body.profession or ''} | {body.purpose}".strip(" |")

    return await create_persona(
        name=body.name,
        persona_content=content.strip(),
        description=desc,
        max_memory_chars=body.max_memory_chars,
    )


@router.post("/api/personas/generate-preview")
async def generate_persona_preview_endpoint(
    body: PersonaGenerate,
    _admin: dict = Depends(require_admin),
):
    """预览 LLM 生成的人格定义（不创建，仅返回生成内容）"""
    from control_plane.llm_helper import llm_chat

    prompt = _build_persona_gen_prompt(body)
    content = await llm_chat(prompt, system="你是 openclaw 系统的首席 Prompt 架构师，专精于为多 Agent 协同系统设计高保真专家人格。", max_tokens=4096)
    if not content:
        raise HTTPException(status_code=503, detail="LLM 服务不可用，请检查 Key 池配置")

    return {"persona_content": content.strip()}


@router.get("/api/personas/{persona_id}")
async def get_persona_endpoint(persona_id: str, _user: dict = Depends(get_current_user)):
    """获取 Persona 详情"""
    p = await get_persona(persona_id)
    if not p:
        raise HTTPException(status_code=404, detail="Persona not found")
    return p


@router.put("/api/personas/{persona_id}")
async def update_persona_endpoint(
    persona_id: str,
    body: PersonaUpdate,
    _admin: dict = Depends(require_admin),
):
    """更新 Persona（仅 admin，人格内容变更会递增版本号）"""
    result = await update_persona(
        persona_id=persona_id,
        persona_content=body.persona_content,
        description=body.description,
        max_memory_chars=body.max_memory_chars,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Persona not found")
    return result


@router.delete("/api/personas/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona_endpoint(persona_id: str, _admin: dict = Depends(require_admin)):
    """删除 Persona（仅 admin，会级联删除所有记忆）"""
    if not await delete_persona(persona_id):
        raise HTTPException(status_code=404, detail="Persona not found")


# ── 节点记忆上报 ──────────────────────────────────────────────────

@router.post("/api/nodes/{node_id}/persona-memory")
async def upload_persona_memory_endpoint(
    node_id: str,
    body: PersonaMemoryBatchUpload,
    current_user: dict = Depends(get_current_user),
):
    """节点批量上报 Persona 记忆

    节点在每次 pipeline stage 执行完后，将整理好的记忆上报到 control_plane。
    """
    results = []
    for mem in body.memories:
        persona = await get_persona_by_name(mem.persona_name)
        if not persona:
            results.append({"persona_name": mem.persona_name, "status": "skipped", "reason": "not found"})
            continue
        r = await upload_node_memory(
            persona_id=persona["id"],
            node_id=node_id,
            memory_content=mem.memory_content,
            history_entries=mem.history_entries,
        )
        results.append({"persona_name": mem.persona_name, "status": "ok", "memory_version": r["memory_version"]})
    return {"results": results}


# ── 节点拉取 Persona 数据 ────────────────────────────────────────

@router.get("/api/nodes/{node_id}/personas")
async def get_node_personas_endpoint(
    node_id: str,
    current_user: dict = Depends(get_current_user),
):
    """节点拉取分配给自己的所有 Persona（人格定义 + 全局记忆）

    节点通过此接口获取最新的人格定义和合并后的全局记忆。
    人格定义只读，全局记忆是所有节点经验的合并结果。
    """
    from control_plane.policies import get_node_policy

    policy = await get_node_policy(node_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Node not found")

    allowed_personas = policy.get("allowed_personas", [])
    result: list[dict] = []

    for name in allowed_personas:
        persona = await get_persona_by_name(name)
        if not persona:
            continue
        gm = await get_global_memory(persona["id"])
        result.append({
            "name": persona["name"],
            "persona_content": persona["persona_content"],
            "version": persona["version"],
            "global_memory": gm["memory_content"] if gm else "",
            "global_memory_version": gm["merge_version"] if gm else 0,
        })

    return {"personas": result}


# ── 记忆查看和合并（admin 操作）──────────────────────────────────

@router.get("/api/personas/{persona_id}/memory")
async def get_persona_memory_endpoint(
    persona_id: str,
    _admin: dict = Depends(require_admin),
):
    """查看某 Persona 在所有节点上的记忆（admin）"""
    persona = await get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    node_memories = await get_all_node_memories(persona_id)
    global_mem = await get_global_memory(persona_id)

    return {
        "persona_name": persona["name"],
        "global_memory": global_mem,
        "node_memories": node_memories,
    }


@router.post("/api/personas/{persona_id}/merge")
async def merge_persona_memory_endpoint(
    persona_id: str,
    _admin: dict = Depends(require_admin),
):
    """触发跨节点记忆合并（admin）

    收集所有节点的记忆，优先用 LLM 智能合并为全局记忆。
    合并时会进行人格一致性检查，确保记忆不与人格定义矛盾。
    LLM 不可用时降级为简单拼接合并。
    """
    from control_plane.persona import llm_merge_memories

    persona = await get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    node_memories = await get_all_node_memories(persona_id)
    if not node_memories:
        return {"status": "no_memories", "message": "No node memories to merge"}

    non_empty = [nm for nm in node_memories if nm["memory_content"].strip()]
    if not non_empty:
        return {"status": "empty", "message": "All node memories are empty"}

    current_global = await get_global_memory(persona_id)
    current_content = current_global["memory_content"] if current_global else ""

    # 优先 LLM 智能合并
    merged = await llm_merge_memories(
        persona_id=persona_id,
        persona_content=persona["persona_content"],
        current_global=current_content,
        node_memories=non_empty,
        max_chars=persona["max_memory_chars"],
    )

    if merged is None:
        # LLM 不可用，降级为简单合并
        merged = _build_merge_fallback(
            current_global=current_content,
            node_memories=non_empty,
            max_chars=persona["max_memory_chars"],
        )
        merge_method = "fallback"
    else:
        merge_method = "llm"

    result = await save_global_memory(persona_id, merged)
    return {
        "status": "merged",
        "merge_version": result["merge_version"],
        "method": merge_method,
        "chars": len(merged),
    }


@router.post("/api/personas/{persona_id}/compress")
async def compress_persona_memory_endpoint(
    persona_id: str,
    _admin: dict = Depends(require_admin),
):
    """触发记忆压缩（admin）

    用 LLM 提炼压缩全局记忆，去除冗余和过时信息。
    适合定期调用防止记忆膨胀。
    """
    from control_plane.persona import compress_memory

    persona = await get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    result = await compress_memory(persona_id)
    if result is None:
        return {"status": "skipped", "message": "Memory too small or LLM unavailable"}
    return {
        "status": "compressed",
        "merge_version": result["merge_version"],
        "before_chars": result["before_chars"],
        "after_chars": result["after_chars"],
    }


@router.post("/api/personas/compress-all")
async def compress_all_personas_endpoint(
    _admin: dict = Depends(require_admin),
):
    """批量压缩所有 Persona 的记忆（admin，适合定时任务调用）"""
    from control_plane.persona import compress_memory

    all_personas = await list_personas()
    results = []
    for p in all_personas:
        r = await compress_memory(p["id"])
        if r:
            results.append({"name": p["name"], **r})
    return {"compressed": len(results), "results": results}


def _build_merge_fallback(
    current_global: str,
    node_memories: list[dict],
    max_chars: int,
) -> str:
    """简单合并降级方案（LLM 不可用时）"""
    parts = []
    if current_global:
        parts.append(f"## 已有全局记忆\n{current_global}")
    for nm in node_memories:
        node_label = nm.get("node_id", "unknown")[:8]
        parts.append(f"## 节点 {node_label} 记忆\n{nm['memory_content']}")

    merged = "\n\n---\n\n".join(parts)
    if len(merged) > max_chars:
        merged = merged[-max_chars:]
    return merged
