# Nanobot Agent Node Windows 打包和安装完整指南

## 📦 打包步骤（在你的主服务器上执行）

### 第一步：运行打包脚本

在 nanobot 项目根目录，选择以下方式之一：

**方式 A：使用 PowerShell（推荐）**
```powershell
powershell -ExecutionPolicy Bypass -File build_package.ps1
```

**方式 B：使用 Batch（Windows cmd）**
```cmd
build_package.bat
```

### 第二步：等待打包完成

脚本会自动：
- ✅ 复制 nanobot 源代码
- ✅ 生成 requirements.txt（依赖列表）
- ✅ 创建 install.ps1（自动安装脚本）
- ✅ 创建 start.bat（快速启动脚本）
- ✅ 创建 INSTALL.md（详细说明）
- ✅ 打包成 ZIP 文件

### 第三步：获取压缩包

打包完成后，压缩包位置：
```
dist/nanobot-agent-node-windows-0.1.4.zip
```

---

## 📋 压缩包内容

```
nanobot-agent-node-windows-0.1.4/
├── install.ps1                    # 自动安装脚本（必须运行）
├── start.bat                       # 快速启动脚本
├── INSTALL.md                      # 详细安装说明
├── AGENT_NODE_DEPLOYMENT.md        # 部署架构说明
├── requirements.txt                # Python 依赖列表
├── pyproject.toml                  # 项目配置
├── README.md                       # 项目说明
├── LICENSE                         # 许可证
└── nanobot/                        # nanobot 源代码
    ├── __init__.py
    ├── cli/
    ├── agent/
    ├── channels/
    ├── providers/
    ├── config/
    ├── managed/
    ├── skills/
    └── ...
```

---

## 🚀 在目标 Windows 电脑上安装

### 第一步：准备环境

1. **安装 Python 3.11+**
   - 下载：https://www.python.org/downloads/
   - 运行安装程序
   - **重要**：勾选 "Add Python to PATH"
   - 验证：打开 cmd，运行 `python --version`

2. **解压压缩包**
   - 右键点击 `nanobot-agent-node-windows-0.1.4.zip`
   - 选择 "解压到此处" 或 "解压到 nanobot-agent-node-windows-0.1.4"
   - 进入解压后的目录

### 第二步：运行安装脚本

**方式 A：直接运行（推荐）**
```powershell
# 右键点击 install.ps1
# 选择 "使用 PowerShell 运行"
```

**方式 B：命令行运行**
```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

**方式 C：手动运行**
```powershell
# 打开 PowerShell，进入解压目录
cd C:\Users\YourName\Downloads\nanobot-agent-node-windows-0.1.4

# 运行安装脚本
powershell -ExecutionPolicy Bypass -File install.ps1
```

### 第三步：等待安装完成

脚本会自动：
- ✅ 检查 Python 环境
- ✅ 创建虚拟环境
- ✅ 安装所有依赖（可能需要 5-10 分钟）
- ✅ 初始化 nanobot 配置

### 第四步：配置 LLM Provider

编辑配置文件：
```
%USERPROFILE%\.nanobot\config.json
```

添加 LLM Provider API Key（选择一个）：

**OpenRouter（推荐，支持所有模型）**
```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5"
    }
  }
}
```

**Anthropic（Claude 直连）**
```json
{
  "providers": {
    "anthropic": {
      "apiKey": "sk-ant-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "claude-opus-4-5"
    }
  }
}
```

**OpenAI（GPT）**
```json
{
  "providers": {
    "openai": {
      "apiKey": "sk-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "gpt-4"
    }
  }
}
```

获取 API Key：
- OpenRouter: https://openrouter.ai/keys
- Anthropic: https://console.anthropic.com
- OpenAI: https://platform.openai.com

### 第五步：启动 Agent Node

**方式 A：双击启动（最简单）**
- 双击 `start.bat`
- 会自动启动 nanobot gateway

**方式 B：PowerShell 启动**
```powershell
$venv = "$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
& $venv
nanobot gateway
```

### 第六步：注册到 Control Plane（可选）

如果你有 Control Plane 中控服务器：

1. 从 Control Plane 管理界面获取注册令牌
2. 在 PowerShell 中运行：
```powershell
$venv = "$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
& $venv
nanobot register --token token_xxx --server http://cp-host:8080
```

---

## 🔧 常见问题

### Q1：无法运行 PowerShell 脚本

**错误信息**：
```
cannot be loaded because running scripts is disabled on this system
```

**解决方案**：
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser
```

