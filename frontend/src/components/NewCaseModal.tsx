"use client";

import React, { useState } from "react";
import { X, Building2, FileCheck2, ArrowRight, Loader2 } from "lucide-react";
import { useCreateApplication } from "@/lib/api-client";

interface NewCaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (createdApp: any) => void;
  defaultBranchId?: string;
}

const ORG_TYPES = [
  { id: "Proprietorship", name: "Proprietorship", desc: "Single owner business enterprise" },
  { id: "Partnership", name: "Partnership Firm", desc: "Registered partnership deed firm" },
  { id: "LLP", name: "Limited Liability Partnership (LLP)", desc: "MCA registered LLP firm" },
  { id: "Private Limited", name: "Private Limited Company", desc: "Incorporated Pvt Ltd company" },
  { id: "OPC", name: "One Person Company (OPC)", desc: "Single member incorporated OPC" },
];

export const NewCaseModal: React.FC<NewCaseModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  defaultBranchId,
}) => {
  const createMutation = useCreateApplication();

  const [businessName, setBusinessName] = useState("");
  const [applicantName, setApplicantName] = useState("");
  const [panNumber, setPanNumber] = useState("");
  const [mobileNumber, setMobileNumber] = useState("");
  const [aadhaarNumber, setAadhaarNumber] = useState("");
  const [selectedOrg, setSelectedOrg] = useState("Proprietorship");
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Basic client validation
    if (!businessName.trim() || !applicantName.trim()) {
      setError("Please provide both Business Name and Applicant Name.");
      return;
    }
    const cleanPan = panNumber.trim().toUpperCase();
    if (!cleanPan || cleanPan.length !== 10) {
      setError("Please enter a valid 10-character PAN number.");
      return;
    }
    const cleanMobile = mobileNumber.replace(/\D/g, "").slice(-10);
    if (cleanMobile.length !== 10) {
      setError("Please enter a valid 10-digit mobile number.");
      return;
    }
    const cleanAadhaar = aadhaarNumber.replace(/\D/g, "").slice(-12);
    if (cleanAadhaar.length !== 12) {
      setError("Please enter a valid 12-digit Aadhaar number.");
      return;
    }

    try {
      // Get branch ID from token or storage or default
      let branchId = defaultBranchId;
      if (!branchId) {
        // Fallback to active session user or known branch
        try {
          const authData = localStorage.getItem("taxla_user");
          if (authData) {
            const parsed = JSON.parse(authData);
            branchId = parsed.branch_id;
          }
        } catch {
          // ignore
        }
      }

      if (!branchId) {
        // Fetch from /api/v1/applications to get any active branch id
        const { apiClient } = await import("@/api/workflow");
        const res = await apiClient.get("/applications");
        if (res.data && res.data.length > 0) {
          branchId = res.data[0].branch_id;
        }
      }

      if (!branchId) {
        branchId = "1dabedf1-50c3-4b43-84b8-dd54b71509f9";
      }

      const created = await createMutation.mutateAsync({
        branch_id: branchId,
        business_name: businessName.trim(),
        applicant_name: applicantName.trim(),
        pan_number: cleanPan,
        mobile_number: cleanMobile,
        aadhaar_number: cleanAadhaar,
        gender: "Male",
        social_category: "General",
        divyang_status: false,
        workflow_type: "NEW_UDYAM",
      });

      if (onSuccess) {
        onSuccess(created);
      }
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Failed to create application");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="glass-panel w-full max-w-lg p-6 relative border border-slate-700 bg-slate-950/95 shadow-2xl rounded-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Building2 className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Create New Intake Case</h3>
            <p className="text-xs text-slate-400">Taxla Udyam MSME Registration Workflow</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Workflow Type (DR-002)
            </label>
            <div className="flex items-center space-x-2 p-2.5 rounded-xl bg-indigo-950/30 border border-indigo-500/30 text-indigo-300 font-medium">
              <FileCheck2 className="w-4 h-4 text-indigo-400" />
              <span>Udyam New Registration</span>
              <span className="ml-auto text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold">
                ACTIVE
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Enterprise Name *
              </label>
              <input
                type="text"
                required
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="e.g. Acme Tech Solutions"
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Applicant / Owner Name *
              </label>
              <input
                type="text"
                required
                value={applicantName}
                onChange={(e) => setApplicantName(e.target.value)}
                placeholder="e.g. Rajesh Sharma"
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1">
                PAN Number *
              </label>
              <input
                type="text"
                required
                maxLength={10}
                value={panNumber}
                onChange={(e) => setPanNumber(e.target.value.toUpperCase())}
                placeholder="ABCDE1234F"
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Mobile Number *
              </label>
              <input
                type="text"
                required
                maxLength={10}
                value={mobileNumber}
                onChange={(e) => setMobileNumber(e.target.value)}
                placeholder="9876543210"
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Aadhaar Number *
              </label>
              <input
                type="text"
                required
                maxLength={12}
                value={aadhaarNumber}
                onChange={(e) => setAadhaarNumber(e.target.value)}
                placeholder="123456789012"
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Organisation Type (DR-003)
            </label>
            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
              {ORG_TYPES.map((org) => (
                <div
                  key={org.id}
                  onClick={() => setSelectedOrg(org.id)}
                  className={`p-2.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                    selectedOrg === org.id
                      ? "bg-indigo-600/20 border-indigo-500 shadow-md shadow-indigo-500/10"
                      : "bg-slate-900/50 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div>
                    <div className="font-semibold text-white">{org.name}</div>
                    <div className="text-[10px] text-slate-400">{org.desc}</div>
                  </div>
                  <div
                    className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                      selectedOrg === org.id ? "border-indigo-400 bg-indigo-500" : "border-slate-600"
                    }`}
                  >
                    {selectedOrg === org.id && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-3 flex items-center justify-end space-x-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold flex items-center space-x-2 transition-all shadow-lg shadow-indigo-600/30 disabled:opacity-50"
            >
              {createMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <span>Initialize Case</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
