"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Cpu,
  Play,
  CheckCircle2,
  AlertCircle,
  Clock,
  KeyRound,
  ShieldAlert,
  ArrowRight,
  RefreshCw,
  ExternalLink,
  Edit3,
  XCircle,
  FileCheck,
} from "lucide-react";

import {
  fetchAutomationStatus,
  startAutomation,
  submitOtp,
  continueAutomation,
  cancelAutomation,
  processManually,
} from "@/lib/api";

const AUTOMATION_STEPS = [
  { id: "INIT", label: "Worker Dispatched & Snapshot Loaded" },
  { id: "BROWSER", label: "Headed Chrome Launched" },
  { id: "PORTAL_NAV", label: "Navigate to UDYAM_TARGET_URL" },
  { id: "AADHAAR_PAN", label: "Aadhaar & PAN Verification" },
  { id: "AADHAAR_OTP", label: "Aadhaar OTP Checkpoint (Human Input)" },
  { id: "ORG_DATA", label: "Organization & Enterprise Details" },
  { id: "ADDRESS_UNITS", label: "Official Address & Plant Units" },
  { id: "BANK", label: "Bank Account Validation" },
  { id: "NIC", label: "Activities & 5-Digit NIC Codes" },
  { id: "EMPLOYMENT", label: "Employment & Exclusions" },
  { id: "FINAL_OTP", label: "Final Submission OTP Checkpoint" },
  { id: "REGISTRATION", label: "Registration Completed (Udyam Number)" },
  { id: "CERTIFICATE", label: "Certificate PDF Retrieval" },
];

