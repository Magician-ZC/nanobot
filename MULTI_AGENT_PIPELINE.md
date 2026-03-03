# 多 Agent 流水线功能

## 概述

nanobot 现在支持类似 OpenClaw 的多 agent 协作流水线功能。通过将复杂任务分解为多个阶段，每个阶段由专门角色的 agent 负责，实现高效的任务协作。

## 核心概念

### Agent 角色

系统预定义了 6 种 agent 角色：

| 角色 | 职责 | 典型工具 |
|------|------|----------|
| **Planner（规划者）** | 分析任务，制定执行计划 | read_file, list_dir |
| **Researcher（研究者）** | 收集信息，研究最佳实践 | web_search, web_fetch |
| **Coder（编码者）** | 编写代码实现 | read_file, write_file, edit_file |
| **Reviewer（审查者）** | 代码审查，质量检查 | read_file, list_dir |
| **Tester（测试者）** | 编写和执行测试 | read_file, write_file, exec |
| **Integrator（集成者）** | 整合结果，生成交付物 | read_file, write_file, list_dir |

### 流水线阶段

每个阶段包含：
- **名称**：阶段标识
- **角色**：使用的 agent 角色
- **提示词模板**：该阶段的具体指令
- **工具集**：该阶段可使用的工具（工具隔离）
- **依赖关系**：需要等待的前置阶段

### 状态传递

- 每个阶段的输出会自动传递给依赖它的后续阶段
- 后续阶段可以看到所有前置阶段的结果
- 最终生成包含所有阶段结果的完整报告

## 使用方法

### 1. 使用预定义流水线

#### 软件开发流水线

```python
# 在 nanobot 对话中使用
"使用 pipeline 工具执行软件开发流水线，任务是：创建一个 Python 的 HTTP 服务器"
```

对应的工具调用：
```json
{
  "task": "创建一个 Python 的 HTTP 服务器，支持 GET 和 POST 请求",
  "pipeline_type": "software_development"
}
```

流水线包含 6 个阶段：
1. **Planning** - 分析需求，制定开发计划
2. **Research** - 研究 Python HTTP 服务器最佳实践
3. **Coding** - 编写服务器代码
4. **Review** - 审查代码质量
5. **Testing** - 编写和执行测试
6. **Integration** - 整合结果，生成文档

#### 研究分析流水线

```json
{
  "task": "研究 Rust 语言在 Web 开发中的应用",
  "pipeline_type": "research"
}
```

流水线包含 4 个阶段：
1. **Topic Analysis** - 分析研究主题
2. **Information Gathering** - 收集相关资料
3. **Analysis** - 分析提取见解
4. **Report Generation** - 生成研究报告

### 2. 自定义流水线

```json
{
  "task": "分析竞品并生成报告",
  "pipeline_type": "custom",
  "custom_stages": [
    {
      "name": "competitor_identification",
      "role": "researcher",
      "prompt": "识别主要竞争对手，列出前 5 名",
      "tools": ["web_search", "web_fetch"]
    },
    {
      "name": "feature_analysis",
      "role": "reviewer",
      "prompt": "分析每个竞品的核心功能和特点",
      "tools": ["web_search", "web_fetch"],
      "depends_on": ["competitor_identification"]
    },
    {
      "name": "report_writing",
      "role": "integrator",
      "prompt": "生成竞品分析报告，包含对比表格",
      "tools": ["write_file"],
      "depends_on": ["competitor_identification", "feature_analysis"]
    }
  ]
}
```

## 架构设计

### 核心组件

```
┌─────────────────────────────────────────────────────────┐
│                     AgentLoop                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │              AgentPipeline                        │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  Stage 1: Planner                           │ │  │
│  │  │  - Tools: read_file, list_dir               │ │  │
│  │  │  - Output: 执行计划                         │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  │           ↓ (context + results)                  │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  Stage 2: Researcher                        │ │  │
│  │  │  - Tools: web_search, web_fetch             │ │  │
│  │  │  - Input: Stage 1 结果                      │ │  │
│  │  │  - Output: 研究资料                         │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  │           ↓ (context + results)                  │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  Stage 3: Coder                             │ │  │
│  │  │  - Tools: write_file, edit_file             │ │  │
│  │  │  - Input: Stage 1, 2 结果                   │ │  │
│  │  │  - Output: 代码实现                         │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  │           ↓                                       │  │
│  │         ...                                       │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  通过 MessageBus 通知主 Agent 完成结果                  │
└─────────────────────────────────────────────────────────┘
```

### 关键特性

1. **工具隔离**：每个阶段只能使用预定义的工具集，避免越权操作
2. **依赖管理**：自动处理阶段间的依赖关系，确保执行顺序
3. **上下文传递**：前置阶段的结果自动注入到后续阶段的提示词中
4. **异步执行**：流水线在后台运行，不阻塞主 agent
5. **结果通知**：完成后通过消息总线通知主 agent

