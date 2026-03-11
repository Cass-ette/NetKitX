"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { connectPluginSession, sendSessionMessage, type PluginSessionEvent } from "@/lib/ws";
import { useAuth } from "@/lib/auth";
import "@xterm/xterm/css/xterm.css";

interface SessionTerminalProps {
  sessionId: string;
  pluginName: string;
  onDisconnect?: () => void;
}

/**
 * Renders an interactive terminal UI connected to a plugin session over WebSocket.
 *
 * Initializes an xterm.js terminal inside a responsive container, establishes a plugin session connection using the provided session ID and auth token, displays server output and prompt lines, captures and sends user commands, maintains command history, and invokes an optional disconnect callback when the session closes.
 *
 * @param sessionId - The plugin session identifier to connect to.
 * @param pluginName - Display name used in the terminal prompt.
 * @param onDisconnect - Optional callback invoked after the session disconnects.
 * @returns The React element containing the rendered session terminal.
 */
export function SessionTerminal({ sessionId, pluginName, onDisconnect }: SessionTerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const inputBufferRef = useRef("");
  const historyRef = useRef<string[]>([]);
  const historyIndexRef = useRef(-1);
  const token = useAuth((s) => s.token);
  const [connected, setConnected] = useState(false);

  const writePrompt = useCallback((term: Terminal, cwd?: string) => {
    const dir = cwd || "/";
    term.write(`\r\n\x1b[32m${pluginName}\x1b[0m:\x1b[34m${dir}\x1b[0m$ `);
  }, [pluginName]);

  const initTerminal = useCallback(() => {
    if (!containerRef.current || termRef.current || !token) return;

    let disposed = false;

    const container = containerRef.current;

    const term = new Terminal({
      fontSize: 13,
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      theme: {
        background: "#0a0a0a",
        foreground: "#e5e5e5",
        cursor: "#e5e5e5",
      },
      convertEol: true,
      scrollback: 10000,
      cursorBlink: true,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    const rafId = requestAnimationFrame(() => {
      if (disposed) return;
      try {
        term.open(container);
        fitAddon.fit();
      } catch { /* renderer not ready */ }
    });

    termRef.current = term;

    const resizeObserver = new ResizeObserver(() => {
      try { fitAddon.fit(); } catch { /* terminal disposed */ }
    });
    resizeObserver.observe(container);

    // Welcome message
    term.writeln(`\x1b[36m[${pluginName}] Session ${sessionId.slice(0, 8)}... connected\x1b[0m`);
    writePrompt(term);

    // Connect WebSocket
    const ws = connectPluginSession(
      sessionId,
      token,
      (event: PluginSessionEvent) => {
        if (disposed) return;

        if (event.type === "event" && event.data) {
          const inner = event.data as { type: string; data: Record<string, unknown> };
          if (inner.type === "result") {
            const output = (inner.data.output as string) || "";
            if (output) {
              term.writeln(output);
            }
            writePrompt(term, inner.data.cwd as string | undefined);
          } else if (inner.type === "error") {
            term.writeln(`\x1b[31m${(inner.data.error as string) || "Error"}\x1b[0m`);
            writePrompt(term);
          } else if (inner.type === "log") {
            term.writeln(`\x1b[33m${(inner.data.msg as string) || ""}\x1b[0m`);
          }
        } else if (event.type === "error") {
          const data = event.data as Record<string, unknown>;
          term.writeln(`\x1b[31m[Error] ${(data.error as string) || "Unknown"}\x1b[0m`);
          writePrompt(term);
        } else if (event.type === "session_end") {
          const data = event.data as Record<string, unknown>;
          term.writeln(`\x1b[31m[Session ended: ${data.reason || "unknown"}]\x1b[0m`);
        }
      },
      () => {
        if (!disposed) {
          setConnected(false);
          term.writeln("\r\n\x1b[31m[Disconnected]\x1b[0m");
          onDisconnect?.();
        }
      },
    );
    wsRef.current = ws;

    ws.onopen = () => {
      if (!disposed) setConnected(true);
    };

    // Handle keyboard input
    term.onData((data) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      const code = data.charCodeAt(0);

      if (code === 13) {
        // Enter
        const cmd = inputBufferRef.current.trim();
        term.write("\r\n");
        if (cmd) {
          historyRef.current.push(cmd);
          historyIndexRef.current = historyRef.current.length;
          sendSessionMessage(ws, { command: cmd });
        } else {
          writePrompt(term);
        }
        inputBufferRef.current = "";
      } else if (code === 127) {
        // Backspace
        if (inputBufferRef.current.length > 0) {
          inputBufferRef.current = inputBufferRef.current.slice(0, -1);
          term.write("\b \b");
        }
      } else if (data === "\x1b[A") {
        // Up arrow
        if (historyIndexRef.current > 0) {
          historyIndexRef.current--;
          const cmd = historyRef.current[historyIndexRef.current];
          // Clear current input
          term.write("\r\x1b[K");
          writePrompt(term);
          term.write(cmd);
          inputBufferRef.current = cmd;
        }
      } else if (data === "\x1b[B") {
        // Down arrow
        if (historyIndexRef.current < historyRef.current.length - 1) {
          historyIndexRef.current++;
          const cmd = historyRef.current[historyIndexRef.current];
          term.write("\r\x1b[K");
          writePrompt(term);
          term.write(cmd);
          inputBufferRef.current = cmd;
        } else {
          historyIndexRef.current = historyRef.current.length;
          term.write("\r\x1b[K");
          writePrompt(term);
          inputBufferRef.current = "";
        }
      } else if (code === 3) {
        // Ctrl+C
        inputBufferRef.current = "";
        term.write("^C");
        writePrompt(term);
      } else if (code >= 32) {
        // Printable characters
        inputBufferRef.current += data;
        term.write(data);
      }
    });

    return () => {
      disposed = true;
      cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      ws.close();
      term.dispose();
      termRef.current = null;
      wsRef.current = null;
    };
  }, [sessionId, token, pluginName, writePrompt, onDisconnect]);

  useEffect(() => {
    const cleanup = initTerminal();
    return () => cleanup?.();
  }, [initTerminal]);

  return (
    <div className="relative">
      {!connected && (
        <div className="absolute top-2 right-2 z-10 rounded bg-yellow-500/20 px-2 py-1 text-xs text-yellow-500">
          Connecting...
        </div>
      )}
      <div
        ref={containerRef}
        className="h-96 w-full rounded-md overflow-hidden"
      />
    </div>
  );
}