然后重新运行 `install.ps1`

### Q2：Python 未找到

**错误信息**：
```
'python' is not recognized as an internal or external command
```

**解决方案**：
1. 确保 Python 已安装
2. 重启 PowerShell 或 cmd
3. 检查 Python 是否在 PATH 中：
```powershell
python --version
```

### Q3：依赖安装失败

**错误信息**：
```
ERROR: Could not find a version that satisfies the requirement
```

**解决方案**：
1. 检查网络连接
2. 尝试手动安装：
```powershell
$venv = "$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
& $venv
pip install --upgrade pip
pip install -r requirements.txt
```

### Q4：启动时出错

**查看日志**：
```powershell
Get-Content $env:USERPROFILE\.nanobot\logs\nanobot.log -Tail 100
```

### Q5：如何开机自启？

创建 Windows 计划任务：
```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-ExecutionPolicy Bypass -File C:\path\to\start.bat"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "NanobotAgentNode" -Action $action -Trigger $trigger -Settings $settings -Force
```

---

## 📊 批量部署到多台电脑

### 方式 A：USB 或网络共享

1. 将压缩包复制到 USB 或网络共享
2. 在每台目标电脑上：
   - 解压
   - 运行 `install.ps1`

### 方式 B：远程执行（需要 WinRM）

在管理电脑上运行：
```powershell
$computers = @("pc1", "pc2", "pc3")
$cpUrl = "http://cp-host:8080"
$token = "token_xxx"

foreach ($computer in $computers) {
    Write-Host "部署到 $computer..."
    Invoke-Command -ComputerName $computer -ScriptBlock {
        param($url, $tok)
        # 假设压缩包已解压到 C:\temp\nanobot
        cd C:\temp\nanobot
        powershell -ExecutionPolicy Bypass -File install.ps1
    } -ArgumentList $cpUrl, $token
}
```

### 方式 C：Group Policy（企业环境）

1. 将压缩包放到 SYSVOL 共享
2. 创建 GPO 启动脚本，执行安装

---

## 📁 文件位置

安装后的文件位置：

| 文件/目录 | 位置 |
|---------|------|
| 配置文件 | `%USERPROFILE%\.nanobot\config.json` |
| 工作区 | `%USERPROFILE%\.nanobot\workspace\` |
| 日志 | `%USERPROFILE%\.nanobot\logs\` |
| 虚拟环境 | `%USERPROFILE%\nanobot\.venv\` |
| 会话数据 | `%USERPROFILE%\.nanobot\sessions\` |

---

## 🔄 更新和维护

### 更新 nanobot

```powershell
$venv = "$env:USERPROFILE\nanobot\.venv\Scripts\Activate.ps1"
& $venv
pip install --upgrade nanobot-ai
```

### 卸载

```powershell
# 删除虚拟环境
Remove-Item -Recurse $env:USERPROFILE\nanobot

# 删除配置和数据
Remove-Item -Recurse $env:USERPROFILE\.nanobot

# 删除计划任务（如果有）
Unregister-ScheduledTask -TaskName "NanobotAgentNode" -Confirm:$false
```

---

## 📞 支持

- 文档：https://github.com/HKUDS/nanobot
- 问题反馈：https://github.com/HKUDS/nanobot/issues
- 讨论：https://github.com/HKUDS/nanobot/discussions

---

## 总结

| 步骤 | 位置 | 操作 |
|------|------|------|
| 1. 打包 | 主服务器 | 运行 `build_package.ps1` |
| 2. 分发 | 主服务器 → 目标电脑 | 复制 ZIP 文件 |
| 3. 解压 | 目标电脑 | 解压 ZIP 文件 |
| 4. 安装 | 目标电脑 | 运行 `install.ps1` |
| 5. 配置 | 目标电脑 | 编辑 `config.json` |
| 6. 启动 | 目标电脑 | 运行 `start.bat` 或 `nanobot gateway` |
| 7. 注册 | 目标电脑 | 运行 `nanobot register` |

祝你使用愉快！🚀
