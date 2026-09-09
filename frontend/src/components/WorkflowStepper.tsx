"use client";

import React from "react";
import { Check, AlertCircle } from "lucide-react";

export type TaxlaStage =
  | "form_sent"
  | "form_submitted"
  | "review"
  | "payment"
  | "ready"
  | "processing"
  | "registration"
  | "certificate"
  | "completed";

const STAGES: { id: TaxlaStage; label: string }[] = [
  { id: "form_sent", label: "Form Sent" },
  { id: "form_submitted", label: "Form Submitted" },
  { id: "review", label: "Review" },
  { id: "payment", label: "Payment" },
  { id: "ready", label: "Ready" },
  { id: "processing", label: "Automation / Manual" },
  { id: "registration", label: "Registration" },
  { id: "certificate", label: "Certificate" },
  { id: "completed", label: "Completed" },
];

export function getStageFromStatus(status?: string): TaxlaStage {
  const s = status?.toUpperCase() ?? "NEW";

  if (s === "NEW" || s === "FORM_SENT") return "form_sent";
  if (s === "FORM_SUBMITTED" || s === "DOCUMENTS_UPLOADED" || s === "EXTRACTED") return "form_submitted";
  if (s === "REVIEW_REQUIRED" || s === "VALIDATION_REVIEW" || s === "NIC_REVIEW" || s === "HUMAN_REVIEW") return "review";
  if (s === "READY_FOR_PAYMENT") return "payment";
  if (s === "PAYMENT_COMPLETED" || s === "READY_FOR_AUTOMATION" || s === "READY_FOR_PORTAL") return "ready";
  if (s === "AUTOMATION_RUNNING" || s === "PORTAL_RUNNING" || s === "OTP_REQUIRED" || s === "AADHAAR_OTP" || s === "MANUAL_PROCESSING") return "processing";
  if (s === "FINAL_SUBMISSION" || s === "REGISTRATION_COMPLETED" || s === "REGISTERED") return "registration";
  if (s === "CERTIFICATE_RETRIEVED" || s === "CERTIFICATE_READY" || s === "CLIENT_NOTIFIED") return "certificate";
  if (s === "COMPLETED") return "completed";

  return "form_sent";
}

export function WorkflowStepper({
  status,
  className = "",
}: {
  status?: string;
  className?: string;
}) {
  const isFailed = status?.toUpperCase().includes("FAIL") || status?.toUpperCase() === "EXCEPTION";
  const currentStage = getStageFromStatus(status);
  const currentIndex = STAGES.findIndex((s) => s.id === currentStage);

  return (
    <div className={`w-full overflow-x-auto py-2 ${className}`}>
      <ol className="flex items-center min-w-[760px] justify-between">
        {STAGES.map((stage, idx) => {
          const isDone = currentIndex > idx;
          const isCurrent = currentIndex === idx;

          return (
            <li key={stage.id} className="relative flex-1 flex flex-col items-center">
              {/* Connector line */}
              {idx < STAGES.length - 1 && (
                <div
                  className={`absolute top-3 left-1/2 w-full h-0.5 -z-0 transition-colors ${
                    currentIndex > idx ? "bg-indigo-600" : "bg-slate-200"
                  }`}
                />
              )}

              {/* Step indicator node */}
              <div
                className={`relative z-10 flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold transition-all ${
                  isDone
                    ? "bg-indigo-600 text-white shadow-sm"
                    : isCurrent
                    ? isFailed
                      ? "bg-rose-600 text-white ring-4 ring-rose-100"
                      : "bg-white text-indigo-600 border-2 border-indigo-600 ring-4 ring-indigo-50"
                    : "bg-white text-slate-400 border border-slate-300"
                }`}
              >
                {isDone ? (
                  <Check className="w-3.5 h-3.5 stroke-[3]" />
                ) : (
                  <span>{idx + 1}</span>
                )}
              </div>

              {/* Step Label */}
              <span
                className={`mt-1.5 text-[11px] font-medium text-center truncate max-w-[85px] ${
                  isCurrent
                    ? "text-indigo-900 font-bold"
                    : isDone
                    ? "text-slate-700"
                    : "text-slate-400"
                }`}
                title={stage.label}
              >
                {stage.label}
              </span>
            </li>
          );
        })}
      </ol>

      {isFailed && (
        <div className="mt-3 flex items-center gap-1.5 px-3 py-1.5 bg-rose-50 border border-rose-200 rounded text-rose-700 text-xs font-medium">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>Workflow paused due to failure. Review details and retry.</span>
        </div>
      )}
    </div>
  );
}