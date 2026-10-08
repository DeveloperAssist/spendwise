import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Trash2 } from "lucide-react";
import { useState } from "react";
import { CategoryIcon, ErrorNote, MonthPicker, PageHeader, ProgressBar, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { SPEND_CATEGORIES } from "../lib/categories";
import { monthLabel, rupees } from "../lib/format";
import { useMonth } from "../lib/month";
import type { Dashboard } from "../lib/types";

export default function Budgets() {
  const { month } = useMonth();
  const qc = useQueryClient();
  const dash = useQuery({
    queryKey: ["dashboard", month],
    queryFn: () => api<Dashboard>(`/api/analytics/dashboard?month=${month}`),
    enabled: !!month,
  });
  const budgets = useQuery({ queryKey: ["budgets"], queryFn: () => api<{ category: string; limit: number }[]>("/api/budgets") });
  const save = useMutation({
    mutationFn: ({ cat, limit }: { cat: string; limit: number }) => api(`/api/budgets/${cat}`, { method: "PUT", json: { limit } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const remove = useMutation({
    mutationFn: (cat: string) => api(`/api/budgets/${cat}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries(),
  });

  if (!budgets.data || (month && !dash.data)) return <Spinner />;
  const limits = Object.fromEntries(budgets.data.map((b) => [b.category, b.limit]));
  const spent = dash.data?.summary.by_category ?? {};

  return (
    <>
      <PageHeader title="Budgets" subtitle={`A monthly limit per category. Spending shown for ${month ? monthLabel(month) : "this month"}.`}
        actions={<MonthPicker />} />
      <ErrorNote error={save.error || remove.error} />
      <div className="grid gap-3 sm:grid-cols-2">
        {SPEND_CATEGORIES.filter((c) => c.key !== "transfers").map((c) => (
          <BudgetRow key={c.key} cat={c.key} label={c.label} spent={spent[c.key] ?? 0} limit={limits[c.key]}
            onSave={(limit) => save.mutate({ cat: c.key, limit })} onRemove={() => remove.mutate(c.key)} />
        ))}
      </div>
    </>
  );
}

function BudgetRow({ cat, label, spent, limit, onSave, onRemove }: {
  cat: string; label: string; spent: number; limit?: number; onSave: (n: number) => void; onRemove: () => void;
}) {
  const [value, setValue] = useState(limit ? String(limit) : "");
  const used = limit ? spent / limit : 0;
  const status = !limit ? "ok" : used > 1 ? "over" : used >= 0.8 ? "close" : "ok";
  const dirty = value !== (limit ? String(limit) : "") && Number(value) > 0;
  return (
    <div className="card">
      <div className="flex items-center gap-3">
        <CategoryIcon name={cat} />
        <div className="flex-1">
          <div className="font-semibold">{label}</div>
          <div className="text-xs text-slate-500">{rupees(spent)} spent{limit ? ` of ${rupees(limit)}` : ""}</div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-sm text-slate-400">₹</span>
          <input className="input !w-24 !py-1.5 text-right" type="number" min="1" placeholder="No limit" value={value}
            onChange={(e) => setValue(e.target.value)} onKeyDown={(e) => e.key === "Enter" && dirty && onSave(Number(value))} />
          {dirty && <button className="btn !px-2.5 !py-1.5" onClick={() => onSave(Number(value))} title="Save"><Check className="size-4" /></button>}
          {limit && !dirty && <button className="p-1.5 text-slate-300 hover:text-rose-600" onClick={() => { setValue(""); onRemove(); }} title="Remove"><Trash2 className="size-4" /></button>}
        </div>
      </div>
      {limit ? (
        <div className="mt-3">
          <ProgressBar used={used} status={status} />
          <div className={`mt-1.5 text-xs font-medium ${status === "over" ? "text-rose-600" : status === "close" ? "text-amber-600" : "text-slate-500"}`}>
            {status === "over" ? `Over by ${rupees(Math.round(spent - limit))}` : `${rupees(Math.round(limit - spent))} left`}
          </div>
        </div>
      ) : null}
    </div>
  );
}
