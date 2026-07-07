"""One-shot launcher that applies YAML config and starts Excalibur."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from excalibur.server.local_llm_config import (
    DEFAULT_LONG_CONTEXT_THRESHOLD,
    JsonObject,
    LocalLLMSettings,
    save_local_llm_config,
    validate_settings,
)
from excalibur.server.mcp_config import (
    add_mcp_server,
    parse_mcp_add_payload,
    parse_mcp_remove_payload,
    remove_mcp_server,
)
from excalibur.server.runtime_config import (
    DEFAULT_RUNTIME_CONFIG_PATH,
    ExcaliburRunSettings,
    load_runtime_config,
    mcp_servers_from_runtime_config,
    run_settings_from_runtime_config,
    settings_from_runtime_config,
)
from excalibur.server.web_config import (
    DEFAULT_CCR_LOG_PATH,
    DEFAULT_CONFIG_PATH,
    DEFAULT_TEMPLATE_PATH,
    ensure_bashrc_activation,
    restart_ccr,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the excalibur-run CLI parser."""
    parser = argparse.ArgumentParser(
        prog="excalibur-run",
        description="Apply /workspace/excalibur.yml, start CCR, and launch Excalibur.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("EXCALIBUR_RUNTIME_CONFIG", str(DEFAULT_RUNTIME_CONFIG_PATH))),
        help="YAML runtime config path",
    )
    parser.add_argument(
        "--ccr-config",
        type=Path,
        default=Path(os.environ.get("EXCALIBUR_CCR_CONFIG", str(DEFAULT_CONFIG_PATH))),
        help="Claude Code Router JSON config path",
    )
    parser.add_argument(
        "--ccr-template",
        type=Path,
        default=Path(os.environ.get("EXCALIBUR_CCR_TEMPLATE", str(DEFAULT_TEMPLATE_PATH))),
        help="Optional Claude Code Router template JSON path",
    )
    parser.add_argument(
        "--ccr-log",
        type=Path,
        default=Path(os.environ.get("EXCALIBUR_CCR_LOG", str(DEFAULT_CCR_LOG_PATH))),
        help="Claude Code Router log path",
    )
    parser.add_argument("--target", help="Target override for this run")
    parser.add_argument("--instruction", help="Instruction/context override for this run")
    parser.add_argument("--model", help="Excalibur Claude model override for this run")
    parser.add_argument("--non-interactive", action="store_true", help="Run without the TUI")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose Excalibur output")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--raw", action="store_true", help="Use raw output mode")
    parser.add_argument("--resume", action="store_true", help="Resume the latest session")
    parser.add_argument("--session-id", help="Resume a specific session ID")
    parser.add_argument("--list-sessions", action="store_true", help="List sessions")
    parser.add_argument("--no-telemetry", action="store_true", help="Disable telemetry")
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Additional argument passed to excalibur; repeat for multiple args",
    )
    parser.add_argument(
        "--configure-only",
        action="store_true",
        help="Write config and start CCR without launching Excalibur",
    )
    parser.add_argument(
        "--no-restart-router",
        action="store_true",
        help="Write CCR config but do not restart Claude Code Router",
    )
    parser.add_argument(
        "--skip-mcp",
        action="store_true",
        help="Skip MCP servers listed in YAML",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the command instead of running it"
    )
    return parser


def merge_run_overrides(
    settings: ExcaliburRunSettings,
    args: argparse.Namespace,
) -> ExcaliburRunSettings:
    """Merge command-line overrides onto YAML run settings."""
    extra_args = [*settings.extra_args, *args.extra_arg]
    return replace(
        settings,
        target=args.target.strip() if isinstance(args.target, str) else settings.target,
        instruction=(
            args.instruction.strip() if isinstance(args.instruction, str) else settings.instruction
        ),
        model=args.model.strip() if isinstance(args.model, str) else settings.model,
        non_interactive=settings.non_interactive or args.non_interactive,
        verbose=settings.verbose or args.verbose,
        debug=settings.debug or args.debug,
        raw=settings.raw or args.raw,
        resume=settings.resume or args.resume,
        session_id=args.session_id.strip()
        if isinstance(args.session_id, str)
        else settings.session_id,
        list_sessions=settings.list_sessions or args.list_sessions,
        no_telemetry=settings.no_telemetry or args.no_telemetry,
        extra_args=extra_args,
    )


