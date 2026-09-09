"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  CreditCard,
  CheckCircle2,
  AlertCircle,
  Receipt,
  ArrowRight,
  ShieldCheck,
  Building,
} from "lucide-react";

import { fetchPayments, markPaymentReceived } from "@/lib/api";

export default function PaymentTabPage() {
  const params = useParams();
  const applicationId = params?.id as string;

  const [paymentData, setPaymentData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Mark Payment Modal State
  const [showModal, setShowModal] = useState(false);
  const [amount, setAmount] = useState("1500.00");
  const [paymentMethod, setPaymentMethod] = useState("UPI / Bank Transfer");
  const [reference, setReference] = useState("MANUAL-CONFIRMED");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function loadPayments() {
    try {
      const data = await fetchPayments(applicationId);
      setPaymentData(data);
    } catch (err) {
      console.error("Failed to load payment details:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!applicationId) return;
    loadPayments();
  }, [applicationId]);

  async function handleConfirmPayment(e: React.FormEvent) {
    e.preventDefault();
    setErrorMessage(null);
    setSubmitting(true);
    try {
      await markPaymentReceived(applicationId, {
        amount: parseFloat(amount) || 1500.0,
        currency: "INR",
        payment_method: paymentMethod,
        reference: reference.trim() || "MANUAL-CONFIRMED",
      });
      setShowModal(false);
      loadPayments();
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || "Failed to confirm payment.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="p-12 text-center text-sm text-slate-400">Loading payment details…</div>;
  }

  const isPaid = paymentData?.status === "PAID";
  const history = paymentData?.history || [];

  return (
    <div className="space-y-6">
      {/* Top Banner & Main Action */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold text-slate-900">Payment & Invoicing</h2>
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                isPaid
                  ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                  : "bg-amber-50 text-amber-800 border-amber-200"
              }`}
            >
              {isPaid ? "Payment Verified & Completed" : "Payment Pending"}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Manual accounting verification before proceeding to government portal automation.
          </p>
        </div>

        {!isPaid ? (
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition-colors"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Mark Payment Received</span>
          </button>
        ) : (
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg text-xs font-semibold">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Payment Verified</span>
          </div>
        )}
      </div>

      {/* Payment Information Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
        <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
          <Receipt className="w-4 h-4 text-slate-500" />
          <span>Billing Summary</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Service Registration Fee</span>
            <div className="text-base font-bold text-slate-900 mt-0.5">₹1,500.00</div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Current Status</span>
            <div className={`text-base font-bold mt-0.5 ${isPaid ? "text-emerald-700" : "text-amber-700"}`}>
              {isPaid ? "PAID" : "PENDING"}
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Payment Channel</span>
            <div className="text-base font-bold text-slate-900 mt-0.5">
              {history[0]?.payment_method || "UPI / Bank Transfer"}
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Transaction Reference</span>
            <div className="text-base font-bold text-slate-900 mt-0.5 truncate">
              {history[0]?.reference || "REF-PENDING"}
            </div>
          </div>
        </div>
      </div>

      {/* Transaction History Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 bg-slate-50/50">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Payment Audit History
          </h3>
        </div>

        {history.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            No payments recorded yet. Click &quot;Mark Payment Received&quot; when customer completes transfer.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="ops-table-header">
                  <th className="px-5 py-3">Transaction ID</th>
                  <th className="px-5 py-3">Amount</th>
                  <th className="px-5 py-3">Channel</th>
                  <th className="px-5 py-3">Reference</th>
                  <th className="px-5 py-3">Confirmed By</th>
                  <th className="px-5 py-3 text-right">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {history.map((h: any) => (
                  <tr key={h.id} className="ops-table-row">
                    <td className="px-5 py-3.5 font-semibold text-slate-900 text-xs">
                      {h.id}
                    </td>
                    <td className="px-5 py-3.5 text-xs font-bold text-emerald-700">
                      ₹{h.amount?.toFixed(2) || "1,500.00"}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-600">
                      {h.payment_method}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-700 font-mono">
                      {h.reference}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-600">
                      {h.confirmed_by_name || "Operator"}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-500 text-right">
                      {h.confirmed_at ? new Date(h.confirmed_at).toLocaleString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">Confirm Payment Received</h3>
                <p className="text-xs text-slate-500">Record customer payment and mark case eligible for automation.</p>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleConfirmPayment} className="p-6 space-y-4">
              {errorMessage && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded text-rose-700 text-xs">
                  {errorMessage}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Amount Received (INR) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-600"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Payment Method *
                </label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-600 bg-white"
                >
                  <option value="UPI / QR Code">UPI / QR Code Transfer</option>
                  <option value="IMPS / NEFT Bank Transfer">IMPS / NEFT Bank Transfer</option>
                  <option value="Debit / Credit Card">Debit / Credit Card</option>
                  <option value="Cash Deposit">Direct Cash Deposit</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  UTR / Reference Number *
                </label>
                <input
                  type="text"
                  required
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="e.g. UTR-982347102938"
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-600"
                />
              </div>

              <div className="pt-4 border-t border-slate-200 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-lg shadow-sm transition-colors"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>{submitting ? "Confirming…" : "Confirm Payment (PAID)"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
