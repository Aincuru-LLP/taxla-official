"use client";

import React from "react";
import Link from "next/link";
import {
  Settings,
  Users,
  MessageSquare,
  Cpu,
  ArrowRight,
  Shield,
  Server,
} from "lucide-react";

export default function SettingsHubPage() {
  const sections = [
    {
      title: "Employee & Role Management",
      description: "Manage system users, access privileges, and assigned operations personas.",
      href: "/settings/users",
      icon: Users,
      badge: "RBAC Controls",
    },
    {
      title: "WhatsApp Cloud API Configuration",
      description: "Inspect message delivery status, approved templates, and webhook endpoints.",
      href: "/settings/whatsapp",
      icon: MessageSquare,
      badge: "Connected",
    },
    {
      title: "System & Automation Target",
      description: "View UDYAM_TARGET_URL configurations, browser execution modes, and operational timeouts.",
      href: "/settings/system",
      icon: Server,
      badge: "Operational",
    },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="pb-6 border-b border-slate-200">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Settings & System Administration
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Configure employee access, messaging integrations, and automation environment parameters.
        </p>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {sections.map((sec) => {
          const Icon = sec.icon;
          return (
            <Link
              key={sec.title}
              href={sec.href}
              className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs hover:border-indigo-400 hover:shadow-sm transition-all group flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 uppercase tracking-wider">
                    {sec.badge}
                  </span>
                </div>

                <h2 className="text-base font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                  {sec.title}
                </h2>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                  {sec.description}
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-indigo-600">
                <span>Configure</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}