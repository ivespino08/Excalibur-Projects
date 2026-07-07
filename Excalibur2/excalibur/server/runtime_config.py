"""YAML runtime config for the Excalibur container workflow."""

from __future__ import annotations

import os
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

from excalibur.server.local_llm_config import (
    DEFAULT_API_BASE_URL,
    DEFAULT_LONG_CONTEXT_THRESHOLD,
    DEFAULT_OLLAMA_BASE_URL,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI_COMPATIBLE,
    PROVIDER_TYPES,
    JsonObject,
    LocalLLMSettings,
    default_routes,
    parse_context_window,
)

DEFAULT_RUNTIME_CONFIG_PATH = Path("/workspace/excalibur.yml")


@dataclass(frozen=True)
class ExcaliburRunSettings:
    """Excalibur command settings stored alongside the LLM config."""

    target: str = ""
    instruction: str = ""
    model: str = ""
    non_interactive: bool = False
    verbose: bool = False
    debug: bool = False
    raw: bool = False
    resume: bool = False
    session_id: str = ""
    list_sessions: bool = False
    no_telemetry: bool = False
    extra_args: list[str] = field(default_factory=list)


def default_runtime_config() -> JsonObject:
    """Return the default YAML config without pre-filled model names."""
    return {
        "llm": {
            "provider": PROVIDER_OPENAI_COMPATIBLE,
            "api_base_url": DEFAULT_API_BASE_URL,
            "api_key": "",
            "enforce_ssl": False,
            "models": [],
            "selected_model": "",
            "context_window": DEFAULT_LONG_CONTEXT_THRESHOLD,
        },
        "excalibur": {
            "target": "",
            "instruction": "",
            "model": "",
            "non_interactive": False,
            "verbose": False,
            "debug": False,
            "raw": False,
            "resume": False,
            "session_id": "",
            "list_sessions": False,
            "no_telemetry": False,
            "extra_args": [],
        },
        "mcp": {
            "servers": [],
        },
    }


def default_runtime_settings() -> LocalLLMSettings:
    """Return UI defaults with an empty model dropdown."""
    return LocalLLMSettings(
        provider_type=PROVIDER_OPENAI_COMPATIBLE,
        api_base_url=DEFAULT_API_BASE_URL,
        api_key="",
        enforce_ssl=False,
        models=[],
        selected_model="",
        context_window=DEFAULT_LONG_CONTEXT_THRESHOLD,
        routes={},
        long_context_threshold=DEFAULT_LONG_CONTEXT_THRESHOLD,
    )


def runtime_config_path_from_env() -> Path:
    """Return the configured YAML path."""
    return Path(os.environ.get("EXCALIBUR_RUNTIME_CONFIG", str(DEFAULT_RUNTIME_CONFIG_PATH)))


def load_runtime_config(config_path: Path) -> JsonObject:
    """Load the YAML runtime config, or defaults when it does not exist."""
    if not config_path.exists():
        return default_runtime_config()

    with config_path.open("r", encoding="utf-8") as config_file:
        loaded = yaml.safe_load(config_file)

    if loaded is None:
        return default_runtime_config()
    if not isinstance(loaded, dict):
        raise ValueError(f"{config_path} must contain a YAML mapping")
    return cast(JsonObject, loaded)


