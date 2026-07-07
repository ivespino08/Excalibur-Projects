"""Small web interface for configuring local LLM routing."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast

from excalibur.core.activity_log import DEFAULT_ACTIVITY_LOG_PATH
from excalibur.server.local_llm_config import (
    DEFAULT_API_BASE_URL,
    DEFAULT_LONG_CONTEXT_THRESHOLD,
    DEFAULT_OLLAMA_BASE_URL,
    LOCAL_PROVIDER_NAME,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI_COMPATIBLE,
    JsonObject,
    LocalLLMSettings,
    default_routes,
    fetch_models,
    load_config,
    normalize_models,
    parse_context_window,
    save_local_llm_config,
    settings_from_config,
    validate_settings,
)
from excalibur.server.mcp_config import (
    add_mcp_server,
    list_mcp_servers,
    parse_mcp_add_payload,
    parse_mcp_remove_payload,
    remove_mcp_server,
)
from excalibur.server.runtime_config import (
    DEFAULT_RUNTIME_CONFIG_PATH,
    default_runtime_settings,
    load_runtime_config,
    save_runtime_config,
    settings_from_runtime_config,
)

DEFAULT_CONFIG_PATH = Path("/home/pentester/.claude-code-router/config.json")
DEFAULT_TEMPLATE_PATH = Path("/app/scripts/ccr-config-template.json")
DEFAULT_CCR_LOG_PATH = Path("/tmp/ccr.log")
DEFAULT_WEB_HOST = "0.0.0.0"
DEFAULT_WEB_PORT = 8080


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Excalibur Local LLM</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f7f4;
      --panel: #ffffff;
      --text: #171717;
      --muted: #5f6368;
      --line: #d9ddd6;
      --accent: #16685b;
      --accent-strong: #0f4f45;
      --warn: #a75518;
      --error: #a52222;
      --ok: #1e6b3c;
      --shadow: 0 10px 30px rgba(23, 23, 23, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }
    main {
      width: min(1120px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 36px;
    }
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 20px;
      margin-bottom: 20px;
    }
    h1 {
      margin: 0;
      font-size: clamp(1.5rem, 2.4vw, 2.2rem);
      font-weight: 720;
      letter-spacing: 0;
    }
    .subtitle {
      margin: 6px 0 0;
      color: var(--muted);
      max-width: 680px;
    }
    .status {
      min-width: 210px;
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
    }
    .pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 7px 10px;
      background: rgba(255, 255, 255, 0.72);
      color: var(--muted);
      font-size: 0.9rem;
      white-space: nowrap;
    }
    .pill.ok { color: var(--ok); border-color: rgba(30, 107, 60, 0.35); }
    .pill.warn { color: var(--warn); border-color: rgba(167, 85, 24, 0.35); }
    .pill.error { color: var(--error); border-color: rgba(165, 34, 34, 0.35); }
    .tabs {
      display: flex;
      gap: 8px;
      margin: 0 0 16px;
      border-bottom: 1px solid var(--line);
      overflow-x: auto;
    }
    .tab-button {
      background: transparent;
      color: var(--muted);
      border: 1px solid transparent;
      border-radius: 6px 6px 0 0;
      min-height: 40px;
      padding: 8px 12px;
    }
    .tab-button:hover {
      background: #ecefed;
      color: var(--text);
    }
    .tab-button.active {
      background: var(--panel);
      color: var(--accent);
      border-color: var(--line);
      border-bottom-color: var(--panel);
      margin-bottom: -1px;
    }
    #mcpTab,
    #mcpPanel,
    #mcpStatus {
      display: none;
    }
    .panel-view.hidden { display: none; }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
      gap: 16px;
      align-items: start;
    }
    .stack {
      display: grid;
      gap: 16px;
      min-width: 0;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 18px;
    }
    h2 {
      margin: 0 0 14px;
      font-size: 1rem;
      letter-spacing: 0;
    }
    label {
      display: block;
      color: var(--muted);
      font-size: 0.9rem;
      min-height: 20px;
      margin: 0 0 6px;
    }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font: inherit;
      height: 42px;
      padding: 8px 10px;
      outline: none;
    }
    textarea {
      height: auto;
      min-height: 128px;
      resize: vertical;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 0.92rem;
    }
    input:focus, textarea:focus, select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(22, 104, 91, 0.14);
    }
    .field {
      min-width: 0;
      margin-bottom: 14px;
    }
    .field.flush-label > label {
      visibility: hidden;
    }
    .routes {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 10px;
      margin-top: 16px;
      flex-wrap: wrap;
    }
    button {
      border: 0;
      border-radius: 6px;
      height: 42px;
      padding: 8px 14px;
      background: var(--accent);
      color: #fff;
      font: inherit;
      font-weight: 680;
      cursor: pointer;
      white-space: nowrap;
      width: auto;
      max-width: 100%;
    }
    button:hover { background: var(--accent-strong); }
    button.secondary {
      background: #ecefed;
      color: var(--text);
    }
    button.secondary:hover { background: #e0e5e2; }
    button.danger {
      background: #a52222;
    }
    button.danger:hover { background: #831919; }
    .message {
      min-height: 22px;
      color: var(--muted);
      font-size: 0.92rem;
      margin-right: auto;
    }
    .form-message {
      width: 100%;
      margin: 10px 0 0;
    }
    .message.error { color: var(--error); }
    .message.ok { color: var(--ok); }
    .meta {
      display: grid;
      gap: 10px;
      color: var(--muted);
      font-size: 0.92rem;
    }
    .meta strong {
      color: var(--text);
      font-weight: 680;
    }
    pre {
      margin: 14px 0 0;
      padding: 12px;
      background: #101513;
      color: #d7e5df;
      border-radius: 6px;
      min-height: 180px;
      max-height: 360px;
      overflow: auto;
      font-size: 0.84rem;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .runtime-output {
      height: 320px;
      min-height: 320px;
      max-height: 320px;
      overflow: auto;
    }
    .log-caption {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 0.88rem;
    }
    .compact-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .model-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: end;
    }
    .model-row button {
      margin-bottom: 14px;
      white-space: nowrap;
    }
    .checkbox-row {
      height: 42px;
      display: flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 10px;
      background: #fff;
    }
    .checkbox-row input {
      width: 16px;
      height: 16px;
      min-width: 16px;
      padding: 0;
      margin: 0;
    }
    .checkbox-row label {
      min-height: auto;
      margin: 0;
      color: var(--text);
      line-height: 1;
    }
    .mcp-output {
      min-height: 260px;
    }
    .mcp-summary {
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.92rem;
    }
    .mcp-table-wrap {
      margin-top: 12px;
      overflow-x: auto;
    }
    .mcp-table {
      width: 100%;
      min-width: 720px;
      border-collapse: collapse;
    }
    .mcp-table th,
    .mcp-table td {
      text-align: left;
      vertical-align: top;
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      font-size: 0.92rem;
    }
    .mcp-table th {
      color: var(--muted);
      font-size: 0.85rem;
      font-weight: 680;
    }
    .mcp-table td code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 0.86rem;
    }
    .mcp-table .empty {
      color: var(--muted);
      text-align: center;
      padding: 20px 8px;
    }
    .mcp-raw {
      margin-top: 12px;
    }
    .mcp-raw summary {
      cursor: pointer;
      color: var(--muted);
      font-size: 0.9rem;
      list-style: none;
    }
    .mcp-raw summary::-webkit-details-marker {
      display: none;
    }
    @media (max-width: 840px) {
      header { display: block; }
      .status { justify-content: flex-start; margin-top: 14px; }
      .grid { grid-template-columns: 1fr; }
      .routes { grid-template-columns: 1fr; }
      .compact-grid { grid-template-columns: 1fr; }
      .model-row { grid-template-columns: 1fr; }
      main { width: min(100vw - 20px, 1120px); padding-top: 18px; }
      section { padding: 14px; }
      .actions { align-items: stretch; flex-direction: column; }
      .message { margin-right: 0; }
      button { width: 100%; white-space: normal; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Excalibur Local LLM</h1>
        <p class="subtitle">Configure the local OpenAI-compatible model endpoint used by Claude Code Router inside this container.</p>
      </div>
      <div class="status">
        <span id="routerStatus" class="pill">Router unknown</span>
        <span id="providerStatus" class="pill">localLLM</span>
        <span id="mcpStatus" class="pill">MCP unknown</span>
      </div>
    </header>

    <div class="tabs" role="tablist">
      <button id="llmTab" class="tab-button active" type="button" role="tab" aria-controls="llmPanel">Local LLM</button>
      <button id="mcpTab" class="tab-button" type="button" role="tab" aria-controls="mcpPanel">MCP Servers</button>
    </div>

    <div id="llmPanel" class="panel-view">
      <div class="grid">
        <div class="stack">
          <section>
            <h2>Model Routing</h2>
            <form id="configForm">
              <div class="compact-grid">
                <div class="field">
                  <label for="providerType">Provider</label>
                  <select id="providerType">
                    <option value="openai-compatible">OpenAI-compatible</option>
                    <option value="ollama">Ollama</option>
                  </select>
                </div>
                <div class="field flush-label" id="enforceSslGroup">
                  <label for="enforceSsl">Enforce SSL</label>
                  <div class="checkbox-row">
                    <input id="enforceSsl" type="checkbox">
                    <label for="enforceSsl">Enforce SSL</label>
                  </div>
                </div>
                <div class="field">
                  <label for="contextWindow">Context window length</label>
                  <input id="contextWindow" type="number" min="1000" step="1000">
                </div>
              </div>

              <div class="field">
                <label for="apiBaseUrl">API base URL</label>
                <input id="apiBaseUrl" name="apiBaseUrl" autocomplete="off" spellcheck="false">
              </div>

              <div class="field" id="apiKeyGroup">
                <label for="apiKey">API key</label>
                <input id="apiKey" type="password" autocomplete="off" spellcheck="false" placeholder="Optional">
              </div>

              <div class="model-row">
                <div class="field">
                  <label for="selectedModel">Model</label>
                  <select id="selectedModel"></select>
                </div>
                <button class="secondary" type="button" id="fetchModelsButton">Fetch models</button>
              </div>

              <div class="actions">
                <button class="secondary" type="button" id="refreshButton">Refresh</button>
                <button type="submit">Save and restart router</button>
              </div>
              <div id="message" class="message form-message" role="status" aria-live="polite"></div>
            </form>
          </section>

          <section>
            <h2>Live Activity</h2>
            <div class="meta">
              <div><strong>Activity log:</strong> <span id="activityLogPath"></span></div>
              <div><strong>Router log:</strong> <span id="routerLogPath"></span></div>
            </div>
            <div class="log-caption">Live feed from Excalibur, Claude Code, and Claude Code Router.</div>
            <pre id="logOutput" class="runtime-output"></pre>
          </section>
        </div>

        <section>
          <h2>Runtime</h2>
          <div class="meta">
            <div><strong>Provider:</strong> <span id="providerName"></span></div>
            <div><strong>Model:</strong> <span id="runtimeModel"></span></div>
            <div><strong>YAML:</strong> <span id="runtimeConfigPath"></span></div>
            <div><strong>Router JSON:</strong> <span id="configPath"></span></div>
            <div><strong>SSH:</strong> <span>ssh -p 2222 pentester@127.0.0.1</span></div>
            <div><strong>Run:</strong> <span>excalibur-run --target TARGET</span></div>
          </div>
        </section>
      </div>
    </div>

    <div id="mcpPanel" class="panel-view hidden">
      <div class="grid">
        <section>
          <h2>MCP Servers</h2>
          <div class="actions">
            <div id="mcpMessage" class="message"></div>
            <button class="secondary" type="button" id="refreshMcpButton">Refresh</button>
          </div>
          <div class="mcp-summary"><strong>Configured:</strong> <span id="mcpCount">0</span></div>
          <div class="mcp-table-wrap">
            <table class="mcp-table" aria-label="Configured MCP servers">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Transport</th>
                  <th>Endpoint / Command</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody id="mcpTableBody">
                <tr>
                  <td class="empty" colspan="4">No MCP servers configured.</td>
                </tr>
              </tbody>
            </table>
          </div>
          <details class="mcp-raw">
            <summary>Raw output</summary>
            <pre id="mcpOutput" class="mcp-output"></pre>
          </details>
        </section>

        <section>
          <h2>Add Server</h2>
          <form id="mcpAddForm">
            <div class="compact-grid">
              <div class="field">
                <label for="mcpName">Name</label>
                <input id="mcpName" autocomplete="off" spellcheck="false">
              </div>
              <div class="field">
                <label for="mcpScope">Scope</label>
                <select id="mcpScope">
                  <option value="project">project</option>
                  <option value="local">local</option>
                  <option value="user">user</option>
                </select>
              </div>
              <div class="field">
                <label for="mcpTransport">Transport</label>
                <select id="mcpTransport">
                  <option value="stdio">stdio</option>
                  <option value="http">http</option>
                  <option value="sse">sse</option>
                </select>
              </div>
            </div>
            <div class="field">
              <label for="mcpCommandOrUrl">Command or URL</label>
              <input id="mcpCommandOrUrl" autocomplete="off" spellcheck="false">
            </div>
            <div class="field">
              <label for="mcpArgs">Arguments</label>
              <input id="mcpArgs" autocomplete="off" spellcheck="false">
            </div>
            <div class="field">
              <label for="mcpEnv">Environment</label>
              <textarea id="mcpEnv" spellcheck="false"></textarea>
            </div>
            <div class="field">
              <label for="mcpHeaders">Headers</label>
              <textarea id="mcpHeaders" spellcheck="false"></textarea>
            </div>
            <div class="actions">
              <button type="submit">Add MCP server</button>
            </div>
          </form>

          <h2>Remove Server</h2>
          <form id="mcpRemoveForm">
            <div class="compact-grid">
              <div class="field">
                <label for="mcpRemoveName">Name</label>
                <input id="mcpRemoveName" autocomplete="off" spellcheck="false">
              </div>
              <div class="field">
                <label for="mcpRemoveScope">Scope</label>
                <select id="mcpRemoveScope">
                  <option value="">any</option>
                  <option value="project">project</option>
                  <option value="local">local</option>
                  <option value="user">user</option>
                </select>
              </div>
              <div class="field"></div>
            </div>
            <div class="actions">
              <button class="danger" type="submit">Remove MCP server</button>
            </div>
          </form>
        </section>
      </div>
    </div>
  </main>

  <script>
    const message = document.querySelector("#message");
    const mcpMessage = document.querySelector("#mcpMessage");
    const mcpOutput = document.querySelector("#mcpOutput");
    const mcpTableBody = document.querySelector("#mcpTableBody");
    const mcpCount = document.querySelector("#mcpCount");
    const providerType = document.querySelector("#providerType");
    const enforceSsl = document.querySelector("#enforceSsl");
    const apiBaseUrl = document.querySelector("#apiBaseUrl");
    const apiKey = document.querySelector("#apiKey");
    const selectedModel = document.querySelector("#selectedModel");
    const contextWindow = document.querySelector("#contextWindow");
    const logOutput = document.querySelector("#logOutput");
    let availableModels = [];
    let defaults = {};

    function setMessage(text, kind = "") {
      message.textContent = text;
      message.className = kind ? `message ${kind}` : "message";
    }

    function setMcpMessage(text, kind = "") {
      mcpMessage.textContent = text;
      mcpMessage.className = kind ? `message ${kind}` : "message";
    }

    function mcpHealthClass(server) {
      if (server.health === "ok") {
        return "ok";
      }
      if (server.health === "error") {
        return "error";
      }
      if (server.auth_required || server.health === "warn") {
        return "warn";
      }
      return "";
    }

    function splitLines(value) {
      return value.split("\\n").map((item) => item.trim()).filter(Boolean);
    }

    function showPanel(name) {
      const llmActive = name === "llm";
      document.querySelector("#llmPanel").classList.toggle("hidden", !llmActive);
      document.querySelector("#mcpPanel").classList.toggle("hidden", llmActive);
      document.querySelector("#llmTab").classList.toggle("active", llmActive);
      document.querySelector("#mcpTab").classList.toggle("active", !llmActive);
      if (!llmActive) {
        loadMcp().catch((error) => setMcpMessage(error.message, "error"));
      }
    }

    function updateProviderControls() {
      const isOpenAI = providerType.value === "openai-compatible";
      document.querySelector("#enforceSslGroup").style.display = isOpenAI ? "block" : "none";
      document.querySelector("#apiKeyGroup").style.display = isOpenAI ? "block" : "none";
      if (!isOpenAI) {
        enforceSsl.checked = false;
        apiKey.value = "";
      }
    }

    function updateModelOptions(models, preferredModel = "") {
      const currentModel = selectedModel.value;
      const requestedModel = preferredModel || currentModel;
      availableModels = Array.from(new Set([requestedModel, ...models].filter(Boolean)));
      selectedModel.innerHTML = "";
      if (availableModels.length === 0) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "No models available";
        option.disabled = true;
        selectedModel.appendChild(option);
        selectedModel.value = "";
        return;
      }
      availableModels.forEach((model) => {
        const option = document.createElement("option");
        option.value = model;
        option.textContent = model;
        selectedModel.appendChild(option);
      });
      selectedModel.value = availableModels.includes(requestedModel) ? requestedModel : availableModels[0];
    }

    function updateStatus(payload) {
      const routerStatus = document.querySelector("#routerStatus");
      routerStatus.textContent = payload.ccr_running ? "Router running" : "Router stopped";
      routerStatus.className = payload.ccr_running ? "pill ok" : "pill warn";
      document.querySelector("#providerName").textContent = payload.provider_type;
      document.querySelector("#runtimeModel").textContent = payload.selected_model || "Not configured";
      document.querySelector("#runtimeConfigPath").textContent = payload.runtime_config_path;
      document.querySelector("#configPath").textContent = payload.config_path;
      document.querySelector("#activityLogPath").textContent = payload.activity_log_path;
      document.querySelector("#routerLogPath").textContent = payload.ccr_log_path;
      updateLogOutput(payload.combined_log || "No activity yet.");
    }

    function updateLogOutput(text) {
      const stickToBottom =
        logOutput.scrollTop + logOutput.clientHeight >= logOutput.scrollHeight - 40;
      logOutput.textContent = text || "No activity yet.";
      if (stickToBottom) {
        logOutput.scrollTop = logOutput.scrollHeight;
      }
    }

    function updateMcpStatus(payload) {
      const status = document.querySelector("#mcpStatus");
      status.textContent = payload.ok ? "MCP ready" : "MCP error";
      status.className = payload.ok ? "pill ok" : "pill warn";
      renderMcpServers(payload.servers || []);
      mcpOutput.textContent = payload.output || "No MCP servers configured.";
    }

    function renderMcpServers(servers) {
      mcpCount.textContent = String(servers.length);
      mcpTableBody.innerHTML = "";
      if (servers.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.className = "empty";
        cell.textContent = "No MCP servers configured.";
        row.appendChild(cell);
        mcpTableBody.appendChild(row);
        return;
      }

      servers.forEach((server) => {
        const row = document.createElement("tr");

        const nameCell = document.createElement("td");
        nameCell.textContent = server.name || "Unknown";

        const transportCell = document.createElement("td");
        transportCell.textContent = server.transport || "unknown";

        const endpointCell = document.createElement("td");
        const endpoint = server.endpoint || "—";
        const endpointCode = document.createElement("code");
        endpointCode.textContent = endpoint;
        endpointCell.appendChild(endpointCode);

        const statusCell = document.createElement("td");
        const badge = document.createElement("span");
        badge.className = `pill ${mcpHealthClass(server)}`;
        badge.textContent = server.status || "Unknown";
        statusCell.appendChild(badge);

        row.append(nameCell, transportCell, endpointCell, statusCell);
        mcpTableBody.appendChild(row);
      });
    }

    async function loadConfig() {
      setMessage("Loading...");
      const response = await fetch("/api/config");
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to load config");
      }
      defaults = payload.defaults || {};
      providerType.value = payload.provider_type;
      apiBaseUrl.value = payload.api_base_url;
      apiKey.value = "";
      apiKey.placeholder = payload.api_key_configured ? "Configured; leave blank to keep" : "Optional";
      enforceSsl.checked = Boolean(payload.enforce_ssl);
      contextWindow.value = payload.context_window;
      updateProviderControls();
      updateModelOptions(payload.models, payload.selected_model);
      updateStatus(payload);
      setMessage("Loaded", "ok");
    }

    async function saveConfig(event) {
      event.preventDefault();
      const model = selectedModel.value.trim();
      if (!model) {
        setMessage("Select a model before saving.", "error");
        return;
      }
      const models = availableModels.includes(model) ? availableModels : [model];
      const body = {
        provider_type: providerType.value,
        api_base_url: apiBaseUrl.value.trim(),
        api_key: apiKey.value,
        enforce_ssl: enforceSsl.checked,
        models,
        selected_model: model,
        context_window: Number(contextWindow.value),
      };
      setMessage("Saving...");
      const response = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to save config");
      }
      updateStatus(payload);
      setMessage(payload.restart.message, payload.restart.ok ? "ok" : "error");
    }

    async function fetchModels() {
      setMessage("Fetching models...");
      const response = await fetch("/api/models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider_type: providerType.value,
          api_base_url: apiBaseUrl.value.trim(),
          enforce_ssl: enforceSsl.checked,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to fetch models");
      }
      updateModelOptions(payload.models);
      if (!availableModels.includes(selectedModel.value) && availableModels.length > 0) {
        selectedModel.value = availableModels[0];
      }
      setMessage(`Fetched ${availableModels.length} model${availableModels.length === 1 ? "" : "s"}`, "ok");
    }

    async function loadMcp() {
      setMcpMessage("Loading...");
      const response = await fetch("/api/mcp");
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to load MCP servers");
      }
      updateMcpStatus(payload);
      setMcpMessage("Loaded", payload.ok ? "ok" : "error");
    }

    async function loadLogs() {
      const response = await fetch("/api/logs");
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to load activity log");
      }
      updateLogOutput(payload.combined_log || "No activity yet.");
    }

    async function addMcp(event) {
      event.preventDefault();
      setMcpMessage("Adding...");
      const body = {
        name: document.querySelector("#mcpName").value.trim(),
        scope: document.querySelector("#mcpScope").value,
        transport: document.querySelector("#mcpTransport").value,
        command_or_url: document.querySelector("#mcpCommandOrUrl").value.trim(),
        args: document.querySelector("#mcpArgs").value.trim(),
        env: splitLines(document.querySelector("#mcpEnv").value),
        headers: splitLines(document.querySelector("#mcpHeaders").value),
      };
      const response = await fetch("/api/mcp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to add MCP server");
      }
      updateMcpStatus(payload.list);
      setMcpMessage(payload.result.output || "MCP server added", payload.result.ok ? "ok" : "error");
    }

    async function removeMcp(event) {
      event.preventDefault();
      setMcpMessage("Removing...");
      const body = {
        name: document.querySelector("#mcpRemoveName").value.trim(),
        scope: document.querySelector("#mcpRemoveScope").value,
      };
      const response = await fetch("/api/mcp/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to remove MCP server");
      }
      updateMcpStatus(payload.list);
      setMcpMessage(payload.result.output || "MCP server removed", payload.result.ok ? "ok" : "error");
    }

    providerType.addEventListener("change", () => {
      updateProviderControls();
      if (providerType.value === "ollama" && defaults.ollama_api_base_url) {
        apiBaseUrl.value = defaults.ollama_api_base_url;
      } else if (providerType.value === "openai-compatible" && defaults.api_base_url) {
        apiBaseUrl.value = defaults.api_base_url;
      }
    });
    document.querySelector("#llmTab").addEventListener("click", () => showPanel("llm"));
    document.querySelector("#mcpTab").addEventListener("click", () => showPanel("mcp"));
    document.querySelector("#refreshButton").addEventListener("click", () => {
      loadConfig().catch((error) => setMessage(error.message, "error"));
    });
    document.querySelector("#fetchModelsButton").addEventListener("click", () => {
      fetchModels().catch((error) => setMessage(error.message, "error"));
    });
    document.querySelector("#refreshMcpButton").addEventListener("click", () => {
      loadMcp().catch((error) => setMcpMessage(error.message, "error"));
    });
    setInterval(() => {
      loadLogs().catch(() => {});
    }, 2000);
    document.querySelector("#configForm").addEventListener("submit", (event) => {
      saveConfig(event).catch((error) => setMessage(error.message, "error"));
    });
    document.querySelector("#mcpAddForm").addEventListener("submit", (event) => {
      addMcp(event).catch((error) => setMcpMessage(error.message, "error"));
    });
    document.querySelector("#mcpRemoveForm").addEventListener("submit", (event) => {
      removeMcp(event).catch((error) => setMcpMessage(error.message, "error"));
    });
    loadConfig().catch((error) => setMessage(error.message, "error"));
    loadMcp().catch(() => {});
    loadLogs().catch(() => {});
  </script>
</body>
</html>
"""


class ConfigHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying config paths for request handlers."""

    config_path: Path
    template_path: Path | None
    ccr_log_path: Path
    activity_log_path: Path
    runtime_config_path: Path

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        config_path: Path,
        template_path: Path | None,
        ccr_log_path: Path,
        activity_log_path: Path,
        runtime_config_path: Path,
    ) -> None:
        super().__init__(server_address, request_handler_class)
        self.config_path = config_path
        self.template_path = template_path
        self.ccr_log_path = ccr_log_path
        self.activity_log_path = activity_log_path
        self.runtime_config_path = runtime_config_path


class ConfigRequestHandler(BaseHTTPRequestHandler):
    """Request handler for the config UI and JSON API."""

    server: ConfigHTTPServer

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path in {"/", "/index.html"}:
            self._send_html(HTML)
            return
        if self.path == "/api/config":
            self._handle_get_config()
            return
        if self.path == "/api/mcp":
            self._handle_get_mcp()
            return
        if self.path == "/api/logs":
            self._handle_get_logs()
            return
        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path == "/api/config":
            self._handle_save_config()
            return
        if self.path == "/api/models":
            self._handle_fetch_models()
            return
        if self.path == "/api/mcp":
            self._handle_add_mcp()
            return
        if self.path == "/api/mcp/remove":
            self._handle_remove_mcp()
            return
        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        """Keep container logs focused on startup and errors."""
        return

    def _handle_get_config(self) -> None:
        try:
            self._send_json(self._config_payload())
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_save_config(self) -> None:
        try:
            body = self._read_json_body()
            settings = settings_from_payload(body)
            runtime_config = load_runtime_config(self.server.runtime_config_path)
            existing_runtime_settings = settings_from_runtime_config(runtime_config)
            existing_config = load_config(self.server.config_path, self.server.template_path)
            if settings.provider_type == PROVIDER_OPENAI_COMPATIBLE and not settings.api_key:
                existing_api_key = existing_runtime_settings.api_key
                if not existing_api_key:
                    existing_api_key = settings_from_config(existing_config).api_key
                settings = LocalLLMSettings(
                    provider_type=settings.provider_type,
                    api_base_url=settings.api_base_url,
                    api_key=existing_api_key,
                    enforce_ssl=settings.enforce_ssl,
                    models=settings.models,
                    selected_model=settings.selected_model,
                    context_window=settings.context_window,
                    routes=settings.routes,
                    long_context_threshold=settings.long_context_threshold,
                )
            save_runtime_config(
                settings,
                self.server.runtime_config_path,
                existing_config=runtime_config,
            )
            save_local_llm_config(
                settings,
                self.server.config_path,
                self.server.template_path,
                existing_config=existing_config,
            )
            ensure_bashrc_activation(Path.home() / ".bashrc")
            restart_result = restart_ccr(self.server.ccr_log_path)
            payload = self._config_payload()
            payload["restart"] = restart_result
            self._send_json(payload)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_fetch_models(self) -> None:
        try:
            body = self._read_json_body()
            provider_type = parse_provider_type(
                body.get("provider_type", PROVIDER_OPENAI_COMPATIBLE)
            )
            api_base_url = parse_api_base_url(body.get("api_base_url"))
            enforce_ssl = bool(body.get("enforce_ssl", False))
            models = fetch_models(provider_type, api_base_url, enforce_ssl)
            self._send_json({"models": models})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_get_mcp(self) -> None:
        try:
            result = list_mcp_servers()
            status = HTTPStatus.OK if result["ok"] else HTTPStatus.INTERNAL_SERVER_ERROR
            self._send_json(result, status)
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_get_logs(self) -> None:
        try:
            self._send_json(self._log_payload())
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_add_mcp(self) -> None:
        try:
            body = self._read_json_body()
            request = parse_mcp_add_payload(body)
            result = add_mcp_server(request)
            status = HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_REQUEST
            self._send_json({"result": result, "list": list_mcp_servers()}, status)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_remove_mcp(self) -> None:
        try:
            body = self._read_json_body()
            request = parse_mcp_remove_payload(body)
            result = remove_mcp_server(request)
            status = HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_REQUEST
            self._send_json({"result": result, "list": list_mcp_servers()}, status)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _config_payload(self) -> JsonObject:
        settings = load_last_used_settings(
            self.server.runtime_config_path,
            self.server.config_path,
        )
        payload = {
            "provider": LOCAL_PROVIDER_NAME,
            "provider_type": settings.provider_type,
            "api_base_url": settings.api_base_url,
            "api_key_configured": bool(settings.api_key),
            "enforce_ssl": settings.enforce_ssl,
            "models": settings.models,
            "selected_model": settings.selected_model,
            "context_window": settings.context_window,
            "routes": settings.routes,
            "long_context_threshold": settings.context_window,
            "ccr_running": ccr_running(),
            "runtime_config_path": str(self.server.runtime_config_path),
            "config_path": str(self.server.config_path),
            "defaults": {
                "provider_type": PROVIDER_OPENAI_COMPATIBLE,
                "api_base_url": DEFAULT_API_BASE_URL,
                "ollama_api_base_url": DEFAULT_OLLAMA_BASE_URL,
                "enforce_ssl": False,
                "models": [],
                "selected_model": "",
                "routes": {},
                "context_window": DEFAULT_LONG_CONTEXT_THRESHOLD,
                "long_context_threshold": DEFAULT_LONG_CONTEXT_THRESHOLD,
            },
        }
        payload.update(self._log_payload())
        return payload

    def _log_payload(self) -> JsonObject:
        activity_log = tail_file(self.server.activity_log_path)
        ccr_log = tail_file(self.server.ccr_log_path)
        return {
            "ccr_running": ccr_running(),
            "activity_log_path": str(self.server.activity_log_path),
            "ccr_log_path": str(self.server.ccr_log_path),
            "activity_log": activity_log,
            "ccr_log": ccr_log,
            "combined_log": combine_log_sections(
                activity_log,
                ccr_log,
                self.server.activity_log_path,
                self.server.ccr_log_path,
            ),
        }

    def _read_json_body(self) -> JsonObject:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("Request body is required")
        body = self.rfile.read(content_length)
        parsed = json.loads(body.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("Request body must be a JSON object")
        return cast(JsonObject, parsed)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: JsonObject, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def load_last_used_settings(
    runtime_config_path: Path,
    ccr_config_path: Path,
) -> LocalLLMSettings:
    """Load persisted UI settings, falling back to existing CCR JSON."""
    if runtime_config_path.exists():
        return settings_from_runtime_config(load_runtime_config(runtime_config_path))

    if ccr_config_path.exists():
        try:
            return settings_from_config(load_config(ccr_config_path, None))
        except (OSError, ValueError):
            return default_runtime_settings()

    return default_runtime_settings()


def parse_provider_type(value: object) -> str:
    """Parse the provider type from an API payload."""
    if not isinstance(value, str) or value not in {PROVIDER_OPENAI_COMPATIBLE, PROVIDER_OLLAMA}:
        raise ValueError("Provider must be openai-compatible or ollama")
    return value


def parse_api_base_url(value: object) -> str:
    """Parse a provider API URL from an API payload."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("API base URL is required")
    api_base_url = value.strip()
    if not api_base_url.startswith(("http://", "https://")):
        raise ValueError("API base URL must start with http:// or https://")
    return api_base_url


