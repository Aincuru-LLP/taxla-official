"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  Users,
  MessageSquare,
  FileBox,
  Settings,
  LogOut,
  UserCheck,
} from "lucide-react";

import { logoutRequest } from "@/api/workflow";
import { useAuthStore } from "@/stores/authStore";

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
}

const navItems: NavItem[] = [
  { name: "Overview", href: "/", icon: LayoutDashboard, exact: true },
  { name: "Applications", href: "/applications", icon: FileText },
  { name: "Customers", href: "/customers", icon: Users },
  { name: "WhatsApp", href: "/whatsapp", icon: MessageSquare },
  { name: "Documents", href: "/documents", icon: FileBox },
  { name: "Settings", href: "/settings", icon: Settings },
];

function formatRole(role?: string): string {
  if (!role) return "Employee";
  const r = role.toUpperCase();
  if (r.includes("SUPER_ADMIN") || r === "ADMIN") return "Administrator";
  if (r.includes("BRANCH_ADMIN") || r.includes("MANAGER")) return "Manager";
  if (r.includes("REVIEWER")) return "Reviewer";
  return "Employee";
}

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  // Do not render sidebar on /login or customer requirement form /form/*
  if (pathname === "/login" || pathname.startsWith("/form")) return null;

  async function handleLogout() {
    try {
      await logoutRequest();
    } finally {
      clearAuth();
      router.replace("/login");
    }
  }

  return (
    <aside className="w-[240px] flex-shrink-0 bg-slate-900 text-slate-300 flex flex-col h-screen border-r border-slate-800 sticky top-0 select-none z-30">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-5 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-indigo-600 flex items-center justify-center text-white font-black text-sm tracking-wider shadow-sm">
            TX
          </div>
          <div>
            <div className="font-bold text-white text-base tracking-tight leading-none">
              TAXLA
            </div>
            <div className="text-[10px] text-indigo-400 font-semibold uppercase tracking-wider mt-0.5">
              Operations
            </div>
          </div>
        </div>
      </div>

      {/* Primary Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = item.exact
            ? pathname === item.href
            : pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? "bg-indigo-600 text-white font-semibold shadow-sm"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? "text-white" : "text-slate-400"}`} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* User Card & Logout Footer */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/40">
        <div className="px-2 py-2 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 text-xs font-bold">
            {user?.name ? user.name.charAt(0).toUpperCase() : <UserCheck className="w-4 h-4 text-slate-400" />}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold text-white truncate">
              {user?.name || user?.email?.split("@")[0] || "Operator"}
            </div>
            <div className="text-[11px] text-slate-400 truncate flex items-center gap-1.5">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              {formatRole(user?.role)}
            </div>
          </div>
        </div>

        <button
          onClick={handleLogout}
          className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-1.5 rounded text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Sign out of TAXLA"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  );
}