const UI = {
  runButton: document.getElementById("run"),
  runStatus: document.getElementById("run-status"),
  digitsInput: document.getElementById("digits"),
  pollInput: document.getElementById("poll-interval"),
  logOutput: document.getElementById("log-output"),
  streaming: {
    clients: document.querySelector('.clients[data-panel="streaming"]'),
    metrics: document.querySelector('.metrics[data-panel="streaming"]'),
  },
  polling: {
    clients: document.querySelector('.clients[data-panel="polling"]'),
    metrics: document.querySelector('.metrics[data-panel="polling"]'),
  },
};

const API_BASE = "/api";
const WS_BASE = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;
const CLIENT_COUNT = 5;

const formatMs = (ms) => `${Math.round(ms)} ms`;
const formatSec = (ms) => `${(ms / 1000).toFixed(2)} s`;
const formatBytes = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

function log(level, message, data) {
  const ts = new Date().toISOString().split("T")[1].split(".")[0];
  let line = `[${ts}] ${level.toUpperCase()}: ${message}`;
  if (data !== undefined) {
    line += ` ${JSON.stringify(data)}`;
  }
  if (level === "error") {
    console.error(line);
  } else {
    console.log(line);
  }
  if (UI.logOutput) {
    UI.logOutput.textContent += `${line}\n`;
    UI.logOutput.scrollTop = UI.logOutput.scrollHeight;
  }
}

log("info", "Demo client loaded", { clientCount: CLIENT_COUNT });

if (!UI.runButton || !UI.streaming.clients || !UI.polling.clients) {
  log("error", "Missing UI elements; check HTML/JS version mismatch.");
}

window.addEventListener("error", (event) => {
  log("error", "Unhandled error", { message: event.message });
});

window.addEventListener("unhandledrejection", (event) => {
  log("error", "Unhandled promise rejection", { reason: String(event.reason) });
});

class ApiClient {
  async startPi(digits) {
    const res = await fetch(`${API_BASE}/calculate_pi`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ n: digits }),
    });
    if (!res.ok) {
      throw new Error(`Failed to start task (${res.status})`);
    }
    const data = await res.json();
    return data.id;
  }

  async startNaivePi(digits, taskId) {
    const res = await fetch(`${API_BASE}/naive/calculate_pi`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ digits, task_id: taskId }),
    });
    if (!res.ok) {
      throw new Error(`Failed to start naive task (${res.status})`);
    }
    const data = await res.json();
    return data.task_id;
  }

  async getNaiveProgress(taskId) {
    return this._getJson(
      `${API_BASE}/naive/check_progress?task_id=${encodeURIComponent(taskId)}`
    );
  }

  async getNaiveResult(taskId) {
    return this._getJson(`${API_BASE}/naive/task_result?task_id=${encodeURIComponent(taskId)}`);
  }

  async _getJson(url) {
    const start = performance.now();
    try {
      const res = await fetch(url);
      const text = await res.text();
      const bytes = text.length;
      let data = null;
      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = null;
        }
      }
      const elapsedMs = performance.now() - start;
      return { ok: res.ok, status: res.status, data, bytes, elapsedMs };
    } catch (error) {
      const elapsedMs = performance.now() - start;
      log("error", "HTTP request failed", { url, error: String(error) });
      return { ok: false, status: 0, data: null, bytes: 0, elapsedMs, error: String(error) };
    }
  }
}

class WsClient {
  constructor(base) {
    this.base = base;
  }

  connect(taskId, clientId, onMessage) {
    const ws = new WebSocket(`${this.base}/ws/tasks/${taskId}`);
    const keepalive = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 1000);
    ws.addEventListener("open", () => log("info", "WS connected", { clientId }));
    ws.addEventListener("message", (event) => onMessage(event.data));
    ws.addEventListener("error", () => log("error", "WS error", { clientId }));
    ws.addEventListener("close", () => {
      clearInterval(keepalive);
      log("info", "WS closed", { clientId });
    });
    return {
      close: () => ws.close(),
    };
  }
}

class StreamingEngine {
  constructor(taskId, wsClient, clientState) {
    this.taskId = taskId;
    this.wsClient = wsClient;
    this.state = clientState;
    this.socket = null;
    this.startTime = performance.now();
  }

  start() {
    this.socket = this.wsClient.connect(
      this.taskId,
      this.state.id,
      (data) => this._handleMessage(data)
    );
  }

  stop() {
    this.socket?.close();
  }

