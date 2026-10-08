import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Gauge, PiggyBank, Sparkles, Upload, Wallet } from "lucide-react";
import { Link } from "react-router";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Empty, ErrorNote, MonthPicker, PageHeader, ProgressBar, Spinner, StatCard } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { category } from "../lib/categories";
import { dateLabel, monthLabel, percent, plural, rupees, rupeesShort } from "../lib/format";
import { useMonth } from "../lib/month";
import type { Dashboard as DashboardData } from "../lib/types";

function Change({ value, invert = false }: { value: number | null | undefined; invert?: boolean }) {
  if (value === null || value === undefined) return <span className="text-slate-400">new</span>;
  if (value === 0) return <span className="text-slate-400">same</span>;
  const up = value > 0;
  const bad = invert ? !up : up; // spending going up is bad; income going up is good
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`inline-flex items-center gap-0.5 ${bad ? "text-rose-600" : "text-emerald-600"}`}>
      <Icon className="size-3.5" /> {Math.abs(value)}%
    </span>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { month, months, ready, error } = useMonth();
  const dash = useQuery({
    queryKey: ["dashboard", month],
    queryFn: () => api<DashboardData>(`/api/analytics/dashboard?month=${month}`),
    enabled: !!month,
  });
  const aiStatus = useQuery({ queryKey: ["ai-status"], queryFn: () => api<{ enabled: boolean }>("/api/ai/status") });
  const insights = useMutation({
    mutationFn: () => api<{ text: string }>(`/api/ai/insights?month=${month}`, { method: "POST" }),
  });

  if (!ready) return error ? <ErrorNote error={error} /> : <Spinner />;
  if (months.length === 0) {
    return (
      <>
        <PageHeader title={`Hi, ${user?.name.split(" ")[0]} 👋`} subtitle="Let's see where your money goes." />
        <div className="card">
          <Empty icon={Upload} title="Import your first statement">
            Upload a bank or UPI statement (CSV or Excel). SpendWise sorts every payment for you.
            <div className="mt-5">
              <Link to="/import" className="btn">Import a statement</Link>
            </div>
          </Empty>
        </div>
      </>
    );
  }
  if (!dash.data) return dash.error ? <ErrorNote error={dash.error} /> : <Spinner />;

  const { summary: s, change, budgets, trend, daily } = dash.data;
  const cats = Object.entries(s.by_category);
  const topCat = cats[0];

  return (
    <>
      <PageHeader title={`Hi, ${user?.name.split(" ")[0]} 👋`} subtitle={`Here's ${monthLabel(dash.data.month)} at a glance.`} actions={<MonthPicker />} />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Spent" value={rupees(s.spent)} icon={Wallet}
          hint={change.total == null ? "no data last month" : `${change.total > 0 ? "▲" : "▼"} ${Math.abs(change.total)}% vs last month`}
          hintTone={change.total == null ? "muted" : change.total > 0 ? "bad" : "good"} />
        <StatCard label="Income" value={rupees(s.income)} icon={ArrowDownRight} hint={`${plural(s.payments, "payment")} out`} />
        <StatCard label="Saved" value={rupees(s.saved)} icon={PiggyBank} hint={s.savings_rate === null ? "no income this month" : `${percent(s.savings_rate)} of income`}
          hintTone={s.saved >= 0 ? "good" : "bad"} />
        <StatCard label="Daily average" value={rupees(Math.round(s.daily_average))} icon={Gauge}
          hint={s.forecast ? `on track for ${rupees(Math.round(s.forecast))}` : topCat ? `most on ${category(topCat[0]).label.toLowerCase()}` : undefined} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <div className="card lg:col-span-3">
          <h2 className="font-semibold">Where it went</h2>
          {cats.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-500">No spending this month.</p>
          ) : (
            <div className="mt-2 grid items-center gap-4 sm:grid-cols-[200px_1fr]">
              <div className="h-[200px]">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={cats.map(([k, v]) => ({ name: category(k).label, value: v, key: k }))} dataKey="value"
                      innerRadius={62} outerRadius={92} paddingAngle={2} stroke="none">
                      {cats.map(([k]) => <Cell key={k} fill={category(k).color} />)}
                    </Pie>
                    <Tooltip formatter={(v) => rupees(Number(v))} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="space-y-2.5">
                {cats.slice(0, 7).map(([k, v]) => (
                  <li key={k} className="flex items-center gap-3 text-sm">
                    <span className="size-2.5 rounded-full" style={{ background: category(k).color }} />
                    <span className="flex-1 text-slate-600">{category(k).label}</span>
                    <span className="font-semibold">{rupees(v)}</span>
                    <span className="w-14 text-right text-xs"><Change value={change[k]} /></span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div className="card lg:col-span-2">
          <h2 className="font-semibold">Income vs spending</h2>
          <div className="mt-3 h-[210px]">
            <ResponsiveContainer>
              <BarChart data={trend.map((t) => ({ ...t, label: monthLabel(t.month, "short") }))} barGap={2}>
                <CartesianGrid vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} />
                <YAxis tickFormatter={rupeesShort} tickLine={false} axisLine={false} fontSize={11} width={48} />
                <Tooltip formatter={(v) => rupees(Number(v))} />
                <Bar dataKey="income" name="Income" fill="#a7f3d0" radius={[6, 6, 0, 0]} />
                <Bar dataKey="spent" name="Spent" fill="#059669" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <div className="card lg:col-span-3">
          <h2 className="font-semibold">Spending day by day</h2>
          <div className="mt-3 h-[190px]">
            <ResponsiveContainer>
              <AreaChart data={daily}>
                <defs>
                  <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="date" tickFormatter={(d) => String(Number(d.slice(8)))} tickLine={false} axisLine={false} fontSize={11} interval={4} />
                <YAxis tickFormatter={rupeesShort} tickLine={false} axisLine={false} fontSize={11} width={48} />
                <Tooltip labelFormatter={(d) => dateLabel(String(d))} formatter={(v) => rupees(Number(v))} />
                <Area type="monotone" dataKey="spent" name="Spent" stroke="#059669" strokeWidth={2} fill="url(#g)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Budgets</h2>
            <Link to="/budgets" className="text-sm font-medium text-brand-700 hover:underline">Edit</Link>
          </div>
          {budgets.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">No budgets yet. <Link className="text-brand-700 underline" to="/budgets">Set one</Link></p>
          ) : (
            <ul className="mt-4 space-y-4">
              {[...budgets].sort((a, b) => b.used - a.used).slice(0, 5).map((b) => (
                <li key={b.category}>
                  <div className="mb-1.5 flex justify-between text-sm">
                    <span className="font-medium">{category(b.category).label}
                      {b.status !== "ok" && <span className={`ml-2 rounded-full px-2 py-0.5 text-[11px] font-semibold ${b.status === "over" ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-700"}`}>
                        {b.status === "over" ? "Over budget" : "Almost there"}</span>}
                    </span>
                    <span className="text-slate-500">{rupees(b.spent)} / {rupees(b.limit)}</span>
                  </div>
                  <ProgressBar used={b.used} status={b.status} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <div className="card lg:col-span-2">
          <h2 className="font-semibold">Top merchants</h2>
          <ul className="mt-3 divide-y divide-slate-100">
            {s.top_merchants.map((m) => (
              <li key={m.merchant} className="flex items-center justify-between py-2.5 text-sm">
                <span className="font-medium">{m.merchant}</span>
                <span className="text-slate-500">{m.payments}× · <b className="text-slate-900">{rupees(m.spent)}</b></span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card bg-gradient-to-br from-brand-50 to-white lg:col-span-3">
          <h2 className="flex items-center gap-2 font-semibold"><Sparkles className="size-4.5 text-brand-600" /> AI insights</h2>
          {!aiStatus.data?.enabled ? (
            <p className="mt-3 text-sm text-slate-500">Add a free Groq API key to the server to turn on AI insights and the assistant.</p>
          ) : insights.data ? (
            <ul className="mt-3 space-y-2 text-sm leading-relaxed text-slate-700">
              {insights.data.text.split("\n").filter(Boolean).map((line, i) => <li key={i}>{line.replace(/^-\s*/, "• ")}</li>)}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Three quick observations about {monthLabel(dash.data.month)}, written by AI from your real numbers.</p>
          )}
          <ErrorNote error={insights.error} />
          {aiStatus.data?.enabled && (
            <button className="btn mt-4" onClick={() => insights.mutate()} disabled={insights.isPending}>
              <Sparkles className="size-4" /> {insights.isPending ? "Thinking…" : insights.data ? "Refresh insights" : "Get AI insights"}
            </button>
          )}
        </div>
      </div>
      <p className="mt-6 text-center text-xs text-slate-400">
        Tip: fix a category once on the Transactions page, and SpendWise remembers it for that merchant.
      </p>
    </>
  );
}
