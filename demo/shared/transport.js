export const API_BASE = "/api";
export const WS_BASE = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;

export async function getJson(url, { onError } = {}) {
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
    if (onError) {
      onError({ url, error: String(error) });
    }
    return { ok: false, status: 0, data: null, bytes: 0, elapsedMs, error: String(error) };
  }
}

export async function postJson(url, body, { onError } = {}) {
  const start = performance.now();
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
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
    if (onError) {
      onError({ url, error: String(error) });
    }
    return { ok: false, status: 0, data: null, bytes: 0, elapsedMs, error: String(error) };
  }
}

export class WsClient {
  constructor(base = WS_BASE, { keepaliveMs = 1000 } = {}) {
    this.base = base;
    this.keepaliveMs = keepaliveMs;
  }

  connect({ taskId, onMessage, onOpen, onError, onClose }) {
    const ws = new WebSocket(`${this.base}/ws/tasks/${taskId}`);
    const keepalive = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, this.keepaliveMs);
    if (onOpen) {
      ws.addEventListener("open", onOpen);
    }
    if (onMessage) {
      ws.addEventListener("message", (event) => onMessage(event.data));
    }
    if (onError) {
      ws.addEventListener("error", onError);
    }
    ws.addEventListener("close", (event) => {
      clearInterval(keepalive);
      if (onClose) {
        onClose(event);
      }
    });
    return {
      close: () => ws.close(),
    };
  }
}
