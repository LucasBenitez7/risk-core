"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  AlertCircle,
  Radio,
  ClipboardList,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/lib/hooks/useAuth";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/policies", label: "Policies", icon: FileText },
  { href: "/claims", label: "Claims", icon: AlertCircle },
  { href: "/events", label: "Events", icon: Radio },
  { href: "/audit", label: "Audit", icon: ClipboardList },
] as const;

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { username, logout } = useAuth();

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="flex w-56 shrink-0 flex-col border-r border-slate-700 bg-slate-900">
        <div className="px-4 py-5">
          <span className="text-lg font-semibold tracking-tight text-white">
            RiskCore
          </span>
        </div>
        <nav className="flex-1 space-y-1 px-2">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-slate-700 text-white"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center justify-between border-t border-slate-700 px-4 py-3">
          <span className="truncate text-sm text-slate-400">
            {username ?? "—"}
          </span>
          <button
            onClick={() => logout()}
            className="text-slate-400 transition-colors hover:text-white"
            title="Logout"
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto bg-slate-950 p-6">
        {children}
      </main>
    </div>
  );
}