  _handleMessage(raw) {
    this.state.metrics.messages += 1;
    this.state.metrics.bytes += raw.length;
    if (!this.state.metrics.firstUpdateMs) {
      this.state.metrics.firstUpdateMs = performance.now() - this.startTime;
    }
    let message;
    try {
      message = JSON.parse(raw);
    } catch {
      log("error", "WS message parse failed", { clientId: this.state.id });
      return;
    }
    if (message.type === "task.status") {
      const status = message.payload?.status;
      const progress = status?.progress?.percentage ?? 0;
      this.state.progress = progress;
      this.state.status = status?.state ?? "RUNNING";
      this.state.statusMetrics = status?.metrics ?? null;
      const meta = status?.metadata;
      if (meta?.server_sent_ts) {
        const latencyMs = Date.now() - meta.server_sent_ts * 1000;
        this.state.metrics.latencyTotalMs += latencyMs;
        this.state.metrics.latencyCount += 1;
      }
      if (meta?.server_cpu_ms_ws !== undefined) {
        this.state.metrics.serverCpuMs = meta.server_cpu_ms_ws;
      }
    }
    if (message.type === "task.result_chunk") {
      const payload = message.payload;
      const data = Array.isArray(payload?.data) ? payload.data : [];
      if (data.length) {
        this.state.result += data.join("");
      }
      if (payload?.is_last) {
        this.state.completed = true;
        this.state.metrics.totalMs = performance.now() - this.startTime;
      }
    }
    if (message.type === "task.result") {
      this.state.completed = true;
      this.state.metrics.totalMs = performance.now() - this.startTime;
    }
  }
}

class PollingEngine {
  constructor(taskId, apiClient, clientState, intervalMs) {
    this.taskId = taskId;
    this.apiClient = apiClient;
    this.state = clientState;
    this.intervalMs = intervalMs;
    this.timer = null;
    this.inFlight = false;
    this.startTime = performance.now();
  }

  start() {
    this.timer = setInterval(() => this._tick(), this.intervalMs);
    this._tick();
  }

  stop() {
    clearInterval(this.timer);
  }

  async _tick() {
    if (this.inFlight || this.state.completed) return;
    this.inFlight = true;
    try {
      const progressRes = await this.apiClient.getNaiveProgress(this.taskId);
      this._record(progressRes.bytes);
      if (progressRes.elapsedMs !== undefined) {
        this.state.metrics.latencyTotalMs += progressRes.elapsedMs;
        this.state.metrics.latencyCount += 1;
      }
      if (progressRes.ok && progressRes.data) {
        const progress = progressRes.data.progress?.percentage ?? 0;
        this.state.progress = progress;
        this.state.status = progressRes.data.state ?? "RUNNING";
        this.state.statusMetrics = progressRes.data.metrics ?? null;
        const meta = progressRes.data.metadata;
        if (meta?.server_cpu_ms_naive !== undefined) {
          this.state.metrics.serverCpuMs = meta.server_cpu_ms_naive;
        }
        this._maybeFirstUpdate(progressRes.data);
      } else if (progressRes.error) {
        log("error", "Polling progress failed", { clientId: this.state.id });
      }

      const resultRes = await this.apiClient.getNaiveResult(this.taskId);
      this._record(resultRes.bytes);
      if (resultRes.elapsedMs !== undefined) {
        this.state.metrics.latencyTotalMs += resultRes.elapsedMs;
        this.state.metrics.latencyCount += 1;
      }
      if (resultRes.ok && resultRes.data) {
        const payload = resultRes.data.partial_result ?? "";
        this.state.result = typeof payload === "string" ? payload : JSON.stringify(payload);
        this._maybeFirstUpdate(progressRes.data);
        const meta = resultRes.data.metadata;
        if (meta?.server_cpu_ms_naive !== undefined) {
          this.state.metrics.serverCpuMs = meta.server_cpu_ms_naive;
        }
        if (resultRes.data.done === true) {
          this.state.completed = true;
          this.state.metrics.totalMs = performance.now() - this.startTime;
          this.stop();
        }
      } else if (resultRes.error) {
        log("error", "Polling result failed", { clientId: this.state.id });
      }
    } finally {
      this.inFlight = false;
    }
  }

  _record(bytes) {
    this.state.metrics.requests += 1;
    this.state.metrics.bytes += bytes;
  }

  _maybeFirstUpdate(progressPayload) {
    if (this.state.metrics.firstUpdateMs) {
      return;
    }
    const current = progressPayload?.progress?.current ?? 0;
    const state = progressPayload?.state ?? "";
    if (state === "RUNNING" && current > 0) {
      this.state.metrics.firstUpdateMs = performance.now() - this.startTime;
    }
  }
}

