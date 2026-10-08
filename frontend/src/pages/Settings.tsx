import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, Download, LogOut, Trash2, User as UserIcon } from "lucide-react";
import { useState } from "react";
import { ErrorNote, PageHeader } from "../components/ui";
import { api, download } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const status = useQuery({ queryKey: ["ai-status"], queryFn: () => api<{ enabled: boolean; model: string | null }>("/api/ai/status") });
  const [password, setPassword] = useState("");
  const remove = useMutation({
    mutationFn: () => api("/api/auth/me", { method: "DELETE", json: { password } }),
    onSuccess: logout,
  });

  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h2 className="flex items-center gap-2 font-semibold"><UserIcon className="size-4.5" /> Account</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-slate-500">Name</dt><dd className="font-medium">{user?.name}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Email</dt><dd className="font-medium">{user?.email}</dd></div>
          </dl>
          <button className="btn-ghost mt-4" onClick={logout}><LogOut className="size-4" /> Log out</button>
        </div>

        <div className="card">
          <h2 className="flex items-center gap-2 font-semibold"><Bot className="size-4.5" /> AI</h2>
          <p className="mt-3 text-sm text-slate-600">
            {status.data?.enabled ? <>On, using <code className="rounded bg-slate-100 px-1.5 py-0.5">{status.data.model}</code> on Groq.</> : "Off: the server has no Groq API key."}
          </p>
          <p className="mt-2 text-xs text-slate-500">Only merchant names (for categories) and your monthly totals (for insights and the assistant) are sent to the AI. Never your password or account details.</p>
        </div>

        <div className="card">
          <h2 className="flex items-center gap-2 font-semibold"><Download className="size-4.5" /> Your data</h2>
          <p className="mt-2 text-sm text-slate-600">Download every transaction as a CSV file you can open in Excel.</p>
          <button className="btn-ghost mt-4" onClick={() => download("/api/transactions/export.csv", "spendwise-all.csv")}>
            <Download className="size-4" /> Export all transactions
          </button>
        </div>

        <div className="card border-rose-200">
          <h2 className="flex items-center gap-2 font-semibold text-rose-700"><Trash2 className="size-4.5" /> Delete account</h2>
          <p className="mt-2 text-sm text-slate-600">Deletes your account and every transaction, budget and import. This can't be undone.</p>
          <div className="mt-4 flex gap-2">
            <input type="password" className="input" placeholder="Your password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <button className="btn !bg-rose-600 hover:!bg-rose-700" disabled={!password || remove.isPending}
              onClick={() => confirm("Delete your account and all your data?") && remove.mutate()}>Delete</button>
          </div>
          <div className="mt-3"><ErrorNote error={remove.error} /></div>
        </div>
      </div>
    </>
  );
}
