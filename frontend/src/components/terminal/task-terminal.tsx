"use client";

import { useEffect, useRef, useCallback } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { api } from "@/lib/api";
import { connectTaskWS } from "@/lib/ws";
import { useAuth } from "@/lib/auth";
import "@xterm/xterm/css/xterm.css";

interface TaskTerminalProps {
  taskId: number;
}

export function TaskTerminal({ taskId }: TaskTerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const token = useAuth((s) => s.token);

  const initTerminal = useCallback(() => {
    if (!containerRef.current || termRef.current) return;

    let disposed = false;
    const safeWriteln = (term: Terminal, data: string) => {
      if (disposed) return;
      try { term.writeln(data); } catch { /* terminal disposed or renderer not ready */ }
    };

    const container = containerRef.current;

    const term = new Terminal({
      disableStdin: true,
      fontSize: 13,
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      theme: {
        background: "#0a0a0a",
        foreground: "#e5e5e5",
        cursor: "#e5e5e5",
      },
      convertEol: true,
      scrollback: 5000,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    // Delay term.open() to next animation frame so the container is fully laid out.
    // Without this, xterm's internal Viewport calls syncScrollArea before the
    // renderer is initialized, causing "_renderer.value is undefined".
    const rafId = requestAnimationFrame(() => {
      if (disposed) return;
      try {
        term.open(container);
        fitAddon.fit();
      } catch { /* renderer not ready */ }
    });

    termRef.current = term;

    const resizeObserver = new ResizeObserver(() => {
      try { fitAddon.fit(); } catch { /* terminal disposed or renderer not ready */ }
    });
    resizeObserver.observe(container);

    // Fetch historical logs
    if (token) {
      api<{ logs: string[] }>(`/api/v1/tasks/${taskId}/logs`, {
        token,
      })
        .then(({ logs }) => {
          for (const line of logs) {
            safeWriteln(term, line);
          }
        })
        .catch(() => {
          safeWriteln(term, "\x1b[31m[Failed to load historical logs]\x1b[0m");
        });
    }

    // Connect WebSocket for real-time log events
    const ws = connectTaskWS(
      taskId,
      (event) => {
        if (event.type === "log") {
          const msg = (event.data.msg as string) || JSON.stringify(event.data);
          safeWriteln(term, msg);
        } else if (event.type === "status") {
          const status = event.data.status as string;
          if (status === "done") {
            safeWriteln(term, "\x1b[32m[Task completed]\x1b[0m");
          } else if (status === "failed") {
            safeWriteln(term, "\x1b[31m[Task failed]\x1b[0m");
          } else if (status === "running") {
            safeWriteln(term, "\x1b[36m[Task started]\x1b[0m");
          }
        } else if (event.type === "error") {
          safeWriteln(
            term,
            `\x1b[31m[Error] ${(event.data.error as string) || "Unknown error"}\x1b[0m`,
          );
        }
      },
      () => {
        // WebSocket closed
      },
    );

    return () => {
      disposed = true;
      cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      ws.close();
      term.dispose();
      termRef.current = null;
    };
  }, [taskId, token]);

  useEffect(() => {
    const cleanup = initTerminal();
    return () => cleanup?.();
  }, [initTerminal]);

  return (
    <div
      ref={containerRef}
      className="h-64 w-full rounded-md overflow-hidden"
    />
  );
}
