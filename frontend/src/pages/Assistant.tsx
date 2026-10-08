import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, Send, Wrench } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Empty, ErrorNote, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import type { ChatMessage, ChatStep } from "../lib/types";

const SUGGESTIONS = [
  "How much did I spend on Swiggy last month?",
  "What subscriptions do I pay for?",
  "Did my food spending go up from August to September?",
  "Show my 5 biggest payments in September",
];

function StepChip({ step }: { step: ChatStep }) {
  const args = Object.entries(step.args).map(([k, v]) => `${k}: ${v}`).join(", ");
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono text-[11px] ${step.ok ? "bg-slate-100 text-slate-600" : "bg-rose-50 text-rose-600"}`}>
      <Wrench className="size-3" /> {step.tool}({args})
    </span>
  );
}

export default function Assistant() {
  const status = useQuery({ queryKey: ["ai-status"], queryFn: () => api<{ enabled: boolean; model: string | null }>("/api/ai/status") });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const chat = useMutation({
    mutationFn: (message: string) =>
      api<{ answer: string; steps: ChatStep[] }>("/api/ai/chat", {
        method: "POST",
        json: { message, history: messages.slice(-10).map(({ role, content }) => ({ role, content })) },
      }),
    onSuccess: (r) => setMessages((m) => [...m, { role: "assistant", content: r.answer, steps: r.steps }]),
  });
  // braces: an effect's return value is its cleanup, and newer browsers return a Promise from scroll methods
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chat.isPending]);

  function ask(message: string) {
    const m = message.trim();
    if (!m || chat.isPending) return;
    setMessages((prev) => [...prev, { role: "user", content: m }]);
    setText("");
    chat.mutate(m);
  }
  const submit = (e: FormEvent) => { e.preventDefault(); ask(text); };

  if (status.data && !status.data.enabled) {
    return (
      <>
        <PageHeader title="AI Assistant" />
        <div className="card"><Empty icon={Bot} title="AI is off on this server">Add a free Groq API key (GROQ_API_KEY) to the backend, then come back to ask questions about your spending.</Empty></div>
      </>
    );
  }

  return (
    <div className="flex h-[calc(100dvh-11rem)] flex-col lg:h-[calc(100dvh-5rem)]">
      <PageHeader title="AI Assistant" subtitle="Ask anything about your spending. It looks up the real numbers before answering." />
      <div className="card flex min-h-0 flex-1 flex-col !p-0">
        <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center py-8 text-center">
              <span className="grid size-14 place-items-center rounded-2xl bg-brand-50 text-brand-600"><Bot className="size-7" /></span>
              <h2 className="mt-4 font-semibold">What would you like to know?</h2>
              <div className="mt-5 flex max-w-xl flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => ask(s)} className="rounded-full border border-slate-200 px-3.5 py-2 text-sm text-slate-600 hover:border-brand-500 hover:text-brand-700">{s}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${m.role === "user" ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-800"}`}>
                <div className="whitespace-pre-wrap">{m.content.replace(/\*\*/g, "")}</div>
                {m.steps && m.steps.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5 border-t border-slate-200 pt-2">
                    {m.steps.map((s, j) => <StepChip key={j} step={s} />)}
                  </div>
                )}
              </div>
            </div>
          ))}
          {chat.isPending && <div className="text-sm text-slate-500">Looking it up…</div>}
          <ErrorNote error={chat.error} />
          <div ref={bottom} />
        </div>
        <form onSubmit={submit} className="flex gap-2 border-t border-slate-100 p-3">
          <input className="input" aria-label="Your question" placeholder="e.g. How much did I spend on travel in July?" value={text} maxLength={1000}
            onChange={(e) => setText(e.target.value)} />
          <button className="btn" aria-label="Send" disabled={!text.trim() || chat.isPending}><Send className="size-4" /></button>
        </form>
      </div>
    </div>
  );
}
