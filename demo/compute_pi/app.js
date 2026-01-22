import { API_BASE, WS_BASE, getJson, postJson, WsClient, ApiClient } from "../shared/transport.js";
import {
  formatMs,
  formatSec,
  formatBytes,
  StreamingEngine,
  PollingEngine,
  applyNaiveStatus,
  TERMINAL_STATES,
} from "../shared/engine.js";

const UI = {
  runButton: document.getElementById("run"),
  runStatus: document.getElementById("run-status"),
  digitsInput: document.getElementById("digits"),
  pollInput: document.getElementById("poll-interval"),
  streaming: {
    clients: document.querySelector('.clients[data-panel="streaming"]'),
    metrics: document.querySelector('.metrics[data-panel="streaming"]'),
  },
  polling: {
    clients: document.querySelector('.clients[data-panel="polling"]'),
    metrics: document.querySelector('.metrics[data-panel="polling"]'),
  },
};

const CLIENT_COUNT = 5;

if (!UI.runButton || !UI.streaming.clients || !UI.polling.clients) {
  throw new Error("Missing UI elements; check HTML/JS version mismatch.");
}

function maybeFirstUpdate(state, progressPayload, startTime) {
  if (state.metrics.firstUpdateMs) {
    return;
  }
  const current = progressPayload?.progress?.current ?? 0;
  const runState = progressPayload?.state ?? "";
  if (runState === "RUNNING" && current > 0 && startTime !== undefined) {
    state.metrics.firstUpdateMs = performance.now() - startTime;
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
    try {
      const taskRes = await this.apiClient.startTask(digits);
      if (!taskRes.ok) {
        throw new Error(`Failed to start task (${taskRes.status})`);
      }
      const taskId = taskRes.data?.id;
      const naiveRes = await this.apiClient.startNaiveTask(digits, taskId);
      if (!naiveRes.ok) {
        throw new Error(`Failed to start naive task (${naiveRes.status})`);
      }
      state.taskId = taskId;
      state.runStatus = "running";
      this.streamingEngines = state.streaming.clients.map(
        (client) =>
          new StreamingEngine({
            taskId,
            wsClient: this.wsClient,
            state: client,
            onResultChunk: (payload, clientState) => {
              const payloadData = payload?.data;
              if (Array.isArray(payloadData)) {
                if (payloadData.length) {
                  clientState.result += payloadData.join("");
                }
              } else if (typeof payloadData === "string" && payloadData) {
                clientState.result += payloadData;
              }
            },
          })
      );
      this.pollingEngines = state.polling.clients.map(
        (client) => {
          const engine = new PollingEngine({
            taskId,
            api: this.apiClient,
            state: client,
            intervalMs: pollInterval,
            onStatus: (data, clientState) => {
              applyNaiveStatus(clientState, data);
              maybeFirstUpdate(clientState, data, engine.startTime);
            },
            onResult: (data, clientState) => {
              const payload = data.partial_result ?? "";
              clientState.result =
                typeof payload === "string" ? payload : JSON.stringify(payload);
              const meta = data.metadata;
              if (meta?.server_cpu_ms_naive !== undefined) {
                clientState.metrics.serverCpuMs = meta.server_cpu_ms_naive;
              }
            },
            shouldStop: ({ phase, statusRes, resultRes, state: clientState }) => {
              if (phase === "status") {
                if (statusRes?.status === 404) return true;
                if (TERMINAL_STATES.has(clientState.status)) return true;
              }
              if (phase === "result") {
                if (resultRes?.status === 404) return true;
                if (resultRes?.ok && resultRes.data?.done === true) return true;
              }
              return false;
            },
          });
          return engine;
        }
      );
      this.streamingEngines.forEach((engine) => engine.start());
      this.pollingEngines.forEach((engine) => engine.start());
    } catch (err) {
      state.runStatus = "error";
      state.error = err.message || String(err);
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

const apiClient = new ApiClient({
  startTask: (digits) => postJson(`${API_BASE}/calculate_pi`, { n: digits }),
  startNaiveTask: (digits, taskId) =>
    postJson(`${API_BASE}/naive/calculate_pi`, {
      digits,
      task_id: taskId,
      demo: true,
    }),
  getStatus: (taskId) =>
    getJson(`${API_BASE}/naive/check_progress?task_id=${encodeURIComponent(taskId)}`),
  getResult: (taskId) =>
    getJson(`${API_BASE}/naive/task_result?task_id=${encodeURIComponent(taskId)}`),
});
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
  }
}, 100);

render(state);
