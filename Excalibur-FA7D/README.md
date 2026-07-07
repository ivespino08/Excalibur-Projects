# Excalibur

AI-powered autonomous penetration testing agent with evidence-guided attack tree search (EGATS) planning. Solves CTF challenges, Hack The Box machines, and authorized security assessments.

## Prerequisites

- **Docker** -- [Install Docker](https://docs.docker.com/get-docker/)
- **LLM Provider** (one of):
  - Claude subscription (OAuth login)
  - Anthropic API key
  - OpenRouter API key
  - Local LLM (LM Studio, Ollama, etc.)

## Installation

```bash
make install          # Build Docker image
make config           # Configure authentication (first time)
make connect          # Connect to container
```

## Usage

Inside the container:

```bash
# Interactive TUI mode (default)
excalibur --target 10.10.11.234

# Non-interactive mode
excalibur --target 10.10.11.100 --non-interactive

# With context hint
excalibur --target 10.10.11.50 --instruction "WordPress site, check plugin vulns"
```

**Keyboard shortcuts:** `F1` Help | `Ctrl+P` Pause/Resume | `Ctrl+Q` Quit

## Docker Commands

| Command | Description |
|---------|-------------|
| `make install` | Build the Docker image |
| `make config` | Configure API authentication |
| `make connect` | Start container and connect over SSH |
| `make ssh` | SSH to a running container |
| `make web` | Print the local web config UI URL |
| `make attach` | Attach to the container TTY |
| `make start` | Start container in the background |
| `make shell` | Open a new bash shell in the running container |
| `make logs` | Follow Docker Compose logs |
| `make stop` | Stop container (config persists) |
| `make clean-docker` | Remove everything including config |

Default local endpoints:

- Web config UI: `http://127.0.0.1:8080`
- SSH: `ssh -p 2222 pentester@127.0.0.1`
- Default SSH password: `excalibur`

Common Docker Compose overrides:

| Variable | Purpose |
|----------|---------|
| `EXCALIBUR_AUTH_MODE` | Authentication mode: `local`, `openrouter`, `anthropic`, or `manual` |
| `EXCALIBUR_WEB_PORT` | Host port for the web config UI, default `8080` |
| `EXCALIBUR_SSH_PORT` | Host port for SSH, default `2222` |
| `EXCALIBUR_SSH_PASSWORD` | Password for the `pentester` account |
| `ANTHROPIC_API_KEY` | Anthropic API key for `anthropic` mode |
| `OPENROUTER_API_KEY` | OpenRouter API key for `openrouter` mode |

The container entrypoint also honors `EXCALIBUR_SSH_AUTHORIZED_KEYS`, `EXCALIBUR_WEB_ENABLED`, `EXCALIBUR_RUNTIME_CONFIG`, and `EXCALIBUR_CCR_LOG` if you inject those variables directly into the container.

For a host-networked alternative (e.g. multi-interface setups), use `docker compose -f docker-compose.host.yml up -d` instead -- see the comments in that file for the tradeoffs.

## Running Tests

```bash
make test             # All tests (excludes Docker tests)
make test-cov         # Tests with coverage report
make lint             # Ruff linter
make typecheck        # Mypy type checking
make check            # All checks (lint + typecheck)
```

## License

MIT License. See `LICENSE.md`.

**Disclaimer:** For educational purposes and authorized security testing only.
