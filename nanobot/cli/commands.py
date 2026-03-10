"""CLI commands for nanobot."""

import asyncio
import os
import select
import signal
import sys
from pathlib import Path

# Force UTF-8 encoding for Windows console
if sys.platform == "win32":
    if sys.stdout.encoding != "utf-8":
        os.environ["PYTHONIOENCODING"] = "utf-8"
        # Re-open stdout/stderr with UTF-8 encoding
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from nanobot import __logo__, __version__
from nanobot.config.paths import get_workspace_path
from nanobot.config.schema import Config
from nanobot.utils.helpers import sync_workspace_templates

app = typer.Typer(
    name="nanobot",
    help=f"{__logo__} nanobot - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}

# ---------------------------------------------------------------------------
# CLI input: prompt_toolkit for editing, paste, history, and display
# ---------------------------------------------------------------------------

_PROMPT_SESSION: PromptSession | None = None
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _init_prompt_session() -> None:
    """Create the prompt_toolkit session with persistent file history."""
    global _PROMPT_SESSION, _SAVED_TERM_ATTRS

    # Save terminal state so we can restore it on exit
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    from nanobot.config.paths import get_cli_history_path

    history_file = get_cli_history_path()
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,   # Enter submits (single line mode)
    )


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with consistent terminal styling."""
    content = response or ""
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    console.print(f"[cyan]{__logo__} nanobot[/cyan]")
    console.print(body)
    console.print()


def _is_exit_command(command: str) -> bool:
    """Return True when input should end interactive chat."""
    return command.lower() in EXIT_COMMANDS


async def _read_interactive_input_async() -> str:
    """Read user input using prompt_toolkit (handles paste, history, display).

    prompt_toolkit natively handles:
    - Multiline paste (bracketed paste mode)
    - History navigation (up/down arrows)
    - Clean display (no ghost characters or artifacts)
    """
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='ansiblue'>You:</b> "),
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc



def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} nanobot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """nanobot - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize nanobot configuration and workspace."""
    from nanobot.config.loader import get_config_path, load_config, save_config
    from nanobot.config.schema import Config

    config_path = get_config_path()

    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        console.print("  [bold]y[/bold] = overwrite with defaults (existing values will be lost)")
        console.print("  [bold]N[/bold] = refresh config, keeping existing values and adding new fields")
        if typer.confirm("Overwrite?"):
            config = Config()
            save_config(config)
            console.print(f"[green]✓[/green] Config reset to defaults at {config_path}")
        else:
            config = load_config()
            save_config(config)
            console.print(f"[green]✓[/green] Config refreshed at {config_path} (existing values preserved)")
    else:
        save_config(Config())
        console.print(f"[green]✓[/green] Created config at {config_path}")

    # Create workspace
    workspace = get_workspace_path()

    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Created workspace at {workspace}")

    sync_workspace_templates(workspace)

    console.print(f"\n{__logo__} nanobot is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.nanobot/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]nanobot agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See: https://github.com/HKUDS/nanobot#-chat-apps[/dim]")





def _make_provider(config: Config):
    """Create the appropriate LLM provider from config."""
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider
    from nanobot.providers.minimax_provider import MinimaxProvider
    from nanobot.providers.azure_openai_provider import AzureOpenAIProvider

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    # OpenAI Codex (OAuth)
    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        return OpenAICodexProvider(default_model=model)

    # MiniMax: 根据 api_base 判断使用哪个 provider
    # - Anthropic 兼容 API (minimaxi.com/anthropic) -> MinimaxProvider
    # - OpenAI 兼容 API (minimax.io/v1) -> LiteLLM
    if provider_name == "minimax":
        api_base = config.get_api_base(model) or ""
        # 如果 api_base 包含 "anthropic"，使用 MinimaxProvider（Anthropic 格式）
        if "anthropic" in api_base.lower():
            return MinimaxProvider(
                api_key=p.api_key if p else "no-key",
                api_base=api_base,
                default_model=model,
            )
        # 否则使用 LiteLLM（OpenAI 格式）
        # 注意：这里不再默认使用 MinimaxProvider，而是交给 LiteLLM 处理

    # Custom: direct OpenAI-compatible endpoint, bypasses LiteLLM
    from nanobot.providers.custom_provider import CustomProvider
    if provider_name == "custom":
        return CustomProvider(
            api_key=p.api_key if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
        )

    # Azure OpenAI: direct Azure OpenAI endpoint with deployment name
    if provider_name == "azure_openai":
        if not p or not p.api_key or not p.api_base:
            console.print("[red]Error: Azure OpenAI requires api_key and api_base.[/red]")
            console.print("Set them in ~/.nanobot/config.json under providers.azure_openai section")
            console.print("Use the model field to specify the deployment name.")
            raise typer.Exit(1)
        
        return AzureOpenAIProvider(
            api_key=p.api_key,
            api_base=p.api_base,
            default_model=model,
        )

    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.registry import find_by_name
    spec = find_by_name(provider_name)
    if not model.startswith("bedrock/") and not (p and p.api_key) and not (spec and spec.is_oauth):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.nanobot/config.json under providers section")
        raise typer.Exit(1)

    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(model),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
    )


def _load_runtime_config(config: str | None = None, workspace: str | None = None) -> Config:
    """Load config and optionally override the active workspace."""
    from nanobot.config.loader import load_config, set_config_path

    config_path = None
    if config:
        config_path = Path(config).expanduser().resolve()
        if not config_path.exists():
            console.print(f"[red]Error: Config file not found: {config_path}[/red]")
            raise typer.Exit(1)
        set_config_path(config_path)
        console.print(f"[dim]Using config: {config_path}[/dim]")

    loaded = load_config(config_path)
    if workspace:
        loaded.agents.defaults.workspace = workspace
    return loaded


# ============================================================================
# Managed Mode Helpers
# ============================================================================

# ── 受管模式路径常量（供 _is_managed_mode / _validate_managed_config 等使用） ──
_MANAGED_MARKER_PATH = Path.home() / ".nanobot" / ".managed"
_CONFIG_CACHE_PATH = Path.home() / ".nanobot" / "config_cache.enc"


def _is_managed_mode(config: Config) -> bool:
    """判断是否应以受管模式运行

    优先级：.managed 标记 > config_cache.enc > controlPlane 配置段
    """
    # 1. .managed 标记文件
    if _MANAGED_MARKER_PATH.exists():
        return True
    # 2. 加密配置缓存
    if _CONFIG_CACHE_PATH.exists():
        return True
    # 3. config.json 中 controlPlane.url 非空
    if config.control_plane.url:
        return True
    return False


def _validate_managed_config(config: Config) -> None:
    """验证受管模式下的配置完整性，不满足则退出"""
    cp = config.control_plane
    if not cp.url or not cp.api_key or not cp.node_id:
        console.print(
            "[red]错误: 此节点为受管部署，需要 Control Plane 连接信息才能运行[/red]"
        )
        console.print(
            "请确保 config.json 中 controlPlane 段包含 url、apiKey 和 nodeId"
        )
        raise typer.Exit(1)


def _init_managed_components(config: Config):
    """初始化受管模式组件，返回 (ManagedClient, PolicyEnforcer)

    强制受管模式下：
    1. 尝试连接 Control Plane 拉取完整配置和策略
    2. 成功后加密缓存到本地
    3. 连接失败时尝试使用本地加密缓存
    4. 无法连接且无缓存时拒绝启动
    """
    from nanobot.managed.client import ManagedClient
    from nanobot.managed.config_cache import EncryptedConfigCache
    from nanobot.managed.policy import PolicyEnforcer

    cp = config.control_plane
    client = ManagedClient(
        control_plane_url=cp.url,
        api_key=cp.api_key,
        node_id=cp.node_id,
    )
    config_cache = EncryptedConfigCache(api_key=cp.api_key)

    import asyncio

    # ── 一次性拉取远程配置和策略 ──
    async def _fetch_all():
        remote_config = None
        enforcer = None
        try:
            remote = await client.fetch_config()
            config_data = remote.get("config_data", {})
            config_data["config_version"] = remote.get("version", 0)
            config_cache.save(config_data)
            remote_config = config_data
        except Exception as exc:
            console.print(f"[yellow]警告: 无法从 Control Plane 拉取配置: {exc}[/yellow]")

        try:
            policy = await client.fetch_policy()
            enforcer = PolicyEnforcer(policy=policy)
            enforcer.save_cache()
        except Exception as exc:
            console.print(f"[yellow]警告: 无法从 Control Plane 拉取策略: {exc}[/yellow]")

        return remote_config, enforcer

    remote_config, enforcer = asyncio.run(_fetch_all())

    # asyncio.run() 结束后 event loop 已关闭，旧的 httpx client 不可复用
    # 置空后 _ensure_client() 会在新 event loop 中自动重建
    client._client = None

    # 连接失败时尝试本地加密缓存
    if remote_config is None:
        cached = config_cache.load()
        if cached is not None:
            console.print("[yellow]使用本地加密缓存配置（离线受管模式）[/yellow]")
            remote_config = cached
        else:
            console.print("[red]错误: 无法连接 Control Plane 且无本地缓存，受管模式无法启动[/red]")
            raise typer.Exit(1)

    # ── 应用远程配置覆盖本地参数 ──
    _apply_remote_config(config, remote_config)

    # 检查 LLM Key 是否已分配
    llm_key = remote_config.get("llm_key")
    if llm_key and llm_key.get("api_key"):
        console.print(f"✓ LLM Key 已注入 (provider={llm_key['provider']})")
    else:
        console.print("[yellow]⚠ Control Plane 未分配 LLM Key，节点将无法调用 LLM[/yellow]")

    # ── 策略降级 ──
    if enforcer is None:
        enforcer = PolicyEnforcer.load_from_cache()
        if enforcer is None:
            console.print("[red]错误: 无法获取策略且无本地缓存，受管模式无法启动[/red]")
            raise typer.Exit(1)

    return client, enforcer


def _apply_remote_config(config: Config, remote_config: dict) -> None:
    """将远程配置应用到本地 Config 对象，覆盖 LLM/通道/代理参数

    强制受管模式下，本地 config.json 中的这些字段会被忽略，
    仅使用 Control Plane 下发的配置。
    """
    # 保存远程配置版本号，供心跳上报使用
    config._remote_config_version = remote_config.get("config_version", 0)

    # 远程配置可能包含 llm、channels、agent 等顶层字段
    for key in ("agents", "channels", "providers", "tools"):
        if key in remote_config:
            try:
                sub_data = remote_config[key]
                sub_model = getattr(config, key).__class__.model_validate(sub_data)
                setattr(config, key, sub_model)
            except Exception:
                pass  # 远程配置字段格式不匹配时保持本地值

    # ── 受管模式 LLM Key 管控 ──
    # 清空本地所有 provider 的 api_key，防止节点使用本地 key 绕过管控
    from loguru import logger
    from nanobot.providers.registry import PROVIDERS
    for spec in PROVIDERS:
        p = getattr(config.providers, spec.name, None)
        if p and p.api_key:
            p.api_key = ""

    # 注入 Control Plane 分配的 LLM Key
    llm_key = remote_config.get("llm_key")
    if llm_key and llm_key.get("api_key"):
        provider_name = llm_key["provider"]
        api_key = llm_key["api_key"]
        api_base = llm_key.get("api_base", "")  # 从 Control Plane 获取自定义 API 端点

        # 特殊处理：MiniMax Coding Plan 使用 Anthropic 兼容 API
        is_minimax_coding_plan = False
        if provider_name == "minimax" and "anthropic" in api_base.lower():
            logger.info(f"受管模式: 检测到 MiniMax Coding Plan (Anthropic 兼容)")
            is_minimax_coding_plan = True
            # 保持 provider=minimax，使用 MinimaxProvider

        # 规范化 provider 名称（处理大小写和模型名称混淆）
        from nanobot.providers.registry import find_by_name
        normalized_provider = None

        # 先尝试直接匹配
        if find_by_name(provider_name):
            normalized_provider = provider_name
        else:
            # 尝试小写匹配
            provider_lower = provider_name.lower()
            if find_by_name(provider_lower):
                normalized_provider = provider_lower
            else:
                # 尝试从模型名称推断 provider（如 MiniMax-M2.5 -> minimax）
                for spec in find_by_name.__globals__.get('PROVIDERS', []):
                    for kw in spec.keywords:
                        if kw.lower() in provider_lower:
                            normalized_provider = spec.name
                            break
                    if normalized_provider:
                        break

        if not normalized_provider:
            logger.warning(f"受管模式: 无法识别 provider '{provider_name}'，尝试使用原值")
            normalized_provider = provider_name

        p = getattr(config.providers, normalized_provider, None)
        if p is not None:
            p.api_key = api_key
            logger.info(f"受管模式: 设置 provider={normalized_provider}, api_key={api_key[:10]}..., api_base={api_base}")
            if api_base:
                p.api_base = api_base
                logger.info(f"受管模式: 已注入 Control Plane 分配的 LLM Key (provider={normalized_provider}, api_base={api_base})")
            else:
                logger.info(f"受管模式: 已注入 Control Plane 分配的 LLM Key (provider={normalized_provider})")

            # 强制设置 provider，确保 _match_provider 能正确匹配
            config.agents.defaults.provider = normalized_provider
            logger.info(f"受管模式: 强制设置 provider={normalized_provider}")

            # 强制设置对应 provider 的默认模型
            default_models = {
                "minimax": "MiniMax-M2.5",
                "anthropic": "claude-3-5-sonnet-20241022",
                "openai": "gpt-4o",
                "deepseek": "deepseek-chat",
                "moonshot": "moonshot-v1-8k",
                "qwen": "qwen-plus",
                "gemini": "gemini-1.5-pro",
            }

            # 如果是 MiniMax Coding Plan，使用 MiniMax-M2.5 模型
            if is_minimax_coding_plan:
                old_model = config.agents.defaults.model
                new_model = "MiniMax-M2.5"
                config.agents.defaults.model = new_model
                logger.info(f"受管模式: 强制切换模型 {old_model} -> {new_model} (MiniMax Coding Plan)")
            elif normalized_provider in default_models:
                old_model = config.agents.defaults.model
                new_model = default_models[normalized_provider]
                config.agents.defaults.model = new_model

                # 如果 Control Plane 没有提供 api_base，使用默认值
                if not api_base and normalized_provider == "minimax":
                    p.api_base = "https://api.minimaxi.com/anthropic/v1"
                    logger.info(f"受管模式: 设置 MiniMax Coding Plan API Base: {p.api_base}")

                logger.info(f"受管模式: 强制切换模型 {old_model} -> {new_model} (匹配 provider={normalized_provider})")
            
            logger.info(f"受管模式: 最终配置 - provider={normalized_provider}, api_base={p.api_base}, model={config.agents.defaults.model}")
        else:
            logger.warning(f"受管模式: 未知的 provider '{normalized_provider}'，无法注入 LLM Key")
    else:
        logger.warning("受管模式: Control Plane 未分配 LLM Key，节点将无法调用 LLM")


# ============================================================================
# Gateway / Server
# ============================================================================

# 受管模式心跳间隔（秒）
_MANAGED_HEARTBEAT_INTERVAL = 30


async def _managed_heartbeat_loop(client, policy_enforcer, config, persona_syncer=None):
    """受管模式下定期向 Control Plane 发送心跳，保持节点 online 状态

    当检测到策略更新时，同步 Persona 数据。
    """
    from nanobot.managed.client import ManagedClient
    interval = _MANAGED_HEARTBEAT_INTERVAL
    while True:
        try:
            resp = await client.heartbeat(
                config_version=getattr(config, '_remote_config_version', 0),
                policy_version=policy_enforcer.policy.version,
            )
            if resp.has_config_update or resp.has_policy_update:
                console.print(
                    f"[yellow]ℹ[/yellow] Control Plane 有更新 "
                    f"(config: v{resp.latest_config_version}, policy: v{resp.latest_policy_version})"
                )
                # 策略更新时重新同步 Persona
                if resp.has_policy_update and persona_syncer:
                    try:
                        policy = await client.fetch_policy()
                        policy_enforcer.policy = policy
                        policy_enforcer.save_cache()
                        sync_result = await persona_syncer.sync(policy.allowed_personas)
                        if sync_result.synced or sync_result.removed:
                            console.print(
                                f"[green]✓[/green] Persona 同步: "
                                f"更新={len(sync_result.synced)}, 删除={len(sync_result.removed)}"
                            )
                    except Exception as e:
                        console.print(f"[yellow]警告: Persona 同步失败: {e}[/yellow]")
        except Exception as e:
            console.print(f"[yellow]警告: 心跳发送失败: {e}[/yellow]")
        await asyncio.sleep(interval)


@app.command()
def gateway(
    port: int | None = typer.Option(None, "--port", "-p", help="Gateway port"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config: str | None = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """Start the nanobot gateway."""
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.channels.manager import ChannelManager
    from nanobot.config.paths import get_cron_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService
    from nanobot.session.manager import SessionManager

    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    config = _load_runtime_config(config, workspace)
    port = port if port is not None else config.gateway.port

    # Docker 自动注册引导：检测环境变量，首次启动时自动注册
    from nanobot.managed.bootstrap import auto_register_if_needed
    asyncio.run(auto_register_if_needed())

    console.print(f"{__logo__} Starting nanobot gateway on port {port}...")
    sync_workspace_templates(config.workspace_path)
    bus = MessageBus()
    
    # ── 受管模式检测 ──
    managed = _is_managed_mode(config)
    gateway_msg_client = None
    persona_syncer = None
    
    if managed:
        _validate_managed_config(config)
        
        # 拉取远程配置覆盖本地配置（受管模式下所有配置由 Control Plane 统一管理）
        managed_client, policy_enforcer = _init_managed_components(config)
        console.print("[green]✓[/green] 受管模式已启用（远程配置已加载）")
        
        # 受管模式下禁用本地飞书通道，避免与 Control Plane 的飞书网关 WebSocket 冲突
        if config.channels.feishu.enabled:
            config.channels.feishu.enabled = False
            console.print("[yellow]ℹ[/yellow] 受管模式下已禁用本地飞书通道（由 Control Plane 统一管理）")
        
        # 初始化网关消息客户端（通过 WebSocket + api_key 认证）
        from nanobot.managed.gateway_client import GatewayMessageClient
        cp = config.control_plane
        gateway_msg_client = GatewayMessageClient(
            control_plane_url=cp.url,
            api_key=cp.api_key,
            node_id=cp.node_id,
            bus=bus,
        )
        console.print(f"[green]✓[/green] 网关消息客户端已初始化 (节点: {cp.node_id[:8]}...)")
        
        # 初始化 Persona 同步器并执行首次同步
        from nanobot.managed.persona_sync import PersonaSyncer
        personas_dir = config.workspace_path / "personas"
        persona_syncer = PersonaSyncer(client=managed_client, personas_dir=personas_dir)
        
        import asyncio as _aio
        async def _initial_persona_sync():
            try:
                result = await persona_syncer.sync(policy_enforcer.policy.allowed_personas)
                if result.synced:
                    console.print(f"[green]✓[/green] Persona 初始同步: {len(result.synced)} 个已同步")
            except Exception as e:
                console.print(f"[yellow]警告: Persona 初始同步失败: {e}[/yellow]")
        _aio.run(_initial_persona_sync())
        # asyncio.run() 结束后重置 httpx client
        managed_client._client = None
    
    provider = _make_provider(config)
    session_manager = SessionManager(config.workspace_path)

    # 受管模式下根据策略过滤 MCP servers，只连接 Control Plane 分配的
    mcp_servers = config.tools.mcp_servers
    if managed:
        mcp_servers = policy_enforcer.filter_mcp_servers(mcp_servers)
        # 同步更新 config 对象，防止 agent 通过其他途径读取到被禁止的 MCP 配置
        config.tools.mcp_servers = mcp_servers

    # Create cron service first (callback set after agent creation)
    cron_store_path = get_cron_dir() / "jobs.json"
    cron = CronService(cron_store_path)

    # Create agent with cron service
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        reasoning_effort=config.agents.defaults.reasoning_effort,
        brave_api_key=config.tools.web.search.api_key or None,
        web_proxy=config.tools.web.proxy or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        mcp_servers=mcp_servers,
        channels_config=config.channels,
    )

    # 受管模式上下文注入到 AgentLoop（供内置受管心跳逻辑使用）
    if managed:
        agent._managed_client = managed_client
        agent._policy_enforcer = policy_enforcer
        # 将 managed_client 传递给 pipeline 和 subagent 的 persona_manager
        # 使其在受管模式下人格只读 + 记忆自动上报
        agent.pipeline.persona_manager._managed_client = managed_client
        agent.subagents.persona_manager._managed_client = managed_client

    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        from nanobot.agent.tools.cron import CronTool
        from nanobot.agent.tools.message import MessageTool
        reminder_note = (
            "[Scheduled Task] Timer finished.\n\n"
            f"Task '{job.name}' has been triggered.\n"
            f"Scheduled instruction: {job.payload.message}"
        )

        # Prevent the agent from scheduling new cron jobs during execution
        cron_tool = agent.tools.get("cron")
        cron_token = None
        if isinstance(cron_tool, CronTool):
            cron_token = cron_tool.set_cron_context(True)
        try:
            response = await agent.process_direct(
                reminder_note,
                session_key=f"cron:{job.id}",
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to or "direct",
            )
        finally:
            if isinstance(cron_tool, CronTool) and cron_token is not None:
                cron_tool.reset_cron_context(cron_token)

        message_tool = agent.tools.get("message")
        if isinstance(message_tool, MessageTool) and message_tool._sent_in_turn:
            return response

        if job.payload.deliver and job.payload.to and response:
            from nanobot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response
            ))
        return response
    cron.on_job = on_cron_job

    # Create channel manager
    channels = ChannelManager(config, bus)

    def _pick_heartbeat_target() -> tuple[str, str]:
        """Pick a routable channel/chat target for heartbeat-triggered messages."""
        enabled = set(channels.enabled_channels)
        # Prefer the most recently updated non-internal session on an enabled channel.
        for item in session_manager.list_sessions():
            key = item.get("key") or ""
            if ":" not in key:
                continue
            channel, chat_id = key.split(":", 1)
            if channel in {"cli", "system"}:
                continue
            if channel in enabled and chat_id:
                return channel, chat_id
        # Fallback keeps prior behavior but remains explicit.
        return "cli", "direct"

    # Create heartbeat service
    async def on_heartbeat_execute(tasks: str) -> str:
        """Phase 2: execute heartbeat tasks through the full agent loop."""
        channel, chat_id = _pick_heartbeat_target()

        async def _silent(*_args, **_kwargs):
            pass

        return await agent.process_direct(
            tasks,
            session_key="heartbeat",
            channel=channel,
            chat_id=chat_id,
            on_progress=_silent,
        )

    async def on_heartbeat_notify(response: str) -> None:
        """Deliver a heartbeat response to the user's channel."""
        from nanobot.bus.events import OutboundMessage
        channel, chat_id = _pick_heartbeat_target()
        if channel == "cli":
            return  # No external channel available to deliver to
        await bus.publish_outbound(OutboundMessage(channel=channel, chat_id=chat_id, content=response))

    hb_cfg = config.gateway.heartbeat
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        provider=provider,
        model=agent.model,
        on_execute=on_heartbeat_execute,
        on_notify=on_heartbeat_notify,
        interval_s=hb_cfg.interval_s,
        enabled=hb_cfg.enabled,
    )

    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        if not managed:
            console.print("[yellow]Warning: No channels enabled[/yellow]")

    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")

    console.print(f"[green]✓[/green] Heartbeat: every {hb_cfg.interval_s}s{' (CP heartbeat: 30s)' if managed else ''}")

    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            # 受管模式下启动网关消息客户端 + Control Plane 心跳
            if gateway_msg_client:
                await gateway_msg_client.start()
                console.print("[green]✓[/green] 网关消息客户端已连接 Control Plane")
            if managed:
                # 立即发一次心跳让节点变为 online，然后启动定期心跳
                asyncio.create_task(_managed_heartbeat_loop(
                    managed_client, policy_enforcer, config,
                    persona_syncer=persona_syncer,
                ))
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
        finally:
            # 受管模式下停止网关消息客户端
            if gateway_msg_client:
                await gateway_msg_client.stop()
            await agent.close_mcp()
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()

    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show nanobot runtime logs during chat"),
):
    """Interact with the agent directly."""
    from loguru import logger

    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.config.paths import get_cron_dir
    from nanobot.cron.service import CronService

    config = _load_runtime_config(config, workspace)
    sync_workspace_templates(config.workspace_path)

    bus = MessageBus()
    provider = _make_provider(config)

    # Create cron service for tool usage (no callback needed for CLI unless running)
    cron_store_path = get_cron_dir() / "jobs.json"
    cron = CronService(cron_store_path)

    if logs:
        logger.enable("nanobot")
    else:
        logger.disable("nanobot")

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        reasoning_effort=config.agents.defaults.reasoning_effort,
        brave_api_key=config.tools.web.search.api_key or None,
        web_proxy=config.tools.web.proxy or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
    )

    # Show spinner when logs are off (no output to miss); skip when logs are on
    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        # Animated spinner is safe to use with prompt_toolkit input handling
        return console.status("[dim]nanobot is thinking...[/dim]", spinner="dots")

    async def _cli_progress(content: str, *, tool_hint: bool = False) -> None:
        ch = agent_loop.channels_config
        if ch and tool_hint and not ch.send_tool_hints:
            return
        if ch and not tool_hint and not ch.send_progress:
            return
        console.print(f"  [dim]↳ {content}[/dim]")

    if message:
        # Single message mode — direct call, no bus needed
        async def run_once():
            with _thinking_ctx():
                response = await agent_loop.process_direct(message, session_id, on_progress=_cli_progress)
            _print_agent_response(response, render_markdown=markdown)
            await agent_loop.close_mcp()

        asyncio.run(run_once())
    else:
        # Interactive mode — route through bus like other channels
        from nanobot.bus.events import InboundMessage
        _init_prompt_session()
        console.print(f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n")

        if ":" in session_id:
            cli_channel, cli_chat_id = session_id.split(":", 1)
        else:
            cli_channel, cli_chat_id = "cli", session_id

        def _handle_signal(signum, frame):
            sig_name = signal.Signals(signum).name
            _restore_terminal()
            console.print(f"\nReceived {sig_name}, goodbye!")
            sys.exit(0)

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
        # SIGHUP is not available on Windows
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, _handle_signal)
        # Ignore SIGPIPE to prevent silent process termination when writing to closed pipes
        # SIGPIPE is not available on Windows
        if hasattr(signal, 'SIGPIPE'):
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)

        async def run_interactive():
            bus_task = asyncio.create_task(agent_loop.run())
            turn_done = asyncio.Event()
            turn_done.set()
            turn_response: list[str] = []

            async def _consume_outbound():
                while True:
                    try:
                        msg = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
                        if msg.metadata.get("_progress"):
                            is_tool_hint = msg.metadata.get("_tool_hint", False)
                            ch = agent_loop.channels_config
                            if ch and is_tool_hint and not ch.send_tool_hints:
                                pass
                            elif ch and not is_tool_hint and not ch.send_progress:
                                pass
                            else:
                                console.print(f"  [dim]↳ {msg.content}[/dim]")
                        elif not turn_done.is_set():
                            if msg.content:
                                turn_response.append(msg.content)
                            turn_done.set()
                        elif msg.content:
                            console.print()
                            _print_agent_response(msg.content, render_markdown=markdown)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        break

            outbound_task = asyncio.create_task(_consume_outbound())

            try:
                while True:
                    try:
                        _flush_pending_tty_input()
                        user_input = await _read_interactive_input_async()
                        command = user_input.strip()
                        if not command:
                            continue

                        if _is_exit_command(command):
                            _restore_terminal()
                            console.print("\nGoodbye!")
                            break

                        turn_done.clear()
                        turn_response.clear()

                        await bus.publish_inbound(InboundMessage(
                            channel=cli_channel,
                            sender_id="user",
                            chat_id=cli_chat_id,
                            content=user_input,
                        ))

                        with _thinking_ctx():
                            await turn_done.wait()

                        if turn_response:
                            _print_agent_response(turn_response[0], render_markdown=markdown)
                    except KeyboardInterrupt:
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
                    except EOFError:
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
            finally:
                agent_loop.stop()
                outbound_task.cancel()
                await asyncio.gather(bus_task, outbound_task, return_exceptions=True)
                await agent_loop.close_mcp()

        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from nanobot.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    dc = config.channels.discord
    table.add_row(
        "Discord",
        "✓" if dc.enabled else "✗",
        dc.gateway_url
    )

    # Feishu
    fs = config.channels.feishu
    fs_config = f"app_id: {fs.app_id[:10]}..." if fs.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "Feishu",
        "✓" if fs.enabled else "✗",
        fs_config
    )

    # Mochat
    mc = config.channels.mochat
    mc_base = mc.base_url or "[dim]not configured[/dim]"
    table.add_row(
        "Mochat",
        "✓" if mc.enabled else "✗",
        mc_base
    )

    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    # Slack
    slack = config.channels.slack
    slack_config = "socket" if slack.app_token and slack.bot_token else "[dim]not configured[/dim]"
    table.add_row(
        "Slack",
        "✓" if slack.enabled else "✗",
        slack_config
    )

    # DingTalk
    dt = config.channels.dingtalk
    dt_config = f"client_id: {dt.client_id[:10]}..." if dt.client_id else "[dim]not configured[/dim]"
    table.add_row(
        "DingTalk",
        "✓" if dt.enabled else "✗",
        dt_config
    )

    # QQ
    qq = config.channels.qq
    qq_config = f"app_id: {qq.app_id[:10]}..." if qq.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "QQ",
        "✓" if qq.enabled else "✗",
        qq_config
    )

    # Email
    em = config.channels.email
    em_config = em.imap_host if em.imap_host else "[dim]not configured[/dim]"
    table.add_row(
        "Email",
        "✓" if em.enabled else "✗",
        em_config
    )

    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess

    # User's bridge location
    from nanobot.config.paths import get_bridge_install_dir

    user_bridge = get_bridge_install_dir()

    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge

    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)

    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # nanobot/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)

    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge

    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall nanobot")
        raise typer.Exit(1)

    console.print(f"{__logo__} Setting up bridge...")

    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))

    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)

        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)

        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)

    return user_bridge


