import { CalendarDays, Loader2, type LucideIcon, Upload } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { category } from "../lib/categories";
import { monthLabel } from "../lib/format";
import { useMonth } from "../lib/month";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function MonthPicker() {
  const { month, months, setMonth } = useMonth();
  if (!month) return null;
  return (
    <label className="relative inline-flex items-center">
      <CalendarDays className="pointer-events-none absolute left-3 size-4 text-slate-400" />
      <select className="input !w-auto pl-9 pr-8 font-medium" value={month} onChange={(e) => setMonth(e.target.value)}>
        {months.map((m) => (
          <option key={m} value={m}>
            {monthLabel(m)}
          </option>
        ))}
      </select>
    </label>
  );
}

export function StatCard({ label, value, hint, hintTone = "muted", icon: Icon }: {
  label: string;
  value: string;
  hint?: string;
  hintTone?: "muted" | "good" | "bad";
  icon: LucideIcon;
}) {
  const tone = { muted: "text-slate-500", good: "text-emerald-600", bad: "text-rose-600" }[hintTone];
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-500">{label}</span>
        <span className="grid size-9 place-items-center rounded-xl bg-brand-50 text-brand-600">
          <Icon className="size-4.5" />
        </span>
      </div>
      <div className="mt-2 text-2xl font-bold tracking-tight">{value}</div>
      {hint && <div className={`mt-1 text-xs font-medium ${tone}`}>{hint}</div>}
    </div>
  );
}

export function CategoryIcon({ name, size = "md" }: { name: string; size?: "sm" | "md" }) {
  const c = category(name);
  const Icon = c.icon;
  const box = size === "sm" ? "size-8 rounded-lg" : "size-10 rounded-xl";
  return (
    <span className={`grid shrink-0 place-items-center ${box}`} style={{ background: `${c.color}1f`, color: c.color }}>
      <Icon className={size === "sm" ? "size-4" : "size-5"} />
    </span>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
      <Loader2 className="size-5 animate-spin" /> {label}
    </div>
  );
}

export function Empty({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <span className="grid size-14 place-items-center rounded-2xl bg-slate-100 text-slate-400">
        <Icon className="size-7" />
      </span>
      <h3 className="mt-4 font-semibold">{title}</h3>
      <div className="mt-1 max-w-sm text-sm text-slate-500">{children}</div>
    </div>
  );
}

export function NoDataYet() {
  return (
    <div className="card">
      <Empty icon={Upload} title="No payments yet">
        Import a bank or UPI statement and this page fills up.
        <div className="mt-5">
          <Link to="/import" className="btn">Import a statement</Link>
        </div>
      </Empty>
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {error instanceof Error ? error.message : "Something went wrong."}
    </div>
  );
}

export function ProgressBar({ used, status }: { used: number; status: "ok" | "close" | "over" }) {
  const color = { ok: "bg-emerald-500", close: "bg-amber-500", over: "bg-rose-500" }[status];
  return (
    <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, used * 100)}%` }} />
    </div>
  );
}
