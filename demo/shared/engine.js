export const formatMs = (ms) => `${Math.round(ms)} ms`;
export const formatSec = (ms) => `${(ms / 1000).toFixed(2)} s`;
export const formatBytes = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

export function recordLatency(metrics, elapsedMs) {
  if (elapsedMs !== undefined) {
    metrics.latencyTotalMs += elapsedMs;
    metrics.latencyCount += 1;
  }
}