@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess

    from nanobot.config.loader import load_config
    from nanobot.config.paths import get_runtime_subdir

    config = load_config()
    bridge_dir = _get_bridge_dir()

    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")

    env = {**os.environ}
    if config.channels.whatsapp.bridge_token:
        env["BRIDGE_TOKEN"] = config.channels.whatsapp.bridge_token
    env["AUTH_DIR"] = str(get_runtime_subdir("whatsapp-auth"))

    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True, env=env)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show nanobot status."""
    from nanobot.config.loader import get_config_path, load_config

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} nanobot Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from nanobot.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")

        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_oauth:
                console.print(f"{spec.label}: [green]✓ (OAuth)[/green]")
            elif spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(f"{spec.label}: {'[green]✓[/green]' if has_key else '[dim]not set[/dim]'}")


# ============================================================================
# Register Command (受管模式节点注册)
# ============================================================================


@app.command()
def register(
    token: str = typer.Option(..., "--token", "-t", help="注册令牌"),
    server: str = typer.Option(..., "--server", "-s", help="Control Plane 地址"),
):
    """注册节点到 Control Plane。"""
    import platform
    from nanobot.config.loader import load_config, save_config, get_config_path

    console.print(f"{__logo__} 正在注册节点到 Control Plane...")

    config_path = get_config_path()
    if config_path.exists():
        config = load_config()
    else:
        config = Config()

    hostname = platform.node() or "unknown"

    async def _do_register():
        from nanobot.managed.client import ManagedClient, ControlPlaneError
        client = ManagedClient(control_plane_url=server)
        try:
            result = await client.register(token=token, hostname=hostname)
            return result
        except ControlPlaneError as e:
            console.print(f"[red]注册失败: {e}[/red]")
            raise typer.Exit(1)
        finally:
            await client.close()

    result = asyncio.run(_do_register())

    # 写入配置
    config.control_plane.url = server
    config.control_plane.api_key = result["api_key"]
    config.control_plane.node_id = result["node_id"]
    save_config(config)

    # 创建受管标记文件
    from nanobot.managed.marker import ManagedMarker
    marker = ManagedMarker()
    marker.create(server)

    console.print(f"[green]✓[/green] 注册成功")
    console.print(f"  Node ID: {result['node_id']}")
    console.print(f"  配置已写入: {config_path}")
    console.print(f"  受管标记已创建: {marker.path}")


# ============================================================================
# OAuth Login
# ============================================================================

provider_app = typer.Typer(help="Manage providers")
app.add_typer(provider_app, name="provider")


_LOGIN_HANDLERS: dict[str, callable] = {}


def _register_login(name: str):
    def decorator(fn):
        _LOGIN_HANDLERS[name] = fn
        return fn
    return decorator


@provider_app.command("login")
def provider_login(
    provider: str = typer.Argument(..., help="OAuth provider (e.g. 'openai-codex', 'github-copilot')"),
):
    """Authenticate with an OAuth provider."""
    from nanobot.providers.registry import PROVIDERS

    key = provider.replace("-", "_")
    spec = next((s for s in PROVIDERS if s.name == key and s.is_oauth), None)
    if not spec:
        names = ", ".join(s.name.replace("_", "-") for s in PROVIDERS if s.is_oauth)
        console.print(f"[red]Unknown OAuth provider: {provider}[/red]  Supported: {names}")
        raise typer.Exit(1)

    handler = _LOGIN_HANDLERS.get(spec.name)
    if not handler:
        console.print(f"[red]Login not implemented for {spec.label}[/red]")
        raise typer.Exit(1)

    console.print(f"{__logo__} OAuth Login - {spec.label}\n")
    handler()


@_register_login("openai_codex")
def _login_openai_codex() -> None:
    try:
        from oauth_cli_kit import get_token, login_oauth_interactive
        token = None
        try:
            token = get_token()
        except Exception:
            pass
        if not (token and token.access):
            console.print("[cyan]Starting interactive OAuth login...[/cyan]\n")
            token = login_oauth_interactive(
                print_fn=lambda s: console.print(s),
                prompt_fn=lambda s: typer.prompt(s),
            )
        if not (token and token.access):
            console.print("[red]✗ Authentication failed[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✓ Authenticated with OpenAI Codex[/green]  [dim]{token.account_id}[/dim]")
    except ImportError:
        console.print("[red]oauth_cli_kit not installed. Run: pip install oauth-cli-kit[/red]")
        raise typer.Exit(1)


@_register_login("github_copilot")
def _login_github_copilot() -> None:
    import asyncio

    console.print("[cyan]Starting GitHub Copilot device flow...[/cyan]\n")

    async def _trigger():
        from litellm import acompletion
        await acompletion(model="github_copilot/gpt-4o", messages=[{"role": "user", "content": "hi"}], max_tokens=1)

    try:
        asyncio.run(_trigger())
        console.print("[green]✓ Authenticated with GitHub Copilot[/green]")
    except Exception as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
