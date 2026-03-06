import { create } from "zustand";
import type { ChatMessage, AgentMode } from "@/types";

const PANEL_WIDTH_KEY = "ai-chat-panel-width";
const DEFAULT_WIDTH = 420;
const MIN_WIDTH = 320;
const MAX_WIDTH = 800;

interface AIChatStore {
  // Panel state
  panelOpen: boolean;
  panelWidth: number;
  togglePanel: () => void;
  setPanelOpen: (open: boolean) => void;
  setPanelWidth: (width: number) => void;

  // Conversation state
  messages: ChatMessage[];
  input: string;
  loading: boolean;
  error: string | null;
  mode: "defense" | "offense";
  agentMode: AgentMode;
  currentTurn: number;
  maxTurns: number;

  // Conversation actions
  setMessages: (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
  setInput: (input: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setMode: (mode: "defense" | "offense") => void;
  setAgentMode: (mode: AgentMode) => void;
  setCurrentTurn: (turn: number) => void;
  clearChat: () => void;
}

export { MIN_WIDTH, MAX_WIDTH };

export const useAIChatStore = create<AIChatStore>((set) => ({
  // Panel state
  panelOpen: false,
  panelWidth: typeof window !== "undefined"
    ? Number(localStorage.getItem(PANEL_WIDTH_KEY)) || DEFAULT_WIDTH
    : DEFAULT_WIDTH,

  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  setPanelOpen: (open) => set({ panelOpen: open }),
  setPanelWidth: (width) => {
    const clamped = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, width));
    if (typeof window !== "undefined") {
      localStorage.setItem(PANEL_WIDTH_KEY, String(clamped));
    }
    set({ panelWidth: clamped });
  },

  // Conversation state
  messages: [],
  input: "",
  loading: false,
  error: null,
  mode: "offense",
  agentMode: "chat",
  currentTurn: 0,
  maxTurns: 0,

  // Conversation actions
  setMessages: (updater) =>
    set((s) => ({
      messages: typeof updater === "function" ? updater(s.messages) : updater,
    })),
  setInput: (input) => set({ input }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setMode: (mode) => set({ mode }),
  setAgentMode: (agentMode) => set({ agentMode }),
  setCurrentTurn: (turn) => set({ currentTurn: turn }),
  clearChat: () => set({ messages: [], input: "", error: null, currentTurn: 0 }),
}));
