const UI = {
  runButton: document.getElementById("run"),
  runStatus: document.getElementById("run-status"),
  controlsForm: document.getElementById("controls"),
  docPathInput: document.getElementById("doc-path"),
  docUrlInput: document.getElementById("doc-url"),
  keywordsInput: document.getElementById("keywords"),
  pollInput: document.getElementById("poll-interval"),
  logOutput: document.getElementById("log-output"),
  streaming: {
    metrics: document.getElementById("streaming-metrics"),
    progress: document.getElementById("streaming-progress"),
    result: document.getElementById("streaming-result"),
    summary: document.getElementById("streaming-summary"),
  },
  polling: {
    metrics: document.getElementById("polling-metrics"),
    progress: document.getElementById("polling-progress"),
    result: document.getElementById("polling-result"),
    summary: document.getElementById("polling-summary"),
  },
};

const API_BASE = "/api";
const WS_BASE = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;

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

window.addEventListener("error", (event) => {
  log("error", "Unhandled error", { message: event.message });
});

window.addEventListener("unhandledrejection", (event) => {
  log("error", "Unhandled promise rejection", { reason: String(event.reason) });
});

class ApiClient {
  async startDocumentAnalysis(documentPath, documentUrl, keywords) {
    const res = await fetch(`${API_BASE}/tasks/document-analysis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document_path: documentPath,
        document_url: documentUrl,
        keywords,
      }),
    });
    if (!res.ok) {
      throw new Error(`Failed to start document analysis (${res.status})`);
    }
    const data = await res.json();
    return data.id;
  }

  async startNaiveDocumentAnalysis(taskId, documentPath, documentUrl, keywords) {
    const res = await fetch(`${API_BASE}/naive/document-analysis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: taskId,
        document_path: documentPath,
        document_url: documentUrl,
        keywords,
      }),
    });
    if (!res.ok) {
      throw new Error(`Failed to start naive document analysis (${res.status})`);
    }
    const data = await res.json();
    return data.task_id;
  }

  async getNaiveStatus(taskId) {
    return this._getJson(
      `${API_BASE}/naive/document-analysis/status?task_id=${encodeURIComponent(taskId)}`
    );
  }

  async getNaiveSnippets(taskId, afterId) {
    const url = new URL(`${API_BASE}/naive/document-analysis/snippets`, window.location.href);
    url.searchParams.set("task_id", taskId);
    if (afterId !== null && afterId !== undefined) {
      url.searchParams.set("after", String(afterId));
    }
    return this._getJson(url.toString());
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

  connect(taskId, onMessage) {
    const ws = new WebSocket(`${this.base}/ws/tasks/${taskId}`);
    const keepalive = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 1000);
    ws.addEventListener("open", () => log("info", "WS connected", { taskId }));
    ws.addEventListener("message", (event) => onMessage(event.data));
    ws.addEventListener("error", () => log("error", "WS error", { taskId }));
    ws.addEventListener("close", () => {
      clearInterval(keepalive);
      log("info", "WS closed", { taskId });
    });
    return {
      close: () => ws.close(),
    };
  }
}

function createPanelState() {
  return {
    progress: 0,
    status: "IDLE",
    result: "",
    statusMetrics: null,
    completed: false,
    lastSnippetId: null,
    metrics: {
      firstUpdateMs: 0,
      totalMs: 0,
      messages: 0,
      bytes: 0,
      requests: 0,
      latencyTotalMs: 0,
      latencyCount: 0,
      serverCpuMs: 0,
    },
  };
}

class StreamingEngine {
  constructor(taskId, wsClient, panelState, onUpdate) {
    this.taskId = taskId;
    this.wsClient = wsClient;
    this.state = panelState;
    this.onUpdate = onUpdate;
    this.socket = null;
    this.startTime = performance.now();
  }

  start() {
    this.socket = this.wsClient.connect(this.taskId, (data) => this._handleMessage(data));
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
      log("error", "WS message parse failed", { taskId: this.taskId });
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
        const latencyMs = performance.now() - meta.server_sent_ts * 1000;
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
        const lines = [];
        for (const item of data) {
          const line = this._formatSnippet(item);
          if (line) lines.push(line);
        }
        if (lines.length) {
          appendResultText(UI.streaming.result, lines.join("\n"));
        }
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
    this.onUpdate();
  }

  _formatSnippet(item) {
    if (!item) return "";
    const line = item.location?.line ?? "?";
    const keyword = item.keyword ?? "keyword";
    const snippet = item.snippet ?? "";
    const entry = `[line ${line}] ${keyword}: ${snippet}`;
    if (this.state.result) {
      this.state.result += `\n${entry}`;
    } else {
      this.state.result = entry;
    }
    return entry;
  }
}

