"""Tests for YAML runtime config and one-shot launcher helpers."""

import argparse
from pathlib import Path

import pytest

from excalibur.server.local_llm_config import LocalLLMSettings
from excalibur.server.run_configured import (
    build_excalibur_command,
    ccr_environment,
    merge_run_overrides,
)
from excalibur.server.runtime_config import (
    ExcaliburRunSettings,
    default_runtime_config,
    load_runtime_config,
    mcp_servers_from_runtime_config,
    run_settings_from_runtime_config,
    save_runtime_config,
    settings_from_runtime_config,
)


def test_default_runtime_config_has_no_prefilled_models() -> None:
    """Fresh YAML/UI defaults should not invent model choices."""
    config = default_runtime_config()
    settings = settings_from_runtime_config(config)

    assert settings.models == []
    assert settings.selected_model == ""
    assert settings.api_key == ""


def test_save_runtime_config_writes_yaml(tmp_path: Path) -> None:
    """Runtime settings are persisted in YAML."""
    config_path = tmp_path / "excalibur.yml"
    llm_settings = LocalLLMSettings(
        api_base_url="https://llm.example/v1",
        api_key="sk-test",
        enforce_ssl=True,
        models=["model-a"],
        selected_model="model-a",
        context_window=128000,
    )
    run_settings = ExcaliburRunSettings(
        target="10.10.10.10",
        instruction="Enumerate carefully",
        non_interactive=True,
    )

    save_runtime_config(llm_settings, config_path, run_settings)
    loaded = load_runtime_config(config_path)

    assert loaded["llm"]["models"] == ["model-a"]
    assert loaded["llm"]["api_key"] == "sk-test"
    assert loaded["excalibur"]["target"] == "10.10.10.10"
    assert run_settings_from_runtime_config(loaded).non_interactive is True


def test_runtime_config_adds_selected_model_to_model_list() -> None:
    """A manually selected model is preserved even if the list is stale."""
    settings = settings_from_runtime_config(
        {
            "llm": {
                "provider": "openai-compatible",
                "api_base_url": "http://localhost:1234/v1",
                "models": ["model-a"],
                "selected_model": "model-b",
                "context_window": 60000,
            }
        }
    )

    assert settings.models == ["model-b", "model-a"]
    assert settings.selected_model == "model-b"


def test_build_excalibur_command() -> None:
    """The one-shot launcher builds the expected Excalibur command."""
    command = build_excalibur_command(
        ExcaliburRunSettings(
            target="target.htb",
            instruction="Focus web first",
            non_interactive=True,
            no_telemetry=True,
            extra_args=["--debug"],
        )
    )

    assert command == [
        "excalibur",
        "--target",
        "target.htb",
        "--instruction",
        "Focus web first",
        "--non-interactive",
        "--no-telemetry",
        "--debug",
    ]


def test_build_excalibur_command_requires_target() -> None:
    """A one-shot run needs a target from YAML or CLI."""
    with pytest.raises(ValueError, match="target is required"):
        build_excalibur_command(ExcaliburRunSettings())


def test_merge_run_overrides_prefers_cli_values() -> None:
    """CLI arguments override YAML run values."""
    parser_args = argparse.Namespace(
        target="cli-target",
        instruction=None,
        model=None,
        non_interactive=True,
        verbose=False,
        debug=False,
        raw=False,
        resume=False,
        session_id=None,
        list_sessions=False,
        no_telemetry=False,
        extra_arg=["--raw"],
    )

    settings = merge_run_overrides(
        ExcaliburRunSettings(target="yaml-target", extra_args=["--debug"]),
        parser_args,
    )

    assert settings.target == "cli-target"
    assert settings.non_interactive is True
    assert settings.extra_args == ["--debug", "--raw"]


def test_ccr_environment_sets_router_values() -> None:
    """The launcher supplies the Anthropic env vars that point at CCR."""
    env = ccr_environment({})

    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:3456"
    assert env["ANTHROPIC_API_KEY"] == "test"


def test_mcp_servers_from_runtime_config() -> None:
    """Optional MCP servers can be declared in YAML."""
    servers = mcp_servers_from_runtime_config(
        {
            "mcp": {
                "servers": [
                    {
                        "name": "example",
                        "scope": "project",
                        "transport": "http",
                        "command_or_url": "http://localhost:3000/mcp",
                    }
                ]
            }
        }
    )

    assert servers[0]["name"] == "example"
