"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  History,
  Shield,
  CreditCard,
  MessageSquare,
  Cpu,
  Clock,
  User,
} from "lucide-react";

import { fetchApplicationActivity } from "@/lib/api";

export default function ActivityTabPage() {
  const params = useParams();
  const applicationId = params?.id as string;

  const [activities, setActivities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!applicationId) return;
    fetchApplicationActivity(applicationId)
      .then((data) => setActivities(data || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [applicationId]);

  if (loading) {
    return <div className="p-12 text-center text-sm text-slate-400">Loading activity feed…</div>;
  }

  function getCategoryIcon(cat: string) {
    switch (cat) {
      case "PAYMENT":
        return <CreditCard className="w-3.5 h-3.5 text-emerald-600" />;
      case "COMMUNICATION":
        return <MessageSquare className="w-3.5 h-3.5 text-indigo-600" />;
      case "AUTOMATION":
        return <Cpu className="w-3.5 h-3.5 text-purple-600" />;
      default:
        return <Shield className="w-3.5 h-3.5 text-slate-600" />;
    }
  }

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">Application Activity & Audit Trail</h2>
          <p className="text-xs text-slate-500 mt-1">
            Immutable chronological record of state changes, human reviews, payments, and worker executions.
          </p>
        </div>

        <div className="text-xs text-slate-500 font-semibold">
          Total Events: {activities.length}
        </div>
      </div>

      {/* Activity Timeline List */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
        {activities.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            No activity records found for this application.
          </div>
        ) : (
          <div className="relative pl-6 border-l-2 border-slate-200 space-y-6">
            {activities.map((item) => (
              <div key={item.id} className="relative group">
                {/* Node icon */}
                <div className="absolute -left-[31px] top-0 w-6 h-6 rounded-full bg-white border-2 border-slate-300 flex items-center justify-center shadow-2xs group-hover:border-indigo-600 transition-colors">
                  {getCategoryIcon(item.category)}
                </div>

                <div className="bg-slate-50 border border-slate-200/80 rounded-lg p-3.5 hover:border-slate-300 transition-colors">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-900">{item.title}</span>
                    <span className="text-[11px] text-slate-400 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      <span>{item.timestamp ? new Date(item.timestamp).toLocaleString() : "—"}</span>
                    </span>
                  </div>

                  {item.description && (
                    <p className="text-xs text-slate-600 mt-1">{item.description}</p>
                  )}

                  <div className="mt-2.5 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[11px] text-slate-500">
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3 text-slate-400" />
                      <span>Actor: <strong className="text-slate-700">{item.actor_name}</strong></span>
                    </span>
                    <span className="px-2 py-0.5 rounded bg-white border border-slate-200 text-[10px] font-semibold text-slate-600">
                      {item.category}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
