const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

/**
 * Open a WebSocket connection to receive real-time events for a specific task.
 *
 * @param taskId - The numeric identifier of the task to subscribe to
 * @param onEvent - Callback invoked with each parsed event object `{ type: string; data: Record<string, unknown> }`
 * @param onClose - Optional callback invoked when the WebSocket closes
 * @returns The WebSocket instance connected to the task events endpoint
 */
export function connectTaskWS(
  taskId: number,
  onEvent: (event: { type: string; data: Record<string, unknown> }) => void,
  onClose?: () => void,
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/api/v1/ws/tasks/${taskId}`);

  ws.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      onEvent(event);
    } catch {
      // ignore parse errors
    }
  };

  ws.onclose = () => {
    onClose?.();
  };

  // Send periodic pings to keep alive
  const interval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send("ping");
    } else {
      clearInterval(interval);
    }
  }, 30000);

  return ws;
}

export interface PluginSessionEvent {
  type: "event" | "pong" | "error" | "session_end";
  data?: { type: string; data: Record<string, unknown> } | Record<string, unknown>;
}

/**
 * Open a WebSocket to a plugin session endpoint and deliver parsed session events to a callback.
 *
 * The socket connects to /api/v1/ws/plugin-sessions/{sessionId}?token={token}, invokes `onEvent` with each incoming message parsed as a `PluginSessionEvent` (parse errors are ignored), invokes `onClose` when the socket closes, and sends a JSON `{"type":"ping"}` every 30 seconds while the socket is open.
 *
 * @param sessionId - The plugin session identifier to connect to
 * @param token - Authentication token (URL-encoded when appended to the URL)
 * @param onEvent - Callback invoked with each parsed `PluginSessionEvent` received from the server
 * @param onClose - Optional callback invoked when the WebSocket closes
 * @returns The opened WebSocket connected to the plugin session
 */
export function connectPluginSession(
  sessionId: string,
  token: string,
  onEvent: (event: PluginSessionEvent) => void,
  onClose?: () => void,
): WebSocket {
  const ws = new WebSocket(
    `${WS_BASE}/api/v1/ws/plugin-sessions/${sessionId}?token=${encodeURIComponent(token)}`,
  );

  ws.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data) as PluginSessionEvent;
      onEvent(event);
    } catch {
      // ignore parse errors
    }
  };

  ws.onclose = () => {
    onClose?.();
  };

  const interval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "ping" }));
    } else {
      clearInterval(interval);
    }
  }, 30000);

  return ws;
}

/**
 * Send a JSON-encoded `message` payload over the given WebSocket when it is open.
 *
 * @param ws - The WebSocket to send the payload on
 * @param data - The object to include as the `data` field of the outgoing message
 */
export function sendSessionMessage(ws: WebSocket, data: Record<string, unknown>): void {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "message", data }));
  }
}
