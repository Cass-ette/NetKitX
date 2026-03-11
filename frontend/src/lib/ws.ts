const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

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

export function sendSessionMessage(ws: WebSocket, data: Record<string, unknown>): void {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "message", data }));
  }
}