class RunController {
  constructor(apiClient, wsClient) {
    this.apiClient = apiClient;
    this.wsClient = wsClient;
    this.streamingEngines = [];
    this.pollingEngines = [];
  }

  async run(digits, pollInterval, state) {
    this._resetState(state);
    state.runStatus = "starting";
    render(state);
    if (UI.logOutput) {
      UI.logOutput.textContent = "";
    }
    log("info", "Demo started", { digits, pollInterval });
    try {
      const taskId = await this.apiClient.startPi(digits);
      await this.apiClient.startNaivePi(digits, taskId);
      state.taskId = taskId;
      state.runStatus = "running";
      this.streamingEngines = state.streaming.clients.map(
        (client) => new StreamingEngine(taskId, this.wsClient, client)
      );
      this.pollingEngines = state.polling.clients.map(
        (client) => new PollingEngine(taskId, this.apiClient, client, pollInterval)
      );
      this.streamingEngines.forEach((engine) => engine.start());
      this.pollingEngines.forEach((engine) => engine.start());
      log("info", "Task started", { taskId });
    } catch (err) {
      state.runStatus = "error";
      state.error = err.message || String(err);
      log("error", "Run failed", { error: state.error });
    }
  }

  stop() {
    this.streamingEngines.forEach((engine) => engine.stop());
    this.pollingEngines.forEach((engine) => engine.stop());
  }

  _resetState(state) {
    state.taskId = null;
    state.runStatus = "idle";
    state.error = null;
    state.streaming.reset();
    state.polling.reset();
  }
}

const createClientState = (id) => ({
  id,
  status: "IDLE",
  progress: 0,
  result: "",
  statusMetrics: null,
  completed: false,
  renderedLength: 0,
  metrics: {
    firstUpdateMs: null,
    totalMs: null,
    messages: 0,
    requests: 0,
    bytes: 0,
    latencyTotalMs: 0,
    latencyCount: 0,
    serverCpuMs: 0,
  },
  reset() {
    this.status = "IDLE";
    this.progress = 0;
    this.result = "";
    this.statusMetrics = null;
    this.completed = false;
    this.renderedLength = 0;
    this.metrics.firstUpdateMs = null;
    this.metrics.totalMs = null;
    this.metrics.messages = 0;
    this.metrics.requests = 0;
    this.metrics.bytes = 0;
    this.metrics.latencyTotalMs = 0;
    this.metrics.latencyCount = 0;
    this.metrics.serverCpuMs = 0;
  },
});

const createModeState = (count) => ({
  clients: Array.from({ length: count }, (_, idx) => createClientState(idx + 1)),
  reset() {
    this.clients.forEach((client) => client.reset());
  },
});

const state = {
  taskId: null,
  runStatus: "idle",
  error: null,
  streaming: createModeState(CLIENT_COUNT),
  polling: createModeState(CLIENT_COUNT),
};

const apiClient = new ApiClient();
const wsClient = new WsClient(WS_BASE);
const controller = new RunController(apiClient, wsClient);

function aggregateMetrics(clients) {
  const firstUpdates = clients
    .map((client) => client.metrics.firstUpdateMs)
    .filter((value) => value !== null);
  const totals = clients
    .map((client) => client.metrics.totalMs)
    .filter((value) => value !== null);
  return {
    firstUpdateMs: firstUpdates.length ? Math.min(...firstUpdates) : null,
    totalMs: totals.length ? Math.max(...totals) : null,
    messages: clients.reduce((sum, client) => sum + client.metrics.messages, 0),
    requests: clients.reduce((sum, client) => sum + client.metrics.requests, 0),
    bytes: clients.reduce((sum, client) => sum + client.metrics.bytes, 0),
    latencyTotalMs: clients.reduce((sum, client) => sum + client.metrics.latencyTotalMs, 0),
    latencyCount: clients.reduce((sum, client) => sum + client.metrics.latencyCount, 0),
    serverCpuMs: clients.reduce((max, client) => Math.max(max, client.metrics.serverCpuMs), 0),
  };
}