def build_excalibur_command(settings: ExcaliburRunSettings) -> list[str]:
    """Build the excalibur command from run settings."""
    if not settings.target:
        raise ValueError("Excalibur target is required. Set excalibur.target or pass --target.")

    command = ["excalibur", "--target", settings.target]
    if settings.instruction:
        command.extend(["--instruction", settings.instruction])
    if settings.model:
        command.extend(["--model", settings.model])
    if settings.non_interactive:
        command.append("--non-interactive")
    if settings.verbose:
        command.append("--verbose")
    if settings.debug:
        command.append("--debug")
    if settings.raw:
        command.append("--raw")
    if settings.resume:
        command.append("--resume")
    if settings.session_id:
        command.extend(["--session-id", settings.session_id])
    if settings.list_sessions:
        command.append("--list-sessions")
    if settings.no_telemetry:
        command.append("--no-telemetry")
    command.extend(settings.extra_args)
    return command


def configure_router(
    settings: LocalLLMSettings,
    config_path: Path,
    template_path: Path | None,
    log_path: Path,
    *,
    restart: bool = True,
) -> JsonObject:
    """Write CCR JSON from YAML LLM settings and optionally restart CCR."""
    validate_settings(settings)
    save_local_llm_config(settings, config_path, template_path)
    ensure_bashrc_activation(Path.home() / ".bashrc")

    if not restart:
        return {"ok": True, "message": "CCR config written; router restart skipped."}

    result = restart_ccr(log_path)
    if not result.get("ok"):
        message = result.get("message", "Claude Code Router did not start")
        raise RuntimeError(str(message))
    return result


def apply_mcp_servers(config: JsonObject) -> None:
    """Apply optional MCP server definitions from YAML."""
    for server in mcp_servers_from_runtime_config(config):
        request = parse_mcp_add_payload(server)
        remove_request = parse_mcp_remove_payload({"name": request.name, "scope": request.scope})
        remove_mcp_server(remove_request)
        result = add_mcp_server(request)
        if not result["ok"]:
            raise RuntimeError(f"Could not add MCP server {request.name}: {result['output']}")


def ccr_environment(base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return environment variables needed for Claude SDK traffic through CCR."""
    env = dict(base_env or os.environ)
    env.setdefault("ANTHROPIC_BASE_URL", "http://127.0.0.1:3456")
    env.setdefault("ANTHROPIC_AUTH_TOKEN", "test")
    env.setdefault("ANTHROPIC_API_KEY", "test")
    env.setdefault("API_TIMEOUT_MS", str(DEFAULT_LONG_CONTEXT_THRESHOLD * 10))
    return env


def run(argv: list[str] | None = None) -> int:
    """Apply YAML config, then optionally launch Excalibur."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_runtime_config(args.config)
        llm_settings = settings_from_runtime_config(config)
        run_settings = merge_run_overrides(run_settings_from_runtime_config(config), args)
        if args.dry_run:
            validate_settings(llm_settings)
            if args.configure_only:
                print(f"Would configure Claude Code Router from {args.config}")
                return 0
            print(" ".join(build_excalibur_command(run_settings)))
            return 0

        restart = not args.no_restart_router
        configure_router(
            llm_settings,
            args.ccr_config,
            args.ccr_template if args.ccr_template.exists() else None,
            args.ccr_log,
            restart=restart,
        )

        if not args.skip_mcp:
            apply_mcp_servers(config)

        if args.configure_only:
            print(f"Configured Claude Code Router from {args.config}")
            return 0

        command = build_excalibur_command(run_settings)
        return subprocess.call(command, env=ccr_environment())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"excalibur-run: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    """Console-script entry point."""
    raise SystemExit(run())


if __name__ == "__main__":
    main()