class PollingEngine {
  constructor(taskId, apiClient, panelState, intervalMs, onUpdate) {
    this.taskId = taskId;
    this.apiClient = apiClient;
    this.state = panelState;
    this.intervalMs = intervalMs;
    this.onUpdate = onUpdate;
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
      const statusRes = await this.apiClient.getNaiveStatus(this.taskId);
      this._record(statusRes.bytes);
      if (statusRes.elapsedMs !== undefined) {
        this.state.metrics.latencyTotalMs += statusRes.elapsedMs;
        this.state.metrics.latencyCount += 1;
      }
      if (statusRes.ok && statusRes.data) {
        const progress = statusRes.data.progress?.percentage ?? 0;
        this.state.progress = progress;
        this.state.status = statusRes.data.state ?? "RUNNING";
        this.state.statusMetrics = statusRes.data.metrics ?? null;
        const meta = statusRes.data.metadata;
        if (meta?.server_cpu_ms_naive !== undefined) {
          this.state.metrics.serverCpuMs = meta.server_cpu_ms_naive;
        }
        this._maybeFirstUpdate(progress, statusRes.data.metrics);
      }

      const snippetRes = await this.apiClient.getNaiveSnippets(
        this.taskId,
        this.state.lastSnippetId
      );
      this._record(snippetRes.bytes);
      if (snippetRes.elapsedMs !== undefined) {
        this.state.metrics.latencyTotalMs += snippetRes.elapsedMs;
        this.state.metrics.latencyCount += 1;
      }
      if (snippetRes.ok && snippetRes.data) {
        const snippets = snippetRes.data.snippets ?? [];
        if (snippets.length) {
          const lines = [];
          for (const item of snippets) {
            const line = this._formatSnippet(item);
            if (line) lines.push(line);
          }
          if (lines.length) {
            appendResultText(UI.polling.result, lines.join("\n"));
          }
          this.state.lastSnippetId = snippetRes.data.last_id ?? this.state.lastSnippetId;
          this._maybeFirstUpdate(1, {});
        }
        const meta = snippetRes.data.metadata;
        if (meta?.server_cpu_ms_naive !== undefined) {
          this.state.metrics.serverCpuMs = meta.server_cpu_ms_naive;
        }
      }

      if (this.state.status === "COMPLETED") {
        this.state.completed = true;
        this.state.metrics.totalMs = performance.now() - this.startTime;
        this.stop();
      }
      this.onUpdate();
    } finally {
      this.inFlight = false;
    }
  }

  _record(bytes) {
    this.state.metrics.requests += 1;
    this.state.metrics.bytes += bytes;
  }

  _formatSnippet(item) {
    if (!item) return "";
    const line = item.line ?? "?";
    const keyword = item.keyword ?? "keyword";
    const snippet = item.snippet ?? "";
    const entry = `[line ${line}] ${keyword}: ${snippet}`;
    if (this.state.result) {
      this.state.result += `\n${entry}`;
    } else {
      this.state.result = entry;
    }
    return entry;
  }

  _maybeFirstUpdate(progress, metrics) {
    if (!this.state.metrics.firstUpdateMs && (progress > 0 || metrics)) {
      this.state.metrics.firstUpdateMs = performance.now() - this.startTime;
    }
  }
}

function renderMetricsText(metrics, perf) {
  if (!metrics) return "metrics: —";
  const eta = metrics.eta_seconds !== undefined ? `${metrics.eta_seconds.toFixed(1)}s` : "—";
  const snippets = metrics.snippets_emitted ?? 0;
  const words = metrics.words_processed ?? 0;
  const avgLatency =
    perf.latencyCount > 0 ? formatMs(perf.latencyTotalMs / perf.latencyCount) : "—";
  const totalLatency = formatMs(perf.latencyTotalMs);
  const serverCpu = `${Math.round(perf.serverCpuMs)} ms`;
  return `metrics: eta ${eta} | snippets ${snippets} | words ${words} | avg latency ${avgLatency} | total latency ${totalLatency} | server cpu ${serverCpu}`;
}

function renderSummary(container, data) {
  const avgLatency =
    data.latencyCount > 0 ? formatMs(data.latencyTotalMs / data.latencyCount) : "—";
  const totalLatency = formatMs(data.latencyTotalMs);
  container.innerHTML = `
    <div>
      <dt>Time to first update</dt>
      <dd>${data.firstUpdateMs ? formatMs(data.firstUpdateMs) : "—"}</dd>
    </div>
    <div>
      <dt>Total duration</dt>
      <dd>${data.totalMs ? formatSec(data.totalMs) : "—"}</dd>
    </div>
    <div>
      <dt>${data.mode === "streaming" ? "WS messages" : "HTTP requests"}</dt>
      <dd>${data.mode === "streaming" ? data.messages : data.requests}</dd>
    </div>
    <div>
      <dt>Bytes received</dt>
      <dd>${formatBytes(data.bytes)}</dd>
    </div>
    <div>
      <dt>Avg latency</dt>
      <dd>${avgLatency}</dd>
    </div>
    <div>
      <dt>Total latency</dt>
      <dd>${totalLatency}</dd>
    </div>
    <div>
      <dt>Server CPU ms</dt>
      <dd>${Math.round(data.serverCpuMs)} ms</dd>
    </div>
  `;
}

