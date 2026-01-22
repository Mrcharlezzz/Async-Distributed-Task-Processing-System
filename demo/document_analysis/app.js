import {
  API_BASE,
  WS_BASE,
  getJson,
  postJson,
  WsClient,
  ApiClient,
} from "../shared/transport.js";
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
  controlsForm: document.getElementById("controls"),
  docPathInput: document.getElementById("doc-path"),
  docUrlInput: document.getElementById("doc-url"),
  keywordsInput: document.getElementById("keywords"),
  pollInput: document.getElementById("poll-interval"),
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

function maybeFirstUpdate(state, startTime, progress, metrics) {
  if (!state.metrics.firstUpdateMs && (progress > 0 || metrics)) {
    state.metrics.firstUpdateMs = performance.now() - startTime;
  }
}

function formatStreamingSnippet(item, state) {
  if (!item) return "";
  const line = item.location?.line ?? "?";
  const keyword = item.keyword ?? "keyword";
  const snippet = item.snippet ?? "";
  const entry = `[line ${line}] ${keyword}: ${snippet}`;
  if (state.result) {
    state.result += `\n${entry}`;
  } else {
    state.result = entry;
  }
  return entry;
}

function formatPollingSnippet(item, state) {
  if (!item) return "";
  const line = item.line ?? "?";
  const keyword = item.keyword ?? "keyword";
  const snippet = item.snippet ?? "";
  const entry = `[line ${line}] ${keyword}: ${snippet}`;
  if (state.result) {
    state.result += `\n${entry}`;
  } else {
    state.result = entry;
  }
  return entry;
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

function renderMetricsText(metrics, perf) {
  if (!metrics) return "metrics: —";
  const snippets = metrics.snippets_emitted ?? 0;
  return `metrics: snippets ${snippets}`;
}

function renderSummary(container, data) {
  const avgLatency =
    data.latencyCount > 0 ? formatMs(data.latencyTotalMs / data.latencyCount) : "—";
  const cumulativeLatency = formatMs(data.latencyTotalMs);
  container.innerHTML = `
    <div>
      <dt>Server CPU ms</dt>
      <dd>${Math.round(data.serverCpuMs)} ms</dd>
    </div>
    <div>
      <dt>Cumulative delivery latency</dt>
      <dd>${cumulativeLatency}</dd>
    </div>
    <div>
      <dt>Avg latency</dt>
      <dd>${avgLatency}</dd>
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

const api = new ApiClient({
  startTask: (documentPath, documentUrl, keywords) =>
    postJson(`${API_BASE}/tasks/document-analysis`, {
      document_path: documentPath,
      document_url: documentUrl,
      keywords,
    }),
  startNaiveTask: (taskId, documentPath, documentUrl, keywords, demo = false) =>
    postJson(`${API_BASE}/naive/document-analysis`, {
      task_id: taskId,
      document_path: documentPath,
      document_url: documentUrl,
      keywords,
      demo,
    }),
  getStatus: (taskId) =>
    getJson(
      `${API_BASE}/naive/document-analysis/status?task_id=${encodeURIComponent(taskId)}`
    ),
  getResult: (taskId, state) => {
    const url = new URL(`${API_BASE}/naive/document-analysis/snippets`, window.location.href);
    url.searchParams.set("task_id", taskId);
    if (state?.lastSnippetId !== null && state?.lastSnippetId !== undefined) {
      url.searchParams.set("after", String(state.lastSnippetId));
    }
    return getJson(url.toString());
  },
});
const wsClient = new WsClient(WS_BASE);

let streamingEngine = null;
let pollingEngine = null;
const streamingState = createPanelState();
const pollingState = createPanelState();
let runInProgress = false;

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

  if (runInProgress && streamingState.completed && pollingState.completed) {
    runInProgress = false;
    UI.runButton.disabled = false;
    UI.runStatus.textContent = "Completed";
  }
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
  runInProgress = true;
  UI.runStatus.textContent = "Starting…";

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
    UI.runStatus.textContent = "Missing document path/URL";
    UI.runButton.disabled = false;
    runInProgress = false;
    return;
  }
  if (!keywords.length) {
    UI.runStatus.textContent = "Missing keywords";
    UI.runButton.disabled = false;
    runInProgress = false;
    return;
  }

  try {
    const taskRes = await api.startTask(documentPath || null, documentUrl || null, keywords);
    if (!taskRes.ok) {
      throw new Error(`Failed to start document analysis (${taskRes.status})`);
    }
    const taskId = taskRes.data?.id;
    const naiveRes = await api.startNaiveTask(
      taskId,
      documentPath || null,
      documentUrl || null,
      keywords,
      true
    );
    if (!naiveRes.ok) {
      throw new Error(`Failed to start naive document analysis (${naiveRes.status})`);
    }
    streamingEngine = new StreamingEngine({
      taskId,
      wsClient,
      state: streamingState,
      onResultChunk: (payload, state) => {
        const data = Array.isArray(payload?.data) ? payload.data : [];
        if (data.length) {
          const lines = [];
          for (const item of data) {
            const line = formatStreamingSnippet(item, state);
            if (line) lines.push(line);
          }
          if (lines.length) {
            appendResultText(UI.streaming.result, lines.join("\n"));
          }
        }
      },
      onUpdate: updateUI,
    });
    pollingEngine = new PollingEngine({
      taskId,
      api,
      state: pollingState,
      intervalMs: pollInterval,
      onStatus: (data, state) => {
        applyNaiveStatus(state, data);
        maybeFirstUpdate(state, pollingEngine.startTime, state.progress, data.metrics);
      },
      onResult: (data, state) => {
        const snippets = data.snippets ?? [];
        if (snippets.length) {
          const lines = [];
          for (const item of snippets) {
            const line = formatPollingSnippet(item, state);
            if (line) lines.push(line);
          }
          if (lines.length) {
            appendResultText(UI.polling.result, lines.join("\n"));
          }
          state.lastSnippetId = data.last_id ?? state.lastSnippetId;
          maybeFirstUpdate(state, pollingEngine.startTime, 1, {});
        }
        const meta = data.metadata;
        if (meta?.server_cpu_ms_naive !== undefined) {
          state.metrics.serverCpuMs = meta.server_cpu_ms_naive;
        }
      },
      shouldStop: ({ phase, statusRes, resultRes, state }) => {
        if (phase === "status") {
          if (statusRes?.status === 404) return true;
        }
        if (phase === "result") {
          if (resultRes?.status === 404) return true;
          if (TERMINAL_STATES.has(state.status)) return true;
        }
        return false;
      },
      onUpdate: updateUI,
    });
    streamingEngine.start();
    pollingEngine.start();
    UI.runStatus.textContent = `Running (${taskId})`;
  } catch (error) {
    UI.runStatus.textContent = "Failed to start";
    UI.runButton.disabled = false;
    runInProgress = false;
  }
}

UI.controlsForm?.addEventListener("submit", runDemo);
UI.runButton?.addEventListener("click", runDemo);