## 实现细节

### 文件结构

```
nanobot/agent/
├── pipeline.py           # 流水线核心实现
│   ├── AgentRole         # Agent 角色枚举
│   ├── PipelineStage     # 流水线阶段定义
│   ├── PipelineContext   # 执行上下文
│   └── AgentPipeline     # 流水线编排器
└── tools/
    └── pipeline.py       # 流水线工具（供主 agent 调用）
```

### 与现有架构的集成

1. **复用 LLMProvider**：所有阶段使用相同的 LLM 提供商
2. **复用 ToolRegistry**：工具注册和执行机制保持一致
3. **复用 MessageBus**：通过消息总线与主 agent 通信
4. **类似 SubagentManager**：设计模式与子 agent 管理器一致

### 扩展性

#### 添加新角色

```python
class AgentRole(str, Enum):
    # ... 现有角色
    DESIGNER = "designer"  # 新增设计师角色
```

#### 创建新的流水线模板

```python
def create_ui_design_pipeline() -> list[PipelineStage]:
    """创建 UI 设计流水线"""
    return [
        PipelineStage(
            name="requirement_analysis",
            role=AgentRole.PLANNER,
            prompt_template="分析 UI 需求，确定设计目标",
            tools=["read_file"],
        ),
        PipelineStage(
            name="design",
            role=AgentRole.DESIGNER,
            prompt_template="设计 UI 界面，生成设计方案",
            tools=["write_file"],
            depends_on=["requirement_analysis"],
        ),
        # ... 更多阶段
    ]
```

## 使用场景

### 1. 复杂软件开发

将软件开发分解为规划、研究、编码、审查、测试、集成等阶段，每个阶段由专门的 agent 负责。

### 2. 深度研究分析

系统化地进行主题分析、信息收集、数据分析、报告生成。

### 3. 内容创作

分阶段完成大纲规划、资料收集、内容撰写、审校润色。

### 4. 数据处理流水线

数据采集 → 清洗 → 分析 → 可视化 → 报告生成。

## 与 OpenClaw 的对比

| 特性 | nanobot Pipeline | OpenClaw |
|------|------------------|----------|
| **代码量** | ~400 行 | 数千行 |
| **角色定义** | 6 种预定义角色 | 灵活的角色系统 |
| **工具隔离** | ✅ 支持 | ✅ 支持 |
| **依赖管理** | ✅ 自动处理 | ✅ 自动处理 |
| **异步执行** | ✅ 后台运行 | ✅ 后台运行 |
| **自定义流水线** | ✅ 支持 | ✅ 支持 |
| **集成难度** | 低（复用现有架构） | 中等 |

## 示例对话

```
用户: 帮我开发一个 TODO 应用，要求有 Web 界面和 REST API

Agent: 我将使用多 agent 流水线来完成这个任务。

[调用 pipeline 工具]
{
  "task": "开发一个 TODO 应用，包含 Web 界面和 REST API",
  "pipeline_type": "software_development"
}

Agent: 已启动软件开发流水线（id: a1b2c3d4），包含 6 个阶段。
我会在完成后通知你。

[几分钟后...]

Agent: 流水线执行完成！

已完成以下工作：
1. 规划阶段：制定了技术选型（Flask + SQLite + HTML/CSS/JS）
2. 研究阶段：收集了 REST API 最佳实践和前端框架选择
3. 编码阶段：实现了后端 API 和前端界面
4. 审查阶段：检查了代码质量和安全性
5. 测试阶段：编写并执行了单元测试和集成测试
6. 集成阶段：生成了完整的项目文档和部署说明

所有代码已保存在 workspace/todo-app/ 目录下。
```

## 最佳实践

1. **合理分解任务**：将复杂任务分解为 3-6 个阶段最佳
2. **明确依赖关系**：确保阶段间的依赖关系清晰
3. **工具最小化**：每个阶段只分配必需的工具
4. **提示词具体化**：为每个阶段编写清晰具体的指令
5. **结果可传递**：确保每个阶段的输出对后续阶段有价值

## 未来扩展

1. **并行执行**：支持无依赖关系的阶段并行执行
2. **条件分支**：根据前置阶段结果选择不同的执行路径
3. **人工介入**：在关键阶段暂停等待人工审核
4. **流水线模板市场**：分享和复用流水线配置
5. **可视化监控**：实时查看流水线执行状态

## 总结

多 agent 流水线功能为 nanobot 带来了强大的任务协作能力，通过角色分工和阶段化执行，能够高效完成复杂任务。这个实现保持了 nanobot 轻量级的特点，仅用约 400 行代码就实现了核心功能，同时充分复用了现有架构。