def write_runtime_config(config: JsonObject, config_path: Path) -> None:
    """Write YAML runtime config using private file permissions."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(config, sort_keys=False, default_flow_style=False)
    config_path.write_text(rendered, encoding="utf-8")
    with suppress(OSError):
        config_path.chmod(0o600)


def settings_from_runtime_config(config: JsonObject) -> LocalLLMSettings:
    """Convert YAML config data into local LLM settings."""
    llm = _mapping(config.get("llm"), "llm")

    provider_type = _text(llm.get("provider", PROVIDER_OPENAI_COMPATIBLE), "llm.provider")
    if provider_type not in PROVIDER_TYPES:
        raise ValueError("llm.provider must be openai-compatible or ollama")

    default_url = (
        DEFAULT_OLLAMA_BASE_URL if provider_type == PROVIDER_OLLAMA else DEFAULT_API_BASE_URL
    )
    api_base_url = _text(llm.get("api_base_url", default_url), "llm.api_base_url")
    api_key = _optional_text(llm.get("api_key", ""))
    enforce_ssl = _bool(llm.get("enforce_ssl", False), "llm.enforce_ssl")
    models = _model_list(llm.get("models", []))
    selected_model = _optional_text(llm.get("selected_model", ""))
    if selected_model and selected_model not in models:
        models = [selected_model, *models]

    context_window = parse_context_window(llm.get("context_window", DEFAULT_LONG_CONTEXT_THRESHOLD))

    return LocalLLMSettings(
        provider_type=provider_type,
        api_base_url=api_base_url,
        api_key=api_key,
        enforce_ssl=enforce_ssl,
        models=models,
        selected_model=selected_model,
        context_window=context_window,
        routes=default_routes(selected_model) if selected_model else {},
        long_context_threshold=context_window,
    )


def run_settings_from_runtime_config(config: JsonObject) -> ExcaliburRunSettings:
    """Convert YAML config data into Excalibur command settings."""
    run = _mapping(config.get("excalibur"), "excalibur")
    return ExcaliburRunSettings(
        target=_optional_text(run.get("target", "")),
        instruction=_optional_text(run.get("instruction", "")),
        model=_optional_text(run.get("model", "")),
        non_interactive=_bool(run.get("non_interactive", False), "excalibur.non_interactive"),
        verbose=_bool(run.get("verbose", False), "excalibur.verbose"),
        debug=_bool(run.get("debug", False), "excalibur.debug"),
        raw=_bool(run.get("raw", False), "excalibur.raw"),
        resume=_bool(run.get("resume", False), "excalibur.resume"),
        session_id=_optional_text(run.get("session_id", "")),
        list_sessions=_bool(run.get("list_sessions", False), "excalibur.list_sessions"),
        no_telemetry=_bool(run.get("no_telemetry", False), "excalibur.no_telemetry"),
        extra_args=_string_list(run.get("extra_args", []), "excalibur.extra_args"),
    )


def runtime_config_from_settings(
    settings: LocalLLMSettings,
    run_settings: ExcaliburRunSettings | None = None,
    existing_config: JsonObject | None = None,
) -> JsonObject:
    """Build YAML config data from local LLM and run settings."""
    base = existing_config.copy() if existing_config else default_runtime_config()
    existing_run = run_settings_from_runtime_config(base) if run_settings is None else run_settings

    base["llm"] = {
        "provider": settings.provider_type,
        "api_base_url": settings.api_base_url,
        "api_key": settings.api_key,
        "enforce_ssl": settings.enforce_ssl,
        "models": list(settings.models),
        "selected_model": settings.selected_model,
        "context_window": settings.context_window,
    }
    base["excalibur"] = {
        "target": existing_run.target,
        "instruction": existing_run.instruction,
        "model": existing_run.model,
        "non_interactive": existing_run.non_interactive,
        "verbose": existing_run.verbose,
        "debug": existing_run.debug,
        "raw": existing_run.raw,
        "resume": existing_run.resume,
        "session_id": existing_run.session_id,
        "list_sessions": existing_run.list_sessions,
        "no_telemetry": existing_run.no_telemetry,
        "extra_args": list(existing_run.extra_args),
    }
    base.setdefault("mcp", {"servers": []})
    return base


def save_runtime_config(
    settings: LocalLLMSettings,
    config_path: Path,
    run_settings: ExcaliburRunSettings | None = None,
    existing_config: JsonObject | None = None,
) -> JsonObject:
    """Persist runtime config YAML and return the written object."""
    config = runtime_config_from_settings(settings, run_settings, existing_config)
    write_runtime_config(config, config_path)
    return config


def mcp_servers_from_runtime_config(config: JsonObject) -> list[JsonObject]:
    """Return optional MCP server definitions from YAML."""
    mcp = _mapping(config.get("mcp"), "mcp")
    servers = mcp.get("servers", [])
    if servers is None:
        return []
    if not isinstance(servers, list):
        raise ValueError("mcp.servers must be a list")
    normalized: list[JsonObject] = []
    for index, server in enumerate(servers, start=1):
        if not isinstance(server, dict):
            raise ValueError(f"mcp.servers[{index}] must be a mapping")
        normalized.append(cast(JsonObject, server))
    return normalized


def _mapping(value: Any, label: str) -> JsonObject:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return cast(JsonObject, value)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    return value.strip()


def _optional_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _bool(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"1", "true", "yes", "on"}:
            return True
        if cleaned in {"0", "false", "no", "off", ""}:
            return False
    raise ValueError(f"{label} must be true or false")


def _model_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace(",", "\n").splitlines()
    elif isinstance(value, list):
        raw_items = value
    else:
        raise ValueError("llm.models must be a list or string")

    models: list[str] = []
    for item in raw_items:
        model = str(item).strip()
        if model and model not in models:
            models.append(model)
    return models


def _string_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return [str(item).strip() for item in value if str(item).strip()]
