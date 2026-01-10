"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  finalizeClarifier,
  sendClarifierTurn,
  type ClarifierFinalizeResponse,
  type ClarifierSessionMessage,
} from "@/app/actions";

type ClarifierQuestion = {
  id: string;
  text: string;
  priority: "blocking" | "important" | "optional";
  suggested_answers?: string[];
};

type ClarifierChatModalProps = {
  isOpen: boolean;
  sessionId: string | null;
  token: string | null;
  initialAssistantMessage: string;
  initialQuestions?: ClarifierQuestion[];
  onClose: () => void;
  onReadyToStart: (result: { enrichedPrompt: string; finalSummary: string; sessionId: string }) => void;
};

function nowIso() {
  try {
    return new Date().toISOString();
  } catch {
    return null;
  }
}

export default function ClarifierChatModal({
  isOpen,
  sessionId,
  token,
  initialAssistantMessage,
  initialQuestions,
  onClose,
  onReadyToStart,
}: ClarifierChatModalProps) {
  const [messages, setMessages] = useState<ClarifierSessionMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [turnCount, setTurnCount] = useState(0);
  const [finalized, setFinalized] = useState<ClarifierFinalizeResponse | null>(null);
  const [activeQuestions, setActiveQuestions] = useState<ClarifierQuestion[]>([]);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const sendLatchRef = useRef(false);

  const canSend = Boolean(isOpen && sessionId && token && !isSending && input.trim() && !finalized);

  useEffect(() => {
    if (!isOpen) return;
    setMessages([
      {
        role: "assistant",
        content: initialAssistantMessage || "Let’s clarify a few details to ensure a solid design. What’s the target deployment environment?",
        created_at: nowIso(),
      },
    ]);
    setActiveQuestions(initialQuestions ?? []);
    setInput("");
    setIsSending(false);
    setTurnCount(0);
    setFinalized(null);
  }, [isOpen, initialAssistantMessage, initialQuestions]);

  useEffect(() => {
    if (!isOpen) return;
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [isOpen, messages.length, finalized?.status]);

  const appendMessage = useCallback((m: ClarifierSessionMessage) => {
    setMessages((prev) => [...prev, m]);
  }, []);

  const doFinalize = useCallback(
    async (proceedAsDraft: boolean) => {
      if (!sessionId || !token) return;
      setIsSending(true);
      try {
        const result = await finalizeClarifier(sessionId, proceedAsDraft, token);
        setFinalized(result);
        appendMessage({
          role: "assistant",
          content: result.final_summary || "Clarifier finalized.",
          created_at: nowIso(),
        });
      } finally {
        setIsSending(false);
      }
    },
    [appendMessage, sessionId, token]
  );

  const handleSend = useCallback(async () => {
    if (!sessionId || !token) return;
    if (sendLatchRef.current) return;
    const text = input.trim();
    if (!text) return;
    sendLatchRef.current = true;

    setInput("");
    appendMessage({ role: "user", content: text, created_at: nowIso() });

    setIsSending(true);
    try {
      const result = await sendClarifierTurn(sessionId, text, token);
      setTurnCount(result.turn_count);
      appendMessage({ role: "assistant", content: result.assistant_message, created_at: nowIso() });
      setActiveQuestions(result.questions ?? []);

      if (result.status === "finalized") {
        await doFinalize(false);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Clarifier turn failed";
      appendMessage({ role: "assistant", content: `Error: ${msg}`, created_at: nowIso() });
    } finally {
      setIsSending(false);
      sendLatchRef.current = false;
    }
  }, [appendMessage, doFinalize, input, sessionId, token]);

  const handleChipClick = useCallback((value: string) => {
    const v = (value || "").trim();
    if (!v) return;
    setInput((prev) => {
      const p = (prev || "").trim();
      if (!p) return v;
      // Avoid duplicating if already present
      if (p.split("\n").map((s) => s.trim()).includes(v)) return prev;
      return `${prev}\n${v}`.trim();
    });
  }, []);

  const handleStart = useCallback(() => {
    if (!finalized || !sessionId) return;
    onReadyToStart({
      enrichedPrompt: finalized.enriched_prompt,
      finalSummary: finalized.final_summary,
      sessionId,
    });
  }, [finalized, onReadyToStart, sessionId]);

  const title = useMemo(() => {
    if (finalized) return `Clarifier (${finalized.status === "ready" ? "Ready" : "Draft"})`;
    return "Clarifier";
  }, [finalized]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-3xl overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xl">
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-[var(--foreground)]">{title}</div>
            <div className="mt-0.5 text-xs text-[var(--foreground-muted)]">
              Turn {turnCount}/5 • Ask questions, or start as draft anytime.
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-sm border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] hover:border-[var(--accent)] hover:text-[var(--foreground)]"
          >
            Close
          </button>
        </div>

        <div ref={scrollRef} className="max-h-[55vh] overflow-y-auto bg-[var(--background)] p-4">
          <div className="space-y-3">
            {messages.map((m, idx) => {
              const isUser = m.role === "user";
              return (
                <div key={idx} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-lg border px-3 py-2 text-sm ${
                      isUser
                        ? "border-[var(--accent)]/40 bg-[var(--accent)]/10 text-[var(--foreground)]"
                        : "border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)]"
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{m.content}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="border-t border-[var(--border)] bg-[var(--surface)] p-4">
          {!finalized ? (
            <div className="flex flex-col gap-2">
              {activeQuestions.length > 0 && (
                <div className="flex flex-col gap-2 rounded-md border border-[var(--border)] bg-[var(--background)] p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                    Suggested answers
                  </div>
                  <div className="space-y-3">
                    {(() => {
                      const q = activeQuestions[0];
                      if (!q) return null;
                      return (
                        <div key={q.id} className="space-y-2">
                          <div className="text-xs text-[var(--foreground)]">{q.text}</div>
                          <div className="flex flex-wrap gap-2">
                            {(q.suggested_answers ?? []).slice(0, 4).map((ans, idx) => (
                              <button
                                key={`${q.id}-${idx}`}
                                type="button"
                                onClick={() => handleChipClick(ans)}
                                className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs text-[var(--foreground)] hover:border-[var(--accent)]"
                              >
                                {ans}
                              </button>
                            ))}
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                </div>
              )}
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your answer…"
                rows={3}
                className="w-full resize-none rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] outline-none focus:border-[var(--accent)]"
                disabled={isSending || !sessionId || !token}
              />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => doFinalize(true)}
                  disabled={isSending || !sessionId || !token}
                  className="rounded-sm border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-xs font-semibold text-[var(--foreground-muted)] hover:border-[var(--accent)] hover:text-[var(--foreground)] disabled:opacity-50"
                >
                  Start anyway (Draft)
                </button>
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={!canSend}
                  className="rounded-sm border border-[var(--accent)] bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
                >
                  {isSending ? "Sending…" : "Send"}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-xs text-[var(--foreground-muted)]">
                Finalized as <span className="font-semibold text-[var(--foreground)]">{finalized.status}</span>.
              </div>
              <button
                type="button"
                onClick={handleStart}
                className="rounded-sm border border-[var(--accent)] bg-[var(--accent)] px-4 py-2 text-xs font-semibold text-white"
              >
                Start run →
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


