"""Helpers for managing local LLM routing through Claude Code Router."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

LOCAL_PROVIDER_NAME = "localLLM"
PROVIDER_OPENAI_COMPATIBLE = "openai-compatible"
PROVIDER_OLLAMA = "ollama"
PROVIDER_TYPES = (PROVIDER_OPENAI_COMPATIBLE, PROVIDER_OLLAMA)
DEFAULT_API_BASE_URL = "http://host.docker.internal:1234/v1/chat/completions"
DEFAULT_OLLAMA_BASE_URL = "http://host.docker.internal:11434"
DEFAULT_MODELS = ["qwen/qwen3-coder-30b", "openai/gpt-oss-20b"]
DEFAULT_SELECTED_MODEL = "openai/gpt-oss-20b"
ROUTE_KEYS = ("default", "background", "think", "longContext", "webSearch")
DEFAULT_ROUTE_MODELS = {
    "default": "openai/gpt-oss-20b",
    "background": "openai/gpt-oss-20b",
    "think": "qwen/qwen3-coder-30b",
    "longContext": "qwen/qwen3-coder-30b",
    "webSearch": "openai/gpt-oss-20b",
}
DEFAULT_LONG_CONTEXT_THRESHOLD = 60000

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class LocalLLMSettings:
    """Local LLM settings exposed through the web interface."""

    provider_type: str = PROVIDER_OPENAI_COMPATIBLE
    api_base_url: str = DEFAULT_API_BASE_URL
    api_key: str = ""
    enforce_ssl: bool = False
    models: list[str] = field(default_factory=lambda: list(DEFAULT_MODELS))
    selected_model: str = DEFAULT_SELECTED_MODEL
    context_window: int = DEFAULT_LONG_CONTEXT_THRESHOLD
    routes: dict[str, str] = field(default_factory=dict)
    long_context_threshold: int = DEFAULT_LONG_CONTEXT_THRESHOLD


def normalize_models(models: list[str] | str) -> list[str]:
    """Normalize model names from a list or newline/comma separated string."""
    raw_models = models.replace(",", "\n").splitlines() if isinstance(models, str) else models

    normalized: list[str] = []
    for model in raw_models:
        model_name = str(model).strip()
        if model_name and model_name not in normalized:
            normalized.append(model_name)

    if not normalized:
        raise ValueError("At least one local model is required")

    return normalized


def parse_context_window(value: object) -> int:
    """Parse a context window length from JSON or config data."""
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ValueError("Context window length must be a number")
    context_window = int(value)
    if context_window < 1000:
        raise ValueError("Context window length must be at least 1000")
    return context_window


def validate_settings(settings: LocalLLMSettings) -> None:
    """Validate a local LLM settings object before writing it to disk."""
    if settings.provider_type not in PROVIDER_TYPES:
        raise ValueError(f"Provider type must be one of: {', '.join(PROVIDER_TYPES)}")

    if not settings.api_base_url.startswith(("http://", "https://")):
        raise ValueError("API base URL must start with http:// or https://")

    if (
        settings.provider_type == PROVIDER_OPENAI_COMPATIBLE
        and settings.enforce_ssl
        and urllib.parse.urlparse(settings.api_base_url).scheme != "https"
    ):
        raise ValueError("Enforce SSL requires an https:// OpenAI-compatible URL")

    models = normalize_models(settings.models)
    if settings.selected_model not in models:
        raise ValueError("Selected model must be in the models list")

    parse_context_window(settings.context_window)


def default_router() -> JsonObject:
    """Return a CCR Router object using the default local model routes."""
    router: JsonObject = dict.fromkeys(
        ROUTE_KEYS,
        f"{LOCAL_PROVIDER_NAME},{DEFAULT_SELECTED_MODEL}",
    )
    router["longContextThreshold"] = DEFAULT_LONG_CONTEXT_THRESHOLD
    return router


def default_routes(selected_model: str = DEFAULT_SELECTED_MODEL) -> dict[str, str]:
    """Return hidden CCR route settings using one selected model everywhere."""
    return dict.fromkeys(ROUTE_KEYS, selected_model)


def default_config() -> JsonObject:
    """Return a minimal CCR config with local LLM routing enabled."""
    return {
        "LOG": False,
        "LOG_LEVEL": "debug",
        "CLAUDE_PATH": "",
        "HOST": "127.0.0.1",
        "PORT": 3456,
        "APIKEY": "",
        "API_TIMEOUT_MS": "600000",
        "PROXY_URL": "",
        "transformers": [],
        "Providers": [
            {
                "name": LOCAL_PROVIDER_NAME,
                "api_base_url": DEFAULT_API_BASE_URL,
                "api_key": "not-needed",
                "models": list(DEFAULT_MODELS),
            }
        ],
        "StatusLine": {
            "enabled": False,
            "currentStyle": "default",
            "default": {"modules": []},
            "powerline": {"modules": []},
        },
        "Router": default_router(),
        "Excalibur": {
            "provider_type": PROVIDER_OPENAI_COMPATIBLE,
            "enforce_ssl": False,
            "selected_model": DEFAULT_SELECTED_MODEL,
            "context_window": DEFAULT_LONG_CONTEXT_THRESHOLD,
        },
        "CUSTOM_ROUTER_PATH": "",
    }


def load_config(config_path: Path, template_path: Path | None = None) -> JsonObject:
    """Load the active CCR config, a template, or a built-in default."""
    for path in (config_path, template_path):
        if path and path.exists():
            with path.open("r", encoding="utf-8") as config_file:
                loaded = json.load(config_file)
            if isinstance(loaded, dict):
                return cast(JsonObject, loaded)
            raise ValueError(f"{path} does not contain a JSON object")

    return default_config()


def get_local_provider(config: JsonObject) -> JsonObject:
    """Return the localLLM provider, creating it when missing."""
    providers_value = config.setdefault("Providers", [])
    if not isinstance(providers_value, list):
        providers_value = []
        config["Providers"] = providers_value

    providers = providers_value
    for provider in providers:
        if isinstance(provider, dict) and provider.get("name") == LOCAL_PROVIDER_NAME:
            return cast(JsonObject, provider)

    provider = {
        "name": LOCAL_PROVIDER_NAME,
        "api_base_url": DEFAULT_API_BASE_URL,
        "api_key": "not-needed",
        "models": list(DEFAULT_MODELS),
    }
    providers.append(provider)
    return provider


def _extract_route_model(router: JsonObject, route_key: str, fallback: str) -> str:
    route_value = router.get(route_key)
    if isinstance(route_value, str):
        prefix = f"{LOCAL_PROVIDER_NAME},"
        if route_value.startswith(prefix):
            return route_value[len(prefix) :]
        if "," not in route_value:
            return route_value
    return fallback


def _metadata_from_config(config: JsonObject) -> JsonObject:
    metadata = config.get("Excalibur", {})
    return metadata if isinstance(metadata, dict) else {}


def _guess_provider_type(config: JsonObject, api_base_url: str) -> str:
    metadata = _metadata_from_config(config)
    provider_type = metadata.get("provider_type")
    if isinstance(provider_type, str) and provider_type in PROVIDER_TYPES:
        return provider_type

    if "11434" in api_base_url or "/api/" in api_base_url:
        return PROVIDER_OLLAMA
    return PROVIDER_OPENAI_COMPATIBLE


def normalize_chat_completions_url(provider_type: str, api_base_url: str) -> str:
    """Normalize a provider base URL into CCR's chat-completions endpoint."""
    url = api_base_url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ValueError("API base URL must start with http:// or https://")

    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"

    if provider_type == PROVIDER_OLLAMA:
        parsed = urllib.parse.urlparse(url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        return f"{root}/v1/chat/completions"

    return f"{url}/v1/chat/completions"


def models_url_for_provider(
    provider_type: str, api_base_url: str, enforce_ssl: bool = False
) -> str:
    """Return the URL used by the fetch-models button."""
    url = api_base_url.strip().rstrip("/")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("API base URL must start with http:// or https://")
    if provider_type == PROVIDER_OPENAI_COMPATIBLE and enforce_ssl and parsed.scheme != "https":
        raise ValueError("Enforce SSL requires an https:// OpenAI-compatible URL")

    if provider_type == PROVIDER_OLLAMA:
        root = f"{parsed.scheme}://{parsed.netloc}"
        return f"{root}/api/tags"

    if url.endswith("/chat/completions"):
        return f"{url.removesuffix('/chat/completions')}/models"
    if url.endswith("/v1"):
        return f"{url}/models"
    return f"{url}/v1/models"


def fetch_models(provider_type: str, api_base_url: str, enforce_ssl: bool = False) -> list[str]:
    """Fetch available models from an OpenAI-compatible or Ollama endpoint."""
    if provider_type not in PROVIDER_TYPES:
        raise ValueError(f"Provider type must be one of: {', '.join(PROVIDER_TYPES)}")

    request = urllib.request.Request(
        models_url_for_provider(provider_type, api_base_url, enforce_ssl),
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not fetch models: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Model endpoint did not return valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("Model endpoint returned an unexpected response")

    if provider_type == PROVIDER_OLLAMA:
        ollama_models = payload.get("models", [])
        if not isinstance(ollama_models, list):
            raise ValueError("Ollama response did not contain a models list")
        return normalize_models(
            [model.get("name", "") for model in ollama_models if isinstance(model, dict)]
        )

    openai_models = payload.get("data", [])
    if not isinstance(openai_models, list):
        raise ValueError("OpenAI-compatible response did not contain a data list")
    return normalize_models(
        [model.get("id", "") for model in openai_models if isinstance(model, dict)]
    )


def settings_from_config(config: JsonObject) -> LocalLLMSettings:
    """Convert a CCR config object into local LLM settings."""
    provider = get_local_provider(config)
    raw_models = provider.get("models", DEFAULT_MODELS)
    if isinstance(raw_models, list):
        models = normalize_models([str(model) for model in raw_models])
    else:
        models = list(DEFAULT_MODELS)

    api_base_url = provider.get("api_base_url")
    if not isinstance(api_base_url, str) or not api_base_url.strip():
        api_base_url = DEFAULT_API_BASE_URL
    provider_type = _guess_provider_type(config, api_base_url)

    metadata = _metadata_from_config(config)
    enforce_ssl = bool(metadata.get("enforce_ssl", False))
    raw_api_key = provider.get("api_key", "")
    api_key = raw_api_key if isinstance(raw_api_key, str) and raw_api_key != "not-needed" else ""

    router_value = config.get("Router", {})
    router = router_value if isinstance(router_value, dict) else default_router()
    router_object = cast(JsonObject, router)

    routes: dict[str, str] = {}
    for route_key in ROUTE_KEYS:
        fallback = DEFAULT_ROUTE_MODELS[route_key]
        route_model = _extract_route_model(router_object, route_key, fallback)
        routes[route_key] = route_model if route_model in models else models[0]

    metadata_model = metadata.get("selected_model")
    selected_model = (
        metadata_model
        if isinstance(metadata_model, str) and metadata_model in models
        else routes.get("default", models[0])
    )

    threshold_value: object = router_object.get(
        "longContextThreshold", DEFAULT_LONG_CONTEXT_THRESHOLD
    )
    metadata_context_window: object = metadata.get("context_window", threshold_value)
    try:
        context_window = parse_context_window(metadata_context_window)
    except (TypeError, ValueError):
        context_window = DEFAULT_LONG_CONTEXT_THRESHOLD

    return LocalLLMSettings(
        provider_type=provider_type,
        api_base_url=api_base_url,
        api_key=api_key,
        enforce_ssl=enforce_ssl,
        models=models,
        selected_model=selected_model,
        context_window=context_window,
        routes=default_routes(selected_model),
        long_context_threshold=context_window,
    )


def apply_settings(config: JsonObject, settings: LocalLLMSettings) -> JsonObject:
    """Apply local LLM settings to a CCR config object."""
    validate_settings(settings)
    models = normalize_models(settings.models)
    selected_model = settings.selected_model

    provider = get_local_provider(config)
    provider["api_base_url"] = normalize_chat_completions_url(
        settings.provider_type,
        settings.api_base_url,
    )
    provider["api_key"] = (
        settings.api_key
        if settings.provider_type == PROVIDER_OPENAI_COMPATIBLE and settings.api_key
        else "not-needed"
    )
    provider["models"] = models

    router: JsonObject = {}
    for route_key in ROUTE_KEYS:
        router[route_key] = f"{LOCAL_PROVIDER_NAME},{selected_model}"
    router["longContextThreshold"] = settings.context_window
    config["Router"] = router
    config["Excalibur"] = {
        "provider_type": settings.provider_type,
        "enforce_ssl": settings.enforce_ssl,
        "selected_model": selected_model,
        "context_window": settings.context_window,
        "api_key_configured": bool(settings.api_key),
    }

    config.setdefault("HOST", "127.0.0.1")
    config.setdefault("PORT", 3456)
    config.setdefault("API_TIMEOUT_MS", "600000")
    config.setdefault("CUSTOM_ROUTER_PATH", "")
    return config


def ensure_local_llm_config(
    config_path: Path, template_path: Path | None = None
) -> LocalLLMSettings:
    """Ensure a writable CCR config exists and returns the active settings."""
    config = load_config(config_path, template_path)
    settings = settings_from_config(config)
    save_local_llm_config(settings, config_path, template_path, existing_config=config)
    return settings


def save_local_llm_config(
    settings: LocalLLMSettings,
    config_path: Path,
    template_path: Path | None = None,
    existing_config: JsonObject | None = None,
) -> JsonObject:
    """Write local LLM settings to the CCR config file."""
    config = existing_config or load_config(config_path, template_path)
    updated_config = apply_settings(config, settings)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as config_file:
        json.dump(updated_config, config_file, indent=2)
        config_file.write("\n")

    return updated_config


def _parse_routes(args: argparse.Namespace, models: list[str]) -> dict[str, str]:
    routes: dict[str, str] = {}
    for route_key in ROUTE_KEYS:
        value = getattr(args, route_key)
        routes[route_key] = value if isinstance(value, str) and value else models[0]
    return routes


def build_parser() -> argparse.ArgumentParser:
    """Build the small command line interface used by the container entrypoint."""
    parser = argparse.ArgumentParser(description="Manage Excalibur local LLM CCR config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create or normalize local LLM config")
    init_parser.add_argument("--config", type=Path, required=True)
    init_parser.add_argument("--template", type=Path)
    init_parser.add_argument("--provider-type", default=PROVIDER_OPENAI_COMPATIBLE)
    init_parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    init_parser.add_argument("--enforce-ssl", action="store_true")
    init_parser.add_argument("--models", default="\n".join(DEFAULT_MODELS))
    init_parser.add_argument("--selected-model", default=DEFAULT_SELECTED_MODEL)
    init_parser.add_argument("--context-window", type=int, default=DEFAULT_LONG_CONTEXT_THRESHOLD)
    for route_key in ROUTE_KEYS:
        init_parser.add_argument(f"--{route_key}", default=DEFAULT_ROUTE_MODELS[route_key])
    init_parser.add_argument(
        "--long-context-threshold",
        type=int,
        default=DEFAULT_LONG_CONTEXT_THRESHOLD,
    )

    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        models = normalize_models(args.models)
        selected_model = args.selected_model if args.selected_model in models else models[0]
        settings = LocalLLMSettings(
            provider_type=args.provider_type,
            api_base_url=args.api_base_url,
            enforce_ssl=args.enforce_ssl,
            models=models,
            selected_model=selected_model,
            context_window=args.context_window,
            routes=default_routes(selected_model),
            long_context_threshold=args.context_window,
        )
        save_local_llm_config(settings, args.config, args.template)
        print(f"Local LLM CCR config written to {args.config}")


if __name__ == "__main__":
    main()