def settings_from_payload(payload: JsonObject) -> LocalLLMSettings:
    """Build validated settings from an API request body."""
    provider_type = parse_provider_type(payload.get("provider_type", PROVIDER_OPENAI_COMPATIBLE))
    api_base_url = parse_api_base_url(payload.get("api_base_url"))
    api_key_value = payload.get("api_key", "")
    if api_key_value is None:
        api_key = ""
    elif isinstance(api_key_value, str):
        api_key = api_key_value.strip()
    else:
        raise ValueError("API key must be a string")
    enforce_ssl = bool(payload.get("enforce_ssl", False))

    raw_models = payload.get("models")
    if isinstance(raw_models, list):
        models = normalize_models([str(model) for model in raw_models])
    elif isinstance(raw_models, str):
        models = normalize_models(raw_models)
    else:
        selected = payload.get("selected_model")
        if not isinstance(selected, str) or not selected.strip():
            raise ValueError("Selected model is required")
        models = normalize_models([selected])

    selected_model = payload.get("selected_model")
    if not isinstance(selected_model, str) or not selected_model.strip():
        selected_model = models[0]
    selected_model = selected_model.strip()
    if selected_model not in models:
        models = normalize_models([selected_model, *models])

    threshold_value: object = payload.get(
        "context_window",
        payload.get("long_context_threshold", DEFAULT_LONG_CONTEXT_THRESHOLD),
    )
    context_window = parse_context_window(threshold_value)

    settings = LocalLLMSettings(
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
    validate_settings(settings)
    return settings


def ensure_bashrc_activation(bashrc_path: Path) -> None:
    """Ensure interactive SSH shells activate Claude Code Router."""
    block_start = "# Excalibur CCR activation"
    block_end = "# End Excalibur CCR activation"
    # `ccr activate` lazily creates its config file on first run and prints
    # human-readable status lines (e.g. "Created minimal default configuration
    # file...") to stdout alongside the export/unset statements we actually
    # want to eval. Filter to just the shell statements so those stray lines
    # don't get executed as commands.
    activate_cmd = "ccr activate 2>/dev/null | grep -E '^(export|unset) '"
    block = f'{block_start}\neval "$({activate_cmd})" || true\n{block_end}\n'

    existing = bashrc_path.read_text(encoding="utf-8") if bashrc_path.exists() else ""
    lines = existing.splitlines(keepends=True)
    filtered: list[str] = []
    in_block = False
    for line in lines:
        if line.strip() == block_start:
            in_block = True
            continue
        if line.strip() == block_end:
            in_block = False
            continue
        if not in_block:
            filtered.append(line)

    if filtered and not filtered[-1].endswith("\n"):
        filtered[-1] += "\n"
    bashrc_path.write_text("".join(filtered) + block, encoding="utf-8")


def ccr_running(host: str = "127.0.0.1", port: int = 3456) -> bool:
    """Return whether CCR is accepting TCP connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def restart_ccr(log_path: Path) -> JsonObject:
    """Restart Claude Code Router and report whether it became reachable."""
    stop_result = subprocess.run(
        ["ccr", "stop"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_file:
        log_file.write(b"\n--- Excalibur web config: restarting CCR ---\n")
        if stop_result.stdout:
            log_file.write(stop_result.stdout.encode("utf-8", errors="replace"))
        if stop_result.stderr:
            log_file.write(stop_result.stderr.encode("utf-8", errors="replace"))
        subprocess.Popen(
            ["ccr", "start"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    for _ in range(30):
        if ccr_running():
            return {"ok": True, "message": "Saved. Claude Code Router is running."}
        time.sleep(0.25)

    return {
        "ok": False,
        "message": "Saved, but Claude Code Router did not become reachable on port 3456.",
    }


def tail_file(path: Path, max_bytes: int = 24000) -> str:
    """Read the tail of a log file."""
    if not path.exists():
        return ""
    with path.open("rb") as log_file:
        log_file.seek(0, os.SEEK_END)
        size = log_file.tell()
        log_file.seek(max(0, size - max_bytes))
        return log_file.read().decode("utf-8", errors="replace")


def combine_log_sections(
    activity_log: str,
    ccr_log: str,
    activity_log_path: Path,
    ccr_log_path: Path,
) -> str:
    """Combine activity and router logs into a single readable feed."""
    sections = [
        (
            "Excalibur activity",
            activity_log_path,
            activity_log.strip() or "No activity yet.",
        ),
        (
            "Claude Code Router",
            ccr_log_path,
            ccr_log.strip() or "No router log yet.",
        ),
    ]
    return "\n\n".join(f"=== {title} ({path}) ===\n{content}" for title, path, content in sections)


def run_server(
    host: str,
    port: int,
    config_path: Path,
    template_path: Path | None,
    ccr_log_path: Path,
    activity_log_path: Path,
    runtime_config_path: Path,
) -> None:
    """Run the web config server forever."""
    server = ConfigHTTPServer(
        (host, port),
        ConfigRequestHandler,
        config_path=config_path,
        template_path=template_path,
        ccr_log_path=ccr_log_path,
        activity_log_path=activity_log_path,
        runtime_config_path=runtime_config_path,
    )
    print(f"Excalibur config UI listening on http://{host}:{port}", flush=True)
    server.serve_forever()


def main() -> None:
    """Start the web config server from environment variables."""
    host = os.environ.get("EXCALIBUR_WEB_HOST", DEFAULT_WEB_HOST)
    port = int(os.environ.get("EXCALIBUR_WEB_PORT", str(DEFAULT_WEB_PORT)))
    config_path = Path(os.environ.get("EXCALIBUR_CCR_CONFIG", str(DEFAULT_CONFIG_PATH)))
    template_env = os.environ.get("EXCALIBUR_CCR_TEMPLATE", str(DEFAULT_TEMPLATE_PATH))
    template_path = Path(template_env) if template_env else None
    ccr_log_path = Path(os.environ.get("EXCALIBUR_CCR_LOG", str(DEFAULT_CCR_LOG_PATH)))
    activity_log_env = os.environ.get("EXCALIBUR_ACTIVITY_LOG")
    activity_log_path = Path(activity_log_env) if activity_log_env else DEFAULT_ACTIVITY_LOG_PATH
    runtime_config_path = Path(
        os.environ.get("EXCALIBUR_RUNTIME_CONFIG", str(DEFAULT_RUNTIME_CONFIG_PATH))
    )

    run_server(
        host,
        port,
        config_path,
        template_path,
        ccr_log_path,
        activity_log_path,
        runtime_config_path,
    )


if __name__ == "__main__":
    main()