export default function AutomationTabPage() {
  const params = useParams();
  const applicationId = params?.id as string;

  const [statusData, setStatusData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [actionInProgress, setActionInProgress] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [missingFields, setMissingFields] = useState<string[]>([]);

  // OTP Modal State
  const [otpInput, setOtpInput] = useState("");
  const [submittingOtp, setSubmittingOtp] = useState(false);

  // Manual Processing Modal State
  const [showManualModal, setShowManualModal] = useState(false);
  const [submittingManual, setSubmittingManual] = useState(false);
  const [udyamNumber, setUdyamNumber] = useState("");
  const [manualNotes, setManualNotes] = useState("");

  const loadStatus = async () => {
    try {
      const data = await fetchAutomationStatus(applicationId);
      setStatusData(data);
    } catch (err) {
      console.error("Error fetching automation status:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    const timer = setInterval(() => {
      if (statusData?.is_running) {
        loadStatus();
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [applicationId, statusData?.is_running]);

  async function handleStart() {
    setActionError(null);
    setMissingFields([]);
    setActionInProgress(true);
    try {
      await startAutomation(applicationId);
      loadStatus();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === "object") {
        setActionError(detail.message || "Automation preflight validation failed.");
        setMissingFields(detail.missing_fields || []);
      } else {
        setActionError(detail || "Failed to start automation.");
        setMissingFields([]);
      }
    } finally {
      setActionInProgress(false);
    }
  }

  async function handleSubmitOtp(e: React.FormEvent) {
    e.preventDefault();
    if (!otpInput) return;
    setSubmittingOtp(true);
    try {
      await submitOtp(applicationId, otpInput);
      setOtpInput("");
      loadStatus();
    } catch (err: any) {
      setActionError(err?.response?.data?.detail || "Failed to submit OTP.");
    } finally {
      setSubmittingOtp(false);
    }
  }

  async function handleContinue() {
    setActionInProgress(true);
    try {
      await continueAutomation(applicationId);
      loadStatus();
    } catch (err) {
      console.error(err);
    } finally {
      setActionInProgress(false);
    }
  }

  async function handleCancel() {
    if (!confirm("Are you sure you want to stop the automation worker?")) return;
    setActionInProgress(true);
    try {
      await cancelAutomation(applicationId);
      loadStatus();
    } catch (err) {
      console.error(err);
    } finally {
      setActionInProgress(false);
    }
  }

  async function handleManualSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!udyamNumber) return;
    setSubmittingManual(true);
    try {
      await processManually(applicationId, {
        udyam_registration_number: udyamNumber.trim().toUpperCase(),
        notes: manualNotes,
      });
      setShowManualModal(false);
      loadStatus();
    } catch (err: any) {
      setActionError(err?.response?.data?.detail || "Failed to record manual processing.");
    } finally {
      setSubmittingManual(false);
    }
  }

  if (loading) {
    return <div className="p-12 text-center text-sm text-slate-400">Loading automation workspace…</div>;
  }

  const preflight = statusData?.preflight || {};
  const isRunning = statusData?.is_running;
  const isOtpRequired = statusData?.is_otp_required;
  const isCompleted = statusData?.status === "COMPLETED" || statusData?.status === "CERTIFICATE_READY";

  return (
    <div className="space-y-6">
      {/* Top Banner & Primary Triggers */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold text-slate-900">Government Portal Automation</h2>
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                isRunning
                  ? "bg-indigo-50 text-indigo-800 border-indigo-200"
                  : isCompleted
                  ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                  : isOtpRequired
                  ? "bg-amber-50 text-amber-800 border-amber-200"
                  : "bg-slate-100 text-slate-700 border-slate-200"
              }`}
            >
              {isRunning
                ? "Worker Running in Chrome"
                : isOtpRequired
                ? "Human Action: OTP Required"
                : isCompleted
                ? "Completed"
                : "Eligible for Automation"}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Worker launches a visible headed Chrome browser and navigates to the official target portal.
          </p>
        </div>

        {/* Action Trigger Group */}
        <div className="flex items-center gap-2 flex-wrap">
          {!isRunning && !isCompleted && (
            <>
              <button
                onClick={handleStart}
                disabled={actionInProgress || !preflight.can_start_automation}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-lg shadow-sm transition-colors"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>{actionInProgress ? "Dispatching Worker…" : "Start Automation"}</span>
              </button>

              <button
                onClick={() => setShowManualModal(true)}
                className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                title="Switch to manual portal entry fallback"
              >
                <Edit3 className="w-3.5 h-3.5 text-slate-500" />
                <span>Manual Processing</span>
              </button>
            </>
          )}

          {isRunning && (
            <button
              onClick={handleCancel}
              disabled={actionInProgress}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-rose-700 bg-rose-50 border border-rose-200 hover:bg-rose-100 rounded-lg transition-colors"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Stop Worker</span>
            </button>
          )}
        </div>
      </div>

      {actionError && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs space-y-2">
          <div className="flex items-center gap-2 font-semibold">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span>{actionError}</span>
          </div>
          {missingFields.length > 0 && (
            <div className="pl-6 space-y-1">
              <div className="font-medium text-rose-700">Missing required customer fields:</div>
              <ul className="list-disc list-inside space-y-0.5 text-rose-600">
                {missingFields.map((field, idx) => (
                  <li key={idx}>{field}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* OTP Human Checkpoint Banner */}
      {isOtpRequired && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-5 shadow-sm space-y-3 animate-in fade-in">
          <div className="flex items-center gap-2.5">
            <KeyRound className="w-5 h-5 text-amber-600" />
            <div>
              <h3 className="text-sm font-bold text-amber-900">
                Aadhaar OTP Required from Customer
              </h3>
              <p className="text-xs text-amber-700">
                An OTP has been dispatched to the customer&apos;s Aadhaar-linked mobile. Enter the 6-digit code to resume automation.
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmitOtp} className="flex items-center gap-3 pt-2">
            <input
              type="text"
              required
              maxLength={8}
              value={otpInput}
              onChange={(e) => setOtpInput(e.target.value.replace(/\D/g, ""))}
              placeholder="e.g. 123456"
              className="w-48 px-3 py-2 text-sm font-mono tracking-widest font-bold border border-amber-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-600 bg-white"
            />
            <button
              type="submit"
              disabled={submittingOtp || !otpInput}
              className="px-4 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors"
            >
              {submittingOtp ? "Resuming Worker…" : "Submit OTP & Continue"}
            </button>
          </form>
        </div>
      )}

      {/* 2-Column Automation Layout: Preflight & Worker Timeline */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Preflight Checklist Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="pb-3 border-b border-slate-100">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-slate-500" />
              <span>Preflight Checklist</span>
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Verified criteria before dispatching automation worker.
            </p>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex items-center justify-between p-2 rounded bg-slate-50">
              <span className="text-slate-600">Requirements Form Submitted</span>
              {preflight.requirements_submitted ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              ) : (
                <AlertCircle className="w-4 h-4 text-amber-600" />
              )}
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-slate-50">
              <span className="text-slate-600">Owner & PAN Details Valid</span>
              {preflight.owner_pan_valid ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              ) : (
                <AlertCircle className="w-4 h-4 text-amber-600" />
              )}
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-slate-50">
              <span className="text-slate-600">Bank Details Complete</span>
              {preflight.bank_details_valid ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              ) : (
                <AlertCircle className="w-4 h-4 text-amber-600" />
              )}
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-slate-50">
              <span className="text-slate-600">Activities & NIC Codes Complete</span>
              {preflight.activity_nic_valid ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              ) : (
                <AlertCircle className="w-4 h-4 text-amber-600" />
              )}
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-slate-50">
              <span className="text-slate-600">Official Address Complete</span>
              {preflight.address_valid ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              ) : (
                <AlertCircle className="w-4 h-4 text-amber-600" />
              )}
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-slate-50">
              <span className="text-slate-600">Accounting Payment Verified</span>
              {preflight.payment_completed ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-600" />
              )}
            </div>
          </div>
        </div>

        {/* Live Step Progression Timeline */}
        <div className="md:col-span-2 bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <Cpu className="w-4 h-4 text-slate-500" />
                <span>Worker Execution Progression</span>
              </h3>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Target URL: {statusData?.target_url || "https://msme-form.vercel.app/udyam"} (Headed Mode)
              </p>
            </div>
            {isRunning && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-indigo-50 text-indigo-700 text-xs font-semibold animate-pulse">
                <RefreshCw className="w-3 h-3 animate-spin" />
                <span>Running</span>
              </span>
            )}
          </div>

          <div className="space-y-2">
            {AUTOMATION_STEPS.map((step, idx) => {
              const isCompletedStep = isCompleted;
              const isCurrent = isRunning && idx === 4; // demo current

              return (
                <div
                  key={step.id}
                  className={`flex items-center justify-between p-2.5 rounded-lg border text-xs transition-colors ${
                    isCompletedStep
                      ? "bg-emerald-50/50 border-emerald-200 text-emerald-900 font-medium"
                      : isCurrent
                      ? "bg-indigo-50 border-indigo-300 text-indigo-900 font-bold shadow-xs"
                      : "bg-slate-50/50 border-slate-100 text-slate-500"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold bg-white border border-slate-300 text-slate-600">
                      {idx + 1}
                    </span>
                    <span>{step.label}</span>
                  </div>

                  <div>
                    {isCompletedStep ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    ) : isCurrent ? (
                      <span className="px-2 py-0.5 rounded bg-indigo-600 text-white text-[10px] font-bold">
                        ACTIVE
                      </span>
                    ) : (
                      <span className="text-[10px] text-slate-400">PENDING</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Manual Processing Fallback Modal */}
      {showManualModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">Manual Registration Entry</h3>
                <p className="text-xs text-slate-500">Record registration completed directly on portal.</p>
              </div>
              <button
                onClick={() => setShowManualModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleManualSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Udyam Registration Number *
                </label>
                <input
                  type="text"
                  required
                  value={udyamNumber}
                  onChange={(e) => setUdyamNumber(e.target.value.toUpperCase())}
                  placeholder="e.g. UDYAM-DL-01-0012345"
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg uppercase font-mono focus:outline-none focus:ring-2 focus:ring-indigo-600"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Processing Notes
                </label>
                <textarea
                  rows={3}
                  value={manualNotes}
                  onChange={(e) => setManualNotes(e.target.value)}
                  placeholder="Completed manually via portal due to OTP or special verification."
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
                />
              </div>

              <div className="pt-4 border-t border-slate-200 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowManualModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingManual || !udyamNumber}
                  className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-lg shadow-sm transition-colors"
                >
                  {submittingManual ? "Saving Record…" : "Save & Complete Case"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
