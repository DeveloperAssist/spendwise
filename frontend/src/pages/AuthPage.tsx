import { Bot, ShieldCheck, Upload } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";
import { Logo } from "../components/Layout";
import { ErrorNote } from "../components/ui";
import { useAuth } from "../lib/auth";

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (isLogin) await login(form.email, form.password);
      else await register(form.name, form.email, form.password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-gradient-to-br from-brand-700 to-emerald-900 p-12 text-white lg:flex">
        <div className="flex items-center gap-2.5 text-lg font-extrabold">
          <span className="grid size-9 place-items-center rounded-xl bg-white/15">₹</span> SpendWise
        </div>
        <div>
          <h2 className="text-4xl font-extrabold leading-tight tracking-tight">Know exactly where your money goes.</h2>
          <ul className="mt-8 space-y-4 text-emerald-50">
            <li className="flex gap-3"><Upload className="size-5 shrink-0" /> Import your bank or UPI statement (CSV or Excel)</li>
            <li className="flex gap-3"><Bot className="size-5 shrink-0" /> Ask the AI assistant anything about your spending</li>
            <li className="flex gap-3"><ShieldCheck className="size-5 shrink-0" /> Your data stays in your own account</li>
          </ul>
        </div>
        <p className="text-sm text-emerald-100/80">A free student project by Developers Assist.</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <h1 className="text-2xl font-bold tracking-tight">{isLogin ? "Welcome back" : "Create your account"}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {isLogin ? "Log in to see your spending." : "It takes 20 seconds. No card, no bank login."}
          </p>
          <div className="mt-6 space-y-4">
            {!isLogin && (
              <div>
                <label className="label" htmlFor="name">Name</label>
                <input id="name" className="input" required maxLength={80} value={form.name} onChange={set("name")} autoComplete="name" />
              </div>
            )}
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input id="email" type="email" className="input" required value={form.email} onChange={set("email")} autoComplete="email" />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input id="password" type="password" className="input" required minLength={isLogin ? 1 : 8} maxLength={128}
                value={form.password} onChange={set("password")} autoComplete={isLogin ? "current-password" : "new-password"} />
              {!isLogin && <p className="mt-1 text-xs text-slate-500">At least 8 characters.</p>}
            </div>
            <ErrorNote error={error} />
            <button className="btn w-full" disabled={busy}>{busy ? "Please wait…" : isLogin ? "Log in" : "Create account"}</button>
          </div>
          <p className="mt-6 text-center text-sm text-slate-500">
            {isLogin ? "New here? " : "Already have an account? "}
            <Link to={isLogin ? "/register" : "/login"} className="font-semibold text-brand-700 hover:underline">
              {isLogin ? "Create an account" : "Log in"}
            </Link>
          </p>
          {isLogin && (
            <button type="button" className="mt-3 w-full text-center text-xs text-slate-400 hover:text-slate-600"
              onClick={() => setForm({ ...form, email: "demo@spendwise.dev", password: "demo-password" })}>
              Use the demo account (after <code>spendwise demo</code>)
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
