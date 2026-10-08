import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Download, Plus, ReceiptText, Search, Trash2, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { CategoryIcon, Empty, ErrorNote, MonthPicker, NoDataYet, PageHeader, Spinner } from "../components/ui";
import { api, download } from "../lib/api";
import { CATEGORIES, category, SOURCE_LABEL } from "../lib/categories";
import { dateLabel, plural, rupees } from "../lib/format";
import { useMonth } from "../lib/month";
import type { Page, Transaction } from "../lib/types";

const SOURCE_STYLE: Record<string, string> = {
  rule: "bg-slate-100 text-slate-600",
  learned: "bg-slate-100 text-slate-600",
  ai: "bg-emerald-50 text-emerald-700",
  you: "bg-blue-50 text-blue-700",
  other: "bg-amber-50 text-amber-700",
};

/** Today in the browser's own timezone (toISOString is UTC: before 5:30 AM IST that's yesterday). */
function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export default function Transactions() {
  const { month, ready } = useMonth();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [cat, setCat] = useState("");
  const [kind, setKind] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const q = useDebounced(search);
  useEffect(() => {
    setPage(1);
  }, [q, cat, kind, sort, month]);

  const params = new URLSearchParams({ page: String(page), page_size: "25", sort });
  if (month) params.set("month", month);
  if (q) params.set("q", q);
  if (cat) params.set("category", cat);
  if (kind) params.set("kind", kind);
  const list = useQuery({
    queryKey: ["transactions", params.toString()],
    queryFn: () => api<Page<Transaction>>(`/api/transactions?${params}`),
    enabled: !!month,
    placeholderData: keepPreviousData,
  });

  const refresh = () => qc.invalidateQueries();
  const fix = useMutation({
    mutationFn: ({ id, category }: { id: number; category: string }) =>
      api<Transaction>(`/api/transactions/${id}`, { method: "PATCH", json: { category } }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: number) => api(`/api/transactions/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  const data = list.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  if (ready && !month) {
    return (
      <>
        <PageHeader title="Transactions" actions={<button className="btn" onClick={() => setAdding(true)}><Plus className="size-4" /> Add</button>} />
        <NoDataYet />
        {adding && <AddDialog onClose={() => setAdding(false)} onSaved={refresh} />}
      </>
    );
  }

  return (
    <>
      <PageHeader title="Transactions" subtitle="Change a category once and every payment to that merchant follows."
        actions={<>
          <MonthPicker />
          <button className="btn-ghost" disabled={!month} onClick={() => month && download(`/api/transactions/export.csv?month=${month}`, `spendwise-${month}.csv`)}>
            <Download className="size-4" /> Export
          </button>
          <button className="btn" onClick={() => setAdding(true)}><Plus className="size-4" /> Add</button>
        </>} />

      <div className="card !p-0">
        <div className="flex flex-wrap gap-2 border-b border-slate-100 p-4">
          <label className="relative min-w-48 flex-1">
            <Search className="pointer-events-none absolute left-3 top-3 size-4 text-slate-400" />
            <input className="input pl-9" placeholder="Search merchant or description" value={search} maxLength={60}
              onChange={(e) => setSearch(e.target.value)} />
          </label>
          <select className="input !w-auto" value={cat} onChange={(e) => setCat(e.target.value)}>
            <option value="">All categories</option>
            {CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
          <select className="input !w-auto" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">Money in & out</option>
            <option value="debit">Money out</option>
            <option value="credit">Money in</option>
          </select>
          <select className="input !w-auto" value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="biggest">Biggest first</option>
          </select>
        </div>
        <ErrorNote error={list.error || fix.error || remove.error} />
        {!data ? <Spinner /> : data.items.length === 0 ? (
          <Empty icon={ReceiptText} title="No transactions here">Try another month or filter, or import a statement.</Empty>
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.items.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-3 px-4 py-3 sm:flex-nowrap">
                <CategoryIcon name={t.category} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{t.merchant}</div>
                  <div className="truncate text-xs text-slate-500" title={t.description}>
                    {dateLabel(t.date)} · {t.description}
                  </div>
                </div>
                <select className="input !w-auto !py-1.5 text-xs" value={t.category} disabled={fix.isPending}
                  onChange={(e) => fix.mutate({ id: t.id, category: e.target.value })}>
                  {CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
                </select>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${SOURCE_STYLE[t.category_source]}`}>
                  {SOURCE_LABEL[t.category_source]}
                </span>
                <span className={`w-24 text-right font-semibold tabular-nums ${t.kind === "credit" ? "text-emerald-600" : ""}`}>
                  {t.kind === "credit" ? "+" : "−"}{rupees(t.amount)}
                </span>
                <button className="text-slate-300 hover:text-rose-600" title="Delete" aria-label={`Delete ${t.merchant}`}
                  onClick={() => confirm(`Delete ${t.merchant} ${rupees(t.amount)}?`) && remove.mutate(t.id)}>
                  <Trash2 className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
        {data && data.total > 0 && (
          <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-500">
            <span>{plural(data.total, "transaction")}</span>
            <div className="flex items-center gap-2">
              <button className="btn-ghost !px-2.5 !py-1.5" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft className="size-4" /></button>
              <span>Page {page} of {pages}</span>
              <button className="btn-ghost !px-2.5 !py-1.5" aria-label="Next page" disabled={page >= pages} onClick={() => setPage(page + 1)}><ChevronRight className="size-4" /></button>
            </div>
          </div>
        )}
      </div>
      {adding && <AddDialog onClose={() => setAdding(false)} onSaved={refresh} />}
    </>
  );
}

function AddDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({ date: localToday(), merchant: "", amount: "", kind: "debit", category: "", note: "" });
  const save = useMutation({
    mutationFn: () => api<Transaction>("/api/transactions", {
      method: "POST",
      json: { ...form, amount: Number(form.amount), category: form.category || null, note: form.note || null },
    }),
    onSuccess: () => { onSaved(); onClose(); },
  });
  const submit = (e: FormEvent) => { e.preventDefault(); save.mutate(); };
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-20 grid place-items-center bg-slate-900/40 p-4" onClick={onClose}>
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()} className="card w-full max-w-md space-y-4"
        role="dialog" aria-modal="true" aria-labelledby="add-title">
        <div className="flex items-center justify-between">
          <h2 id="add-title" className="text-lg font-semibold">Add a payment</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="text-slate-400 hover:text-slate-700"><X className="size-5" /></button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label">Date</label><input type="date" className="input" required autoFocus value={form.date} onChange={set("date")} /></div>
          <div><label className="label">Amount (₹)</label><input type="number" className="input" required min="0.01" step="0.01" value={form.amount} onChange={set("amount")} /></div>
        </div>
        <div><label className="label">Paid to / from</label><input className="input" required maxLength={120} placeholder="e.g. Swiggy" value={form.merchant} onChange={set("merchant")} /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label">Type</label>
            <select className="input" value={form.kind} onChange={set("kind")}><option value="debit">Money out</option><option value="credit">Money in</option></select></div>
          <div><label className="label">Category</label>
            <select className="input" value={form.category} onChange={set("category")}>
              <option value="">Let SpendWise decide</option>
              {CATEGORIES.map((c) => <option key={c.key} value={c.key}>{category(c.key).label}</option>)}
            </select></div>
        </div>
        <div><label className="label">Note (optional)</label><input className="input" maxLength={200} value={form.note} onChange={set("note")} /></div>
        <ErrorNote error={save.error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save"}</button>
        </div>
      </form>
    </div>
  );
}
