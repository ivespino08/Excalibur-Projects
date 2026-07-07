"""Helpers for managing Claude Code MCP servers from the web UI."""

from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MCP_SCOPES = ("project", "local", "user")
MCP_TRANSPORTS = ("stdio", "http", "sse")
MCP_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
MCP_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
DEFAULT_MCP_CWD = Path("/workspace")


@dataclass(frozen=True)
class MCPAddRequest:
    """Validated request to add an MCP server."""

    name: str
    transport: str
    scope: str
    command_or_url: str
    args: list[str] = field(default_factory=list)
    env: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MCPRemoveRequest:
    """Validated request to remove an MCP server."""

    name: str
    scope: str | None = None


def _clean_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} is required")
    if "\x00" in cleaned:
        raise ValueError(f"{label} contains an invalid character")
    return cleaned


def validate_mcp_name(name: Any) -> str:
    """Validate a Claude MCP server name."""
    cleaned = _clean_text(name, "MCP server name")
    if not MCP_NAME_RE.fullmatch(cleaned):
        raise ValueError(
            "MCP server name can only contain letters, numbers, dots, dashes, and underscores"
        )
    return cleaned


def validate_scope(scope: Any, *, allow_none: bool = False) -> str | None:
    """Validate an MCP config scope."""
    if allow_none and (scope is None or scope == ""):
        return None
    cleaned = _clean_text(scope, "MCP scope")
    if cleaned not in MCP_SCOPES:
        raise ValueError(f"MCP scope must be one of: {', '.join(MCP_SCOPES)}")
    return cleaned


def validate_transport(transport: Any) -> str:
    """Validate an MCP transport."""
    cleaned = _clean_text(transport, "MCP transport")
    if cleaned not in MCP_TRANSPORTS:
        raise ValueError(f"MCP transport must be one of: {', '.join(MCP_TRANSPORTS)}")
    return cleaned


def normalize_lines(value: Any, label: str) -> list[str]:
    """Normalize either a string or list into non-empty lines."""
    if value is None:
        return []
    raw_items: list[Any]
    if isinstance(value, str):
        raw_items = value.splitlines()
    elif isinstance(value, list):
        raw_items = value
    else:
        raise ValueError(f"{label} must be a string or list")

    normalized: list[str] = []
    for item in raw_items:
        cleaned = _clean_text(item, label) if str(item).strip() else ""
        if cleaned:
            normalized.append(cleaned)
    return normalized


def normalize_env(value: Any) -> list[str]:
    """Normalize and validate KEY=value environment entries."""
    env = normalize_lines(value, "MCP environment variable")
    for item in env:
        if not MCP_ENV_RE.fullmatch(item):
            raise ValueError("MCP environment entries must look like KEY=value")
    return env


def normalize_headers(value: Any) -> list[str]:
    """Normalize and validate HTTP header entries."""
    headers = normalize_lines(value, "MCP header")
    for item in headers:
        if ":" not in item or item.startswith(":"):
            raise ValueError("MCP headers must look like Header-Name: value")
    return headers


def parse_mcp_add_payload(payload: dict[str, Any]) -> MCPAddRequest:
    """Validate an MCP add request payload."""
    name = validate_mcp_name(payload.get("name"))
    transport = validate_transport(payload.get("transport", "stdio"))
    scope = validate_scope(payload.get("scope", "project"))
    command_or_url = _clean_text(payload.get("command_or_url"), "MCP command or URL")

    args_value = payload.get("args", [])
    if isinstance(args_value, str):
        args = shlex.split(args_value)
    elif isinstance(args_value, list):
        args = [_clean_text(arg, "MCP argument") for arg in args_value if str(arg).strip()]
    else:
        raise ValueError("MCP args must be a string or list")

    if transport in {"http", "sse"} and not command_or_url.startswith(("http://", "https://")):
        raise ValueError("HTTP and SSE MCP servers require an http:// or https:// URL")

    scope_value = scope or "project"
    return MCPAddRequest(
        name=name,
        transport=transport,
        scope=scope_value,
        command_or_url=command_or_url,
        args=args,
        env=normalize_env(payload.get("env", [])),
        headers=normalize_headers(payload.get("headers", [])),
    )


def parse_mcp_remove_payload(payload: dict[str, Any]) -> MCPRemoveRequest:
    """Validate an MCP remove request payload."""
    return MCPRemoveRequest(
        name=validate_mcp_name(payload.get("name")),
        scope=validate_scope(payload.get("scope"), allow_none=True),
    )


def build_mcp_add_command(request: MCPAddRequest) -> list[str]:
    """Build the Claude Code MCP add command."""
    command = [
        "claude",
        "mcp",
        "add",
        "--scope",
        request.scope,
        "--transport",
        request.transport,
    ]
    for env_entry in request.env:
        command.extend(["-e", env_entry])
    for header in request.headers:
        command.extend(["-H", header])

    command.append(request.name)
    if request.transport == "stdio":
        command.extend(["--", request.command_or_url, *request.args])
    else:
        command.append(request.command_or_url)
    return command


def build_mcp_remove_command(request: MCPRemoveRequest) -> list[str]:
    """Build the Claude Code MCP remove command."""
    command = ["claude", "mcp", "remove"]
    if request.scope:
        command.extend(["--scope", request.scope])
    command.append(request.name)
    return command


def run_command(command: list[str], timeout: int = 30) -> dict[str, Any]:
    """Run a Claude MCP command and return structured output."""
    result = subprocess.run(
        command,
        cwd=DEFAULT_MCP_CWD if DEFAULT_MCP_CWD.exists() else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "output": output,
    }


def parse_mcp_list_output(output: str) -> list[dict[str, Any]]:
    """Parse `claude mcp list` output into structured rows."""
    servers: list[dict[str, Any]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("Checking MCP server health"):
            continue
        if ":" not in line:
            continue

        name, remainder = line.split(":", 1)
        name = name.strip()
        remainder = remainder.strip()
        endpoint = remainder
        status = ""
        if " - " in remainder:
            endpoint, status = remainder.rsplit(" - ", 1)
            endpoint = endpoint.strip()
            status = status.strip()

        status_lower = status.lower()
        if endpoint.startswith(("http://", "https://", "ws://", "wss://")):
            transport = "http"
        elif endpoint:
            transport = "stdio"
        else:
            transport = "unknown"

        if status_lower.startswith("✓") or "connected" in status_lower:
            health = "ok"
        elif "needs authentication" in status_lower:
            health = "warn"
        elif status_lower.startswith("✗") or "failed" in status_lower or "error" in status_lower:
            health = "error"
        else:
            health = "unknown"

        servers.append(
            {
                "name": name,
                "transport": transport,
                "endpoint": endpoint,
                "status": status or "Configured",
                "health": health,
                "auth_required": "needs authentication" in status_lower,
                "raw_line": raw_line,
            }
        )

    return servers


def list_mcp_servers() -> dict[str, Any]:
    """List configured Claude Code MCP servers."""
    result = run_command(["claude", "mcp", "list"])
    result["servers"] = parse_mcp_list_output(result.get("output", ""))
    return result


def add_mcp_server(request: MCPAddRequest) -> dict[str, Any]:
    """Add a Claude Code MCP server."""
    return run_command(build_mcp_add_command(request))


def remove_mcp_server(request: MCPRemoveRequest) -> dict[str, Any]:
    """Remove a Claude Code MCP server."""
    return run_command(build_mcp_remove_command(request))
