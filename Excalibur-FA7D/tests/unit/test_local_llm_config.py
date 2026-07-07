"""Tests for local LLM config helpers."""

import json
from pathlib import Path

import pytest

from excalibur.server.local_llm_config import (
    DEFAULT_API_BASE_URL,
    LOCAL_PROVIDER_NAME,
    LocalLLMSettings,
    ensure_local_llm_config,
    load_config,
    models_url_for_provider,
    normalize_chat_completions_url,
    normalize_models,
    save_local_llm_config,
    settings_from_config,
)
from excalibur.server.runtime_config import save_runtime_config
from excalibur.server.web_config import (
    ensure_bashrc_activation,
    load_last_used_settings,
    settings_from_payload,
)


def test_save_local_llm_config_writes_provider_and_router(tmp_path: Path) -> None:
    """Saving settings writes the CCR local provider and router."""
    config_path = tmp_path / "config.json"
    settings = LocalLLMSettings(
        api_base_url="http://host.docker.internal:11434/v1/chat/completions",
        models=["llama3.1:latest", "qwen2.5-coder:14b"],
        selected_model="qwen2.5-coder:14b",
        context_window=32000,
    )

    save_local_llm_config(settings, config_path)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    local_provider = next(
        provider for provider in config["Providers"] if provider["name"] == LOCAL_PROVIDER_NAME
    )
    assert local_provider["api_base_url"] == settings.api_base_url
    assert local_provider["models"] == settings.models
    assert config["Router"]["think"] == "localLLM,qwen2.5-coder:14b"
    assert config["Router"]["longContextThreshold"] == 32000
    assert config["Excalibur"]["selected_model"] == "qwen2.5-coder:14b"


def test_save_local_llm_config_writes_openai_api_key(tmp_path: Path) -> None:
    """OpenAI-compatible API keys are written to the CCR provider."""
    config_path = tmp_path / "config.json"

    save_local_llm_config(
        LocalLLMSettings(
            api_key="sk-test",
            models=["model-a"],
            selected_model="model-a",
        ),
        config_path,
    )

    config = json.loads(config_path.read_text(encoding="utf-8"))
    local_provider = next(
        provider for provider in config["Providers"] if provider["name"] == LOCAL_PROVIDER_NAME
    )
    assert local_provider["api_key"] == "sk-test"
    assert settings_from_config(config).api_key == "sk-test"


def test_settings_from_existing_config_reads_local_routes(tmp_path: Path) -> None:
    """Existing CCR JSON can be converted back to UI settings."""
    config_path = tmp_path / "config.json"
    save_local_llm_config(
        LocalLLMSettings(
            models=["model-a", "model-b"],
            selected_model="model-b",
            context_window=64000,
        ),
        config_path,
    )

    settings = settings_from_config(load_config(config_path))

    assert settings.api_base_url == DEFAULT_API_BASE_URL
    assert settings.selected_model == "model-b"
    assert settings.routes["think"] == "model-b"
    assert settings.long_context_threshold == 64000


def test_load_last_used_settings_returns_empty_defaults_without_config(tmp_path: Path) -> None:
    """Fresh UI defaults do not pre-fill model names."""
    settings = load_last_used_settings(
        tmp_path / "missing.yml",
        tmp_path / "missing.json",
    )

    assert settings.models == []
    assert settings.selected_model == ""


def test_load_last_used_settings_falls_back_to_ccr_config(tmp_path: Path) -> None:
    """Existing CCR JSON is used when YAML has not been created yet."""
    ccr_config_path = tmp_path / "config.json"
    save_local_llm_config(
        LocalLLMSettings(
            models=["model-a", "model-b"],
            selected_model="model-b",
            context_window=96000,
        ),
        ccr_config_path,
    )

    settings = load_last_used_settings(tmp_path / "missing.yml", ccr_config_path)

    assert settings.models == ["model-a", "model-b"]
    assert settings.selected_model == "model-b"
    assert settings.context_window == 96000


