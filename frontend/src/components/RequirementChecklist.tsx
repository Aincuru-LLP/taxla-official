'use client';
import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertCircle,
  Clock,
  ShieldCheck,
  Sparkles,
  ChevronDown,
  ChevronUp,
  FileCheck2,
  FileSpreadsheet,
} from 'lucide-react';
import { useApplicationRequirements } from '@/lib/api-client';

interface RequirementChecklistProps {
  applicationId: string;
  onOpenTemplateGenerator?: () => void;
}

export const RequirementChecklist: React.FC<RequirementChecklistProps> = ({
  applicationId,
  onOpenTemplateGenerator,
}) => {
  const { data: reqData, isLoading } = useApplicationRequirements(applicationId);
  const [filter, setFilter] = useState<'all' | 'completed' | 'missing'>('all');

  const reqs = reqData?.requirements || [];
  const pct = reqData?.completion_percentage || 0;

  const completedCount = reqs.filter((r) => r.is_completed).length;
  const missingCount = reqs.filter((r) => !r.is_completed).length;

  const filtered = reqs.filter((r) => {
    if (filter === 'completed') return r.is_completed;
    if (filter === 'missing') return !r.is_completed;
    return true;
  });

  return (
    <div className="glass-panel p-5 rounded-2xl border border-slate-800 bg-slate-950/80 shadow-xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <span>27 Standard Udyam Requirements</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              DR-001
            </span>
          </h3>
          <p className="text-[11px] text-slate-400">
            Official Ministry of MSME registration checklist & completeness scoring
          </p>
        </div>

        {onOpenTemplateGenerator && (
          <button
            onClick={onOpenTemplateGenerator}
            className="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 text-xs font-semibold flex items-center gap-1.5 transition-all"
          >
            <FileSpreadsheet className="w-3.5 h-3.5" />
            <span>Generate Requirement Form</span>
          </button>
        )}
      </div>

      {/* Progress Bar & Stat Badges */}
      <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-300 font-semibold">Intake Completeness</span>
          <span className="text-indigo-400 font-extrabold">{pct}%</span>
        </div>
        <div className="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 transition-all duration-500 rounded-full"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="flex items-center justify-between pt-1 text-[11px] text-slate-400">
          <span className="flex items-center gap-1 text-emerald-400">
            <CheckCircle2 className="w-3 h-3" /> {completedCount} Completed
          </span>
          <span className="flex items-center gap-1 text-amber-400">
            <AlertCircle className="w-3 h-3" /> {missingCount} Missing
          </span>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setFilter('all')}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
            filter === 'all'
              ? 'bg-slate-800 text-white'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          All ({reqs.length})
        </button>
        <button
          onClick={() => setFilter('completed')}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
            filter === 'completed'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Completed ({completedCount})
        </button>
        <button
          onClick={() => setFilter('missing')}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
            filter === 'missing'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Missing ({missingCount})
        </button>
      </div>

      {/* Requirements List */}
      <div className="max-h-[420px] overflow-y-auto space-y-2 pr-1">
        {isLoading ? (
          <div className="text-center py-8 text-xs text-slate-500">
            Loading requirements checklist...
          </div>
        ) : (
          filtered.map((r) => (
            <div
              key={r.id}
              className={`p-3 rounded-xl border transition-all flex items-start justify-between ${
                r.is_completed
                  ? 'bg-slate-900/40 border-slate-800/80 hover:border-slate-700'
                  : 'bg-amber-950/10 border-amber-500/20 hover:border-amber-500/40'
              }`}
            >
              <div className="flex items-start space-x-2.5">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
                  r.is_completed
                    ? 'bg-emerald-500/10 text-emerald-400'
                    : 'bg-amber-500/10 text-amber-400'
                }`}>
                  {r.is_completed ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Clock className="w-3.5 h-3.5" />}
                </div>

                <div className="space-y-0.5">
                  <div className="text-xs font-semibold text-white">{r.display_label}</div>
                  {r.value ? (
                    <div className="text-[11px] text-slate-300 font-mono bg-slate-950/70 px-2 py-0.5 rounded border border-slate-800 inline-block">
                      {r.value}
                    </div>
                  ) : (
                    <div className="text-[11px] text-amber-400/80">Pending intake / upload</div>
                  )}
                </div>
              </div>

              <div className="flex items-center space-x-1.5 shrink-0">
                {r.source && (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                    {r.source === 'DOCUMENT_EXTRACTED' ? 'OCR Extracted' : 'User Input'}
                  </span>
                )}
                <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                  r.is_completed
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                }`}>
                  {r.is_completed ? 'PASS' : 'MISSING'}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
