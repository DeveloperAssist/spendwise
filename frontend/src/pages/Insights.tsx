import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Repeat, Sparkles } from "lucide-react";
import { Bold } from "../components/Bold";
import { CategoryIcon, Empty, ErrorNote, MonthPicker, NoDataYet, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { dateLabel, monthLabel, rupees } from "../lib/format";
import { useMonth } from "../lib/month";
import type { Subscription, Unusual } from "../lib/types";

export default function Insights() {
  const { month, ready } = useMonth();
  const subs = useQuery({
    queryKey: ["subscriptions"],
    queryFn: () => api<{ items: Subscription[]; per_month: number }>("/api/analytics/subscriptions"),
  });
  const odd = useQuery({
    queryKey: ["unusual", month],
    queryFn: () => api<{ items: Unusual[] }>(`/api/analytics/unusual?month=${month}`),
    enabled: !!month,
  });
  const aiStatus = useQuery({ queryKey: ["ai-status"], queryFn: () => api<{ enabled: boolean }>("/api/ai/status") });
  const ai = useMutation({ mutationFn: () => api<{ text: string }>(`/api/ai/insights?month=${month}`, { method: "POST" }) });

  if (ready && !month) {
    return (
      <>
        <PageHeader title="Insights" />
        <NoDataYet />
      </>
    );
  }
  return (
    <>
      <PageHeader title="Insights" subtitle="Patterns SpendWise found in your payments." actions={<MonthPicker />} />

      <div className="card bg-gradient-to-br from-brand-50 to-white">
        <h2 className="flex items-center gap-2 font-semibold"><Sparkles className="size-4.5 text-brand-600" /> AI summary of {month ? monthLabel(month) : "the month"}</h2>
        {!aiStatus.data?.enabled ? (
          <p className="mt-2 text-sm text-slate-500">AI is off on this server. Add a free Groq API key to turn it on.</p>
        ) : ai.data ? (
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-slate-700">
            {ai.data.text.split("\n").filter(Boolean).map((l, i) => <li key={i}><Bold text={l.replace(/^-\s*/, "• ")} /></li>)}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-slate-500">The AI reads totals, budgets, subscriptions and unusual payments that SpendWise computed, and turns them into three tips. It never invents a number.</p>
        )}
        <ErrorNote error={ai.error} />
        {aiStatus.data?.enabled && (
          <button className="btn mt-4" onClick={() => ai.mutate()} disabled={ai.isPending}>
            <Sparkles className="size-4" /> {ai.isPending ? "Thinking…" : "Summarise this month"}
          </button>
        )}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="card">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-semibold"><Repeat className="size-4.5 text-slate-500" /> Subscriptions & regular bills</h2>
            {subs.data && <span className="text-sm text-slate-500">{rupees(subs.data.per_month)}/month</span>}
          </div>
          <p className="mt-1 text-xs text-slate-500">Same merchant, a similar amount, about once a month.</p>
          {!subs.data ? <Spinner /> : subs.data.items.length === 0 ? (
            <Empty icon={Repeat} title="None found yet">They show up after three monthly payments.</Empty>
          ) : (
            <ul className="mt-3 divide-y divide-slate-100">
              {subs.data.items.map((s) => (
                <li key={s.merchant} className="flex items-center gap-3 py-3">
                  <CategoryIcon name={s.category} size="sm" />
                  <div className="flex-1">
                    <div className="font-medium">{s.merchant}
                      <span className={`ml-2 rounded-full px-2 py-0.5 text-[11px] font-semibold ${s.type === "bill" ? "bg-slate-100 text-slate-600" : "bg-violet-50 text-violet-700"}`}>
                        {s.type === "bill" ? "Bill" : "Subscription"}</span>
                    </div>
                    <div className="text-xs text-slate-500">Paid {s.times}× · next around {dateLabel(s.next_expected)}</div>
                  </div>
                  <span className="font-semibold">{rupees(s.amount)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <h2 className="flex items-center gap-2 font-semibold"><AlertTriangle className="size-4.5 text-amber-500" /> Unusual payments</h2>
          <p className="mt-1 text-xs text-slate-500">At least 3× what you usually pay in that category.</p>
          <ErrorNote error={odd.error} />
          {!odd.data ? <Spinner /> : odd.data.items.length === 0 ? (
            <Empty icon={AlertTriangle} title="Nothing unusual">No payment stands out this month.</Empty>
          ) : (
            <ul className="mt-3 divide-y divide-slate-100">
              {odd.data.items.map((u) => (
                <li key={u.id} className="flex items-center gap-3 py-3">
                  <CategoryIcon name={u.category} size="sm" />
                  <div className="flex-1">
                    <div className="font-medium">{u.merchant}</div>
                    <div className="text-xs text-slate-500">{dateLabel(u.date)} · usually about {rupees(Math.round(u.typical))}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold">{rupees(u.amount)}</div>
                    <div className="text-xs font-semibold text-amber-600">{u.times_usual}× usual</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}