def test_load_last_used_settings_prefers_yaml_over_ccr_config(tmp_path: Path) -> None:
    """YAML is the source of truth once it exists."""
    runtime_config_path = tmp_path / "excalibur.yml"
    ccr_config_path = tmp_path / "config.json"
    save_local_llm_config(
        LocalLLMSettings(models=["model-a"], selected_model="model-a"),
        ccr_config_path,
    )
    save_runtime_config(
        LocalLLMSettings(
            api_base_url="http://host.docker.internal:11434",
            models=["model-b"],
            selected_model="model-b",
            context_window=128000,
        ),
        runtime_config_path,
    )

    settings = load_last_used_settings(runtime_config_path, ccr_config_path)

    assert settings.models == ["model-b"]
    assert settings.selected_model == "model-b"
    assert settings.context_window == 128000


def test_ensure_local_llm_config_creates_missing_config(tmp_path: Path) -> None:
    """A missing CCR config is created with usable defaults."""
    config_path = tmp_path / "missing" / "config.json"

    settings = ensure_local_llm_config(config_path)

    assert config_path.exists()
    assert settings.models
    assert settings.routes["default"] in settings.models


def test_normalize_models_rejects_empty_input() -> None:
    """At least one model is required."""
    with pytest.raises(ValueError, match="At least one"):
        normalize_models(" , \n")


def test_settings_from_payload_adds_selected_model_to_models() -> None:
    """The web API payload parser supports a manual model name."""
    payload = {
        "provider_type": "openai-compatible",
        "api_base_url": "http://host.docker.internal:1234/v1/chat/completions",
        "models": ["model-a"],
        "selected_model": "model-b",
        "context_window": 60000,
    }

    settings = settings_from_payload(payload)

    assert settings.models == ["model-b", "model-a"]
    assert settings.selected_model == "model-b"
    assert settings.context_window == 60000


def test_settings_from_payload_accepts_optional_api_key() -> None:
    """The web API payload parser accepts an optional API key field."""
    settings = settings_from_payload(
        {
            "provider_type": "openai-compatible",
            "api_base_url": "https://local.example/v1",
            "api_key": " sk-test ",
            "models": ["model-a"],
            "selected_model": "model-a",
            "context_window": 60000,
        }
    )

    assert settings.api_key == "sk-test"


def test_settings_from_payload_validates_ssl() -> None:
    """OpenAI-compatible SSL enforcement requires HTTPS."""
    with pytest.raises(ValueError, match="Enforce SSL"):
        settings_from_payload(
            {
                "provider_type": "openai-compatible",
                "api_base_url": "http://host.docker.internal:1234/v1/chat/completions",
                "models": ["model-a"],
                "selected_model": "model-a",
                "enforce_ssl": True,
                "context_window": 60000,
            }
        )


def test_model_url_helpers() -> None:
    """Provider URLs are normalized for saving and fetching."""
    assert (
        normalize_chat_completions_url("openai-compatible", "http://host.docker.internal:1234/v1")
        == "http://host.docker.internal:1234/v1/chat/completions"
    )
    assert (
        normalize_chat_completions_url("ollama", "http://host.docker.internal:11434")
        == "http://host.docker.internal:11434/v1/chat/completions"
    )
    assert (
        models_url_for_provider("openai-compatible", "http://host.docker.internal:1234/v1")
        == "http://host.docker.internal:1234/v1/models"
    )
    assert (
        models_url_for_provider("ollama", "http://host.docker.internal:11434/v1/chat/completions")
        == "http://host.docker.internal:11434/api/tags"
    )


def test_ensure_bashrc_activation_replaces_existing_block(tmp_path: Path) -> None:
    """The bashrc activation block is idempotent."""
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text(
        "export EXISTING=1\n"
        "# Excalibur CCR activation\n"
        "old activation\n"
        "# End Excalibur CCR activation\n",
        encoding="utf-8",
    )

    ensure_bashrc_activation(bashrc)
    ensure_bashrc_activation(bashrc)

    content = bashrc.read_text(encoding="utf-8")
    assert "export EXISTING=1" in content
    assert "old activation" not in content
    assert content.count("# Excalibur CCR activation\n") == 1
