# 多 Agent 流水线使用指南

## 快速开始

### 1. 在对话中使用

最简单的方式是直接在与 nanobot 的对话中使用：

```
用户: 使用多 agent 流水线开发一个 TODO 应用

nanobot: 我将启动软件开发流水线来完成这个任务...
[自动调用 pipeline 工具]
```

### 2. 通过工具调用

如果你想更精确地控制，可以明确指定工具参数：

```
用户: 调用 pipeline 工具，参数如下：
- task: 创建一个 Python HTTP 服务器
- pipeline_type: software_development
```

### 3. 编程方式使用

参考 `pipeline_example.py` 中的示例代码。

## 预定义流水线

### software_development（软件开发）

适用于：完整的软件开发任务

阶段：
1. Planning - 需求分析和技术选型
2. Research - 技术调研和最佳实践
3. Coding - 代码实现
4. Review - 代码审查
5. Testing - 测试验证
6. Integration - 整合和文档

示例任务：
- "开发一个 REST API 服务"
- "创建一个数据处理脚本"
- "实现一个命令行工具"

### research（研究分析）

适用于：深度研究和分析任务

阶段：
1. Topic Analysis - 主题分析
2. Information Gathering - 信息收集
3. Analysis - 数据分析
4. Report Generation - 报告生成

示例任务：
- "研究 Rust 在 Web 开发中的应用"
- "分析机器学习框架的对比"
- "调研云原生技术趋势"

## 自定义流水线

### 基本结构

```json
{
  "task": "你的任务描述",
  "pipeline_type": "custom",
  "custom_stages": [
    {
      "name": "stage_name",
      "role": "researcher",
      "prompt": "这个阶段要做什么",
      "tools": ["web_search", "web_fetch"],
      "depends_on": []
    }
  ]
}
```

### 可用角色

- `planner` - 规划者（分析和计划）
- `researcher` - 研究者（信息收集）
- `coder` - 编码者（代码实现）
- `reviewer` - 审查者（质量检查）
- `tester` - 测试者（测试验证）
- `integrator` - 集成者（整合结果）

### 可用工具

- `read_file` - 读取文件
- `write_file` - 写入文件
- `edit_file` - 编辑文件
- `list_dir` - 列出目录
- `exec` - 执行命令
- `web_search` - 网络搜索
- `web_fetch` - 获取网页内容

### 示例：竞品分析流水线

```json
{
  "task": "分析 AI 代码助手市场竞品",
  "pipeline_type": "custom",
  "custom_stages": [
    {
      "name": "identify_competitors",
      "role": "researcher",
      "prompt": "识别主要竞争对手，列出前 5 名",
      "tools": ["web_search", "web_fetch"]
    },
    {
      "name": "analyze_features",
      "role": "reviewer",
      "prompt": "分析每个竞品的核心功能和定价",
      "tools": ["web_search", "web_fetch"],
      "depends_on": ["identify_competitors"]
    },
    {
      "name": "generate_report",
      "role": "integrator",
      "prompt": "生成竞品分析报告，包含对比表格",
      "tools": ["write_file"],
      "depends_on": ["identify_competitors", "analyze_features"]
    }
  ]
}
```

## 运行示例代码

```bash
# 确保已安装 nanobot
pip install -e .

# 确保已配置 API key
nanobot onboard

# 运行示例
python examples/pipeline_example.py
```

## 最佳实践

1. **任务描述要清晰**：明确说明要完成什么，期望的输出是什么
2. **合理分解阶段**：3-6 个阶段最佳，太少无法充分利用协作，太多会增加复杂度
3. **工具最小化原则**：每个阶段只分配必需的工具
4. **依赖关系要明确**：确保后续阶段真的需要前置阶段的结果
5. **提示词要具体**：为每个阶段编写清晰的指令

## 常见问题

### Q: 流水线执行需要多长时间？

A: 取决于任务复杂度和阶段数量。简单任务可能 2-3 分钟，复杂任务可能需要 10-15 分钟。

### Q: 可以中途停止流水线吗？

A: 目前不支持中途停止。建议将大任务分解为多个小流水线。

### Q: 流水线失败了怎么办？

A: 检查错误信息，通常是因为：
- API key 配置问题
- 网络连接问题
- 任务描述不够清晰
- 工具权限不足

### Q: 如何查看流水线执行进度？

A: 流水线在后台执行，完成后会通过消息通知。可以在日志中查看详细进度。

### Q: 可以并行执行多个流水线吗？

A: 可以，每个流水线独立执行，互不影响。

## 进阶用法

### 嵌套流水线

在某个阶段中启动另一个流水线：

```python
PipelineStage(
    name="sub_task",
    role=AgentRole.PLANNER,
    prompt_template="分析子任务，如果需要可以启动新的流水线",
    tools=["pipeline"],  # 允许使用 pipeline 工具
)
```

### 条件执行（未来功能）

根据前置阶段的结果决定是否执行某个阶段。

### 人工审核（未来功能）

在关键阶段暂停，等待人工审核后继续。

## 反馈和贡献

如果你有好的流水线模板或改进建议，欢迎提交 PR 或 Issue！
