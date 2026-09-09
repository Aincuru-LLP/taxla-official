"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  CheckCircle2,
  AlertCircle,
  Clock,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Send,
  Sparkles,
} from "lucide-react";

import { fetchRequirements, requestMissingInfo } from "@/lib/api";

export default function RequirementsTabPage() {
  const params = useParams();
  const applicationId = params?.id as string;

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Request Info Modal State
  const [showRequestModal, setShowRequestModal] = useState(false);
  const [selectedFields, setSelectedFields] = useState<string[]>([]);
  const [customNote, setCustomNote] = useState("");
  const [sendingRequest, setSendingRequest] = useState(false);
  const [requestSuccess, setRequestSuccess] = useState(false);

  useEffect(() => {
    if (!applicationId) return;
    fetchRequirements(applicationId)
      .then((res) => setData(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [applicationId]);

  if (loading) {
    return <div className="p-12 text-center text-sm text-slate-400">Loading requirements…</div>;
  }

  const sections = data?.sections || [];
  const completionPct = data?.completion_percentage ?? 0;

  const commonMissingItems = [
    "Bank Account Number & IFSC",
    "Aadhaar Number",
    "PAN Card Copy",
    "Latest Electricity Bill for Address",
    "GST Registration Number",
    "Turnover & Investment Figures",
    "Unit Address Verification",
  ];

  function toggleFieldSelection(field: string) {
    if (selectedFields.includes(field)) {
      setSelectedFields(selectedFields.filter((f) => f !== field));
    } else {
      setSelectedFields([...selectedFields, field]);
    }
  }

  async function handleSendRequest(e: React.FormEvent) {
    e.preventDefault();
    if (selectedFields.length === 0) return;
    setSendingRequest(true);
    try {
      await requestMissingInfo(applicationId, selectedFields, customNote);
      setRequestSuccess(true);
      setTimeout(() => {
        setRequestSuccess(false);
        setShowRequestModal(false);
        setSelectedFields([]);
        setCustomNote("");
      }, 2000);
    } catch (err) {
      console.error("Failed to dispatch request info:", err);
    } finally {
      setSendingRequest(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Top Banner: Completion Status + Request Info Action */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold text-slate-900">
              Requirements Review (11 Operational Domains)
            </h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
              {completionPct}% Complete
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Structured information collected from customer intake form, verified against official guidelines.
          </p>
        </div>

        <button
          onClick={() => setShowRequestModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-colors"
        >
          <MessageSquare className="w-4 h-4" />
          <span>Request Info (WhatsApp)</span>
        </button>
      </div>

      {/* 11 Sections Grid */}
      <div className="space-y-4">
        {sections.map((sec: any) => {
          const isComplete = sec.status === "COMPLETE";
          const isNeedsReview = sec.status === "NEEDS_REVIEW";

          return (
            <div
              key={sec.section_id}
              className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs"
            >
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                      isComplete
                        ? "bg-emerald-100 text-emerald-700"
                        : isNeedsReview
                        ? "bg-amber-100 text-amber-700"
                        : "bg-rose-100 text-rose-700"
                    }`}
                  >
                    {isComplete ? (
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    ) : (
                      <AlertCircle className="w-3.5 h-3.5" />
                    )}
                  </div>
                  <h3 className="text-sm font-bold text-slate-900">{sec.title}</h3>
                </div>

                <span
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${
                    isComplete
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : isNeedsReview
                      ? "bg-amber-50 text-amber-800 border-amber-200"
                      : "bg-rose-50 text-rose-700 border-rose-200"
                  }`}
                >
                  {sec.status.replace(/_/g, " ")}
                </span>
              </div>

              {/* Section Fields Key-Value Table */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-3 text-xs">
                {Object.entries(sec.fields || {}).map(([key, val]) => {
                  if (typeof val === "object" && val !== null) {
                    return (
                      <div key={key} className="col-span-full bg-slate-50 p-3 rounded-lg border border-slate-200">
                        <span className="font-semibold text-slate-700 capitalize">{key.replace(/_/g, " ")}:</span>
                        <pre className="text-[11px] text-slate-600 mt-1 whitespace-pre-wrap font-sans">
                          {JSON.stringify(val, null, 2)}
                        </pre>
                      </div>
                    );
                  }

                  return (
                    <div key={key} className="p-2 bg-slate-50/60 rounded border border-slate-100">
                      <div className="text-[11px] text-slate-500 capitalize">{key.replace(/_/g, " ")}</div>
                      <div className="font-semibold text-slate-900 mt-0.5 truncate">
                        {val === true ? "Yes" : val === false ? "No" : String(val || "—")}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Request Info WhatsApp Modal */}
      {showRequestModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-lg w-full border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">Request Missing Information</h3>
                <p className="text-xs text-slate-500">Dispatch an official WhatsApp reminder to the customer.</p>
              </div>
              <button
                onClick={() => setShowRequestModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleSendRequest} className="p-6 space-y-4">
              {requestSuccess ? (
                <div className="p-6 text-center space-y-2">
                  <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
                  <div className="text-sm font-bold text-slate-900">Request Dispatched!</div>
                  <div className="text-xs text-slate-500">
                    A WhatsApp notification listing the required fields has been sent to the customer.
                  </div>
                </div>
              ) : (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-2">
                      Select Missing Requirements to Request:
                    </label>
                    <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                      {commonMissingItems.map((item) => {
                        const isChecked = selectedFields.includes(item);
                        return (
                          <label
                            key={item}
                            className={`flex items-center gap-2.5 p-2 rounded-lg border text-xs cursor-pointer transition-colors ${
                              isChecked
                                ? "bg-indigo-50 border-indigo-300 text-indigo-900 font-semibold"
                                : "bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100"
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => toggleFieldSelection(item)}
                              className="rounded text-indigo-600 focus:ring-indigo-600"
                            />
                            <span>{item}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Additional Message (Optional)
                    </label>
                    <textarea
                      rows={3}
                      value={customNote}
                      onChange={(e) => setCustomNote(e.target.value)}
                      placeholder="e.g. Please send the document or complete before 5 PM."
                      className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
                    />
                  </div>

                  <div className="pt-4 border-t border-slate-200 flex items-center justify-end gap-3">
                    <button
                      type="button"
                      onClick={() => setShowRequestModal(false)}
                      className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={sendingRequest || selectedFields.length === 0}
                      className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-lg shadow-sm transition-colors"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>{sendingRequest ? "Sending…" : "Send via WhatsApp"}</span>
                    </button>
                  </div>
                </>
              )}
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
