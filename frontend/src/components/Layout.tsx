import {
  Bot,
  LayoutDashboard,
  Lightbulb,
  LogOut,
  ReceiptText,
  Settings,
  Target,
  Upload,
} from "lucide-react";
import { NavLink, Outlet } from "react-router";
import { useAuth } from "../lib/auth";
import { MonthProvider } from "../lib/month";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, mobile: true },
  { to: "/transactions", label: "Transactions", icon: ReceiptText, mobile: true },
  { to: "/assistant", label: "AI Assistant", icon: Bot, mobile: true },
  { to: "/insights", label: "Insights", icon: Lightbulb, mobile: true },
  { to: "/budgets", label: "Budgets", icon: Target, mobile: true },
  { to: "/import", label: "Import", icon: Upload, mobile: false },
  { to: "/settings", label: "Settings", icon: Settings, mobile: false },
];

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid size-9 place-items-center rounded-xl bg-brand-600 text-lg font-extrabold text-white">₹</span>
      <span className="text-lg font-extrabold tracking-tight">SpendWise</span>
    </div>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const link = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
      isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
    }`;
  return (
    <MonthProvider>
      <div className="min-h-screen lg:pl-64">
        {/* desktop sidebar */}
        <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-slate-200 bg-white px-4 py-5 lg:flex">
          <Logo />
          <nav className="mt-8 flex flex-1 flex-col gap-1">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} end={to === "/"} className={link}>
                <Icon className="size-4.5" /> {label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3 rounded-xl border border-slate-200 p-3">
            <span className="grid size-9 place-items-center rounded-full bg-slate-900 text-sm font-bold text-white">
              {user?.name[0]?.toUpperCase()}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold">{user?.name}</div>
              <div className="truncate text-xs text-slate-500">{user?.email}</div>
            </div>
            <button onClick={logout} className="text-slate-400 hover:text-slate-700" title="Log out">
              <LogOut className="size-4.5" />
            </button>
          </div>
        </aside>

        {/* mobile top bar */}
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
          <Logo />
          <div className="flex gap-1">
            <NavLink to="/import" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100" title="Import">
              <Upload className="size-5" />
            </NavLink>
            <NavLink to="/settings" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100" title="Settings">
              <Settings className="size-5" />
            </NavLink>
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-4 pb-28 pt-6 sm:px-6 lg:px-8 lg:pb-10 lg:pt-8">
          <Outlet />
        </main>

        {/* mobile tab bar */}
        <nav className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-5 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] lg:hidden">
          {NAV.filter((n) => n.mobile).map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium ${isActive ? "text-brand-600" : "text-slate-500"}`
              }
            >
              <Icon className="size-5" />
              {label.replace("AI Assistant", "Ask AI")}
            </NavLink>
          ))}
        </nav>
      </div>
    </MonthProvider>
  );
}
