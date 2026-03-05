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
    term.open(containerRef.current);
    fitAddon.fit();

    termRef.current = term;

    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit();
    });
    resizeObserver.observe(containerRef.current);

    // Fetch historical logs
    if (token) {
      api<{ logs: string[] }>(`/api/v1/tasks/${taskId}/logs`, {
        token,
      })
        .then(({ logs }) => {
          for (const line of logs) {
            term.writeln(line);
          }
        })
        .catch(() => {
          term.writeln("\x1b[31m[Failed to load historical logs]\x1b[0m");
        });
    }

    // Connect WebSocket for real-time log events
    const ws = connectTaskWS(
      taskId,
      (event) => {
        if (event.type === "log") {
          const msg = (event.data.msg as string) || JSON.stringify(event.data);
          term.writeln(msg);
        } else if (event.type === "status") {
          const status = event.data.status as string;
          if (status === "done") {
            term.writeln("\x1b[32m[Task completed]\x1b[0m");
          } else if (status === "failed") {
            term.writeln("\x1b[31m[Task failed]\x1b[0m");
          } else if (status === "running") {
            term.writeln("\x1b[36m[Task started]\x1b[0m");
          }
        } else if (event.type === "error") {
          term.writeln(
            `\x1b[31m[Error] ${(event.data.error as string) || "Unknown error"}\x1b[0m`,
          );
        }
      },
      () => {
        // WebSocket closed
      },
    );

    return () => {
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