function resetPanel(panel, state) {
  state.progress = 0;
  state.status = "IDLE";
  state.result = "";
  state.statusMetrics = null;
  state.completed = false;
  state.lastSnippetId = null;
  state.metrics = {
    firstUpdateMs: 0,
    totalMs: 0,
    messages: 0,
    bytes: 0,
    requests: 0,
    latencyTotalMs: 0,
    latencyCount: 0,
    serverCpuMs: 0,
  };
  panel.progress.style.width = "0%";
  panel.result.textContent = "—";
  panel.result.dataset.placeholder = "true";
  panel.result.dataset.hasContent = "false";
  panel.metrics.textContent = "metrics: —";
  panel.summary.innerHTML = "";
}

const api = new ApiClient();
const wsClient = new WsClient(WS_BASE);

let streamingEngine = null;
let pollingEngine = null;
const streamingState = createPanelState();
const pollingState = createPanelState();

function updateUI() {
  UI.streaming.progress.style.width = `${Math.min(streamingState.progress * 100, 100)}%`;
  UI.streaming.metrics.textContent = renderMetricsText(
    streamingState.statusMetrics,
    streamingState.metrics
  );
  renderSummary(UI.streaming.summary, {
    ...streamingState.metrics,
    mode: "streaming",
  });

  UI.polling.progress.style.width = `${Math.min(pollingState.progress * 100, 100)}%`;
  UI.polling.metrics.textContent = renderMetricsText(
    pollingState.statusMetrics,
    pollingState.metrics
  );
  renderSummary(UI.polling.summary, {
    ...pollingState.metrics,
    mode: "polling",
  });
}

function appendResultText(container, text) {
  if (!text) return;
  if (container.dataset.placeholder === "true") {
    container.textContent = "";
    container.dataset.placeholder = "false";
  }
  const hasContent = container.dataset.hasContent === "true";
  const prefix = hasContent ? "\n" : "";
  container.appendChild(document.createTextNode(prefix + text));
  container.dataset.hasContent = "true";
  requestAnimationFrame(() => {
    container.scrollTop = container.scrollHeight;
  });
}

function parseKeywords(input) {
  return input
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function resolveDocumentPath(documentPath, documentUrl) {
  if (documentPath) return documentPath;
  if (!documentUrl) return "";
  try {
    const url = new URL(documentUrl);
    const name = url.pathname.split("/").pop() || "document.txt";
    return `/data/books/${name}`;
  } catch {
    return "";
  }
}

async function runDemo(event) {
  event.preventDefault();
  if (!UI.runButton) return;
  UI.runButton.disabled = true;
  UI.runStatus.textContent = "Starting…";
  UI.logOutput.textContent = "";

  if (streamingEngine) streamingEngine.stop();
  if (pollingEngine) pollingEngine.stop();
  resetPanel(UI.streaming, streamingState);
  resetPanel(UI.polling, pollingState);

  const documentUrl = UI.docUrlInput?.value.trim() || "";
  const documentPath = resolveDocumentPath(
    UI.docPathInput?.value.trim(),
    documentUrl
  );
  const keywords = parseKeywords(UI.keywordsInput?.value || "");
  const pollInterval = Number(UI.pollInput?.value || 200);

  if (!documentPath && !documentUrl) {
    log("error", "Document path or URL is required");
    UI.runStatus.textContent = "Missing document path/URL";
    UI.runButton.disabled = false;
    return;
  }
  if (!keywords.length) {
    log("error", "Keywords are required");
    UI.runStatus.textContent = "Missing keywords";
    UI.runButton.disabled = false;
    return;
  }

  try {
    const taskId = await api.startDocumentAnalysis(documentPath || null, documentUrl || null, keywords);
    log("info", "Streaming task created", { taskId });
    await api.startNaiveDocumentAnalysis(
      taskId,
      documentPath || null,
      documentUrl || null,
      keywords
    );
    log("info", "Naive task created", { taskId });

    streamingEngine = new StreamingEngine(taskId, wsClient, streamingState, updateUI);
    pollingEngine = new PollingEngine(taskId, api, pollingState, pollInterval, updateUI);
    streamingEngine.start();
    pollingEngine.start();
    UI.runStatus.textContent = `Running (${taskId})`;
  } catch (error) {
    log("error", "Run failed", { error: String(error) });
    UI.runStatus.textContent = "Failed to start";
  } finally {
    UI.runButton.disabled = false;
  }
}

UI.controlsForm?.addEventListener("submit", runDemo);
UI.runButton?.addEventListener("click", runDemo);
log("info", "Document analysis demo ready");
