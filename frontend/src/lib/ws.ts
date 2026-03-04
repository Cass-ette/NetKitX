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