function renderPanel(ui, mode, isStreaming) {
  if (!ui.clients) {
    log("error", "Missing client container", { panel: isStreaming ? "streaming" : "polling" });
    return;
  }
  ensureClientNodes(ui.clients, mode.clients.length);
  updateClientNodes(ui.clients, mode.clients);

  const metricsAggregate = aggregateMetrics(mode.clients);
  const avgLatency =
    metricsAggregate.latencyCount > 0
      ? formatMs(metricsAggregate.latencyTotalMs / metricsAggregate.latencyCount)
      : "—";
  const cumulativeLatency = formatMs(metricsAggregate.latencyTotalMs);
  const metrics = [
    ["Server CPU ms", `${Math.round(metricsAggregate.serverCpuMs)} ms`],
    ["Cumulative delivery latency", cumulativeLatency],
    ["Avg latency", avgLatency],
    ["Total time", metricsAggregate.totalMs ? formatSec(metricsAggregate.totalMs) : "—"],
    [
      isStreaming ? "WS messages" : "HTTP requests",
      isStreaming ? metricsAggregate.messages : metricsAggregate.requests,
    ],
    ["Bytes received", formatBytes(metricsAggregate.bytes)],
  ];

  ui.metrics.innerHTML = metrics
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");
}

function ensureClientNodes(container, count) {
  const existing = container.querySelectorAll(".client").length;
  if (existing === count) {
    return;
  }
  container.innerHTML = "";
  for (let i = 0; i < count; i += 1) {
    const client = document.createElement("div");
    client.className = "client";
    client.innerHTML = `
      <div class="client-label">Client ${i + 1}</div>
      <div class="client-metrics">metrics: —</div>
      <div class="client-progress">
        <div class="progress-bar" style="width: 0%"></div>
      </div>
      <div class="client-result">—</div>
    `;
    container.appendChild(client);
  }
}

function updateClientNodes(container, clients) {
  const nodes = container.querySelectorAll(".client");
  clients.forEach((client, idx) => {
    const node = nodes[idx];
    if (!node) return;
    const metricsNode = node.querySelector(".client-metrics");
    const progressNode = node.querySelector(".progress-bar");
    const resultNode = node.querySelector(".client-result");

    if (metricsNode) {
      metricsNode.textContent = formatClientMetrics(client);
    }
    if (progressNode) {
      progressNode.style.width = `${Math.min(client.progress * 100, 100)}%`;
    }
    if (resultNode) {
      const shouldStick =
        resultNode.scrollTop + resultNode.clientHeight >= resultNode.scrollHeight - 8;
      const next = client.result || "—";
      if (next === "—") {
        resultNode.textContent = "—";
        client.renderedLength = 0;
      } else if (resultNode.textContent === "—") {
        resultNode.textContent = next;
        client.renderedLength = next.length;
      } else if (next.length < client.renderedLength) {
        resultNode.textContent = next;
        client.renderedLength = next.length;
      } else if (next.length > client.renderedLength && next !== "—") {
        resultNode.textContent += next.slice(client.renderedLength);
        client.renderedLength = next.length;
      } else if (client.renderedLength === 0 && next !== "—") {
        resultNode.textContent = next;
        client.renderedLength = next.length;
      }
      if (shouldStick) {
        resultNode.scrollTop = resultNode.scrollHeight;
      }
    }
  });
}

function formatClientMetrics(client) {
  if (!client.statusMetrics) {
    return "metrics: —";
  }
  const eta =
    client.statusMetrics.eta_seconds !== undefined
      ? `${client.statusMetrics.eta_seconds.toFixed(1)}s`
      : "—";
  const digits = client.statusMetrics.digits_sent ?? 0;
  const total = client.statusMetrics.digits_total ?? 0;
  return `metrics: eta ${eta} | digits ${digits}/${total}`;
}

function render(state) {
  UI.runButton.disabled = state.runStatus === "running" || state.runStatus === "starting";
  UI.runStatus.textContent = state.error
    ? `Error: ${state.error}`
    : state.runStatus.toUpperCase();
  renderPanel(UI.streaming, state.streaming, true);
  renderPanel(UI.polling, state.polling, false);
}

UI.runButton.addEventListener("click", async (event) => {
  event.preventDefault();
  controller.stop();
  const digits = Number(UI.digitsInput.value) || 500;
  const pollInterval = Number(UI.pollInput.value) || 150;
  await controller.run(digits, pollInterval, state);
});

setInterval(() => {
  render(state);
  const streamingDone = state.streaming.clients.every((client) => client.completed);
  const pollingDone = state.polling.clients.every((client) => client.completed);
  if (streamingDone && pollingDone && state.runStatus === "running") {
    state.runStatus = "done";
    log("info", "Demo completed");
  }
}, 100);

render(state);
