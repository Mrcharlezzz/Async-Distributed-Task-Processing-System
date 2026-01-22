export const formatMs = (ms) => `${Math.round(ms)} ms`;
export const formatSec = (ms) => `${(ms / 1000).toFixed(2)} s`;
export const formatBytes = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

export const TERMINAL_STATES = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export function recordLatency(metrics, elapsedMs) {
  if (elapsedMs !== undefined) {
    metrics.latencyTotalMs += elapsedMs;
    metrics.latencyCount += 1;
  }
}

export function applyStatusPayload(state, payload, { cpuKey, useServerSentTs } = {}) {
  if (!payload) return;
  const progress = payload.progress?.percentage ?? 0;
  state.progress = progress;
  state.status = payload.state ?? "RUNNING";
  state.statusMetrics = payload.metrics ?? null;
  const meta = payload.metadata;
  if (useServerSentTs && meta?.server_sent_ts) {
    const latencyMs = Date.now() - meta.server_sent_ts * 1000;
    state.metrics.latencyTotalMs += latencyMs;
    state.metrics.latencyCount += 1;
  }
  if (cpuKey && meta?.[cpuKey] !== undefined) {
    state.metrics.serverCpuMs = meta[cpuKey];
  }
}

export function applyStreamingStatus(state, payload) {
  applyStatusPayload(state, payload, { cpuKey: "server_cpu_ms_ws", useServerSentTs: true });
}

export function applyNaiveStatus(state, payload) {
  applyStatusPayload(state, payload, { cpuKey: "server_cpu_ms_naive", useServerSentTs: false });
}

export class StreamingEngine {
  constructor({
    taskId,
    wsClient,
    state,
    onResultChunk,
    onResult,
    onUpdate,
    onOpen,
    onError,
    onClose,
  }) {
    this.taskId = taskId;
    this.wsClient = wsClient;
    this.state = state;
    this.onResultChunk = onResultChunk;
    this.onResult = onResult;
    this.onUpdate = onUpdate;
    this.onOpen = onOpen;
    this.onError = onError;
    this.onClose = onClose;
    this.socket = null;
    this.startTime = performance.now();
  }

  start() {
    this.socket = this.wsClient.connect({
      taskId: this.taskId,
      onMessage: (data) => this._handleMessage(data),
      onOpen: this.onOpen,
      onError: this.onError,
      onClose: this.onClose,
    });
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
      return;
    }
    if (message.type === "task.status") {
      applyStreamingStatus(this.state, message.payload?.status);
    }
    if (message.type === "task.result_chunk") {
      const payload = message.payload;
      if (this.onResultChunk) {
        this.onResultChunk(payload, this.state);
      }
      if (payload?.is_last) {
        this.state.completed = true;
        this.state.metrics.totalMs = performance.now() - this.startTime;
      }
    }
    if (message.type === "task.result") {
      if (this.onResult) {
        this.onResult(message.payload, this.state);
      }
      this.state.completed = true;
      this.state.metrics.totalMs = performance.now() - this.startTime;
    }
    if (this.onUpdate) {
      this.onUpdate();
    }
  }
}

export class PollingEngine {
  constructor({
    taskId,
    api,
    state,
    intervalMs,
    onStatus,
    onResult,
    onUpdate,
    shouldStop,
  }) {
    this.taskId = taskId;
    this.api = api;
    this.state = state;
    this.intervalMs = intervalMs;
    this.onStatus = onStatus;
    this.onResult = onResult;
    this.onUpdate = onUpdate;
    this.shouldStop = shouldStop;
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

  _stopNow() {
    this.state.completed = true;
    this.state.metrics.totalMs = performance.now() - this.startTime;
    this.stop();
  }

  async _tick() {
    if (this.inFlight || this.state.completed) return;
    this.inFlight = true;
    try {
      const statusRes = await this.api.getStatus(this.taskId, this.state);
      this._record(statusRes.bytes);
      recordLatency(this.state.metrics, statusRes.elapsedMs);
      if (statusRes.ok && statusRes.data && this.onStatus) {
        this.onStatus(statusRes.data, this.state);
      }
      if (this.shouldStop?.({ phase: "status", statusRes, resultRes: null, state: this.state })) {
        this._stopNow();
        if (this.onUpdate) this.onUpdate();
        return;
      }

      const resultRes = await this.api.getResult(this.taskId, this.state);
      this._record(resultRes.bytes);
      recordLatency(this.state.metrics, resultRes.elapsedMs);
      if (resultRes.ok && resultRes.data && this.onResult) {
        this.onResult(resultRes.data, this.state);
      }
      if (this.shouldStop?.({ phase: "result", statusRes, resultRes, state: this.state })) {
        this._stopNow();
        if (this.onUpdate) this.onUpdate();
        return;
      }
      if (this.onUpdate) {
        this.onUpdate();
      }
    } finally {
      this.inFlight = false;
    }
  }

  _record(bytes) {
    this.state.metrics.requests += 1;
    this.state.metrics.bytes += bytes;
  }
}
