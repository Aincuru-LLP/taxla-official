"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Building2,
  ShieldCheck,
  CreditCard,
  Briefcase,
  MapPin,
  Save,
  Users,
  Check,
  Plus,
  Trash2,
  AlertCircle,
  Building,
  FileText,
  Info,
} from "lucide-react";

import { fetchPublicForm, savePublicFormDraft, submitPublicForm } from "@/lib/api";
import { INDIAN_STATES_LIST, getDistrictsForState } from "@/lib/indiaGeography";
import { getNic2Digits, getNic4Digits, getNic5Digits } from "@/lib/nicData";

const STEPS = [
  { id: 1, label: "Owner", icon: ShieldCheck },
  { id: 2, label: "PAN & Org", icon: CreditCard },
  { id: 3, label: "Business & Financial", icon: Briefcase },
  { id: 4, label: "Official Address", icon: MapPin },
  { id: 5, label: "Bank & Units", icon: Building2 },
  { id: 6, label: "Activity & NIC", icon: FileText },
  { id: 7, label: "Employment", icon: Users },
  { id: 8, label: "Review & Submit", icon: CheckCircle2 },
];

export default function CustomerIntakeFormPage() {
  const params = useParams();
  const applicationCode = params?.applicationCode as string;
  const token = params?.token as string;

  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form State
  const [form, setForm] = useState<any>({
    // Step 1: Owner Identification
    aadhaar_number: "",
    aadhaar_name: "",
    aadhaar_consent: true,

    // Step 2: PAN & Organization Details
    organization_type: "Proprietorship",
    pan_number: "",
    pan_name: "",
    date_of_birth: "",
    social_category: "General",
    gender: "Male",
    specially_abled: false,
    pan_consent: true,
    itr_status: "No",
    itr_form_type: "",

    // Step 3: Business, Contact & Financial Profile
    mobile_number: "",
    email: "",
    enterprise_name: "",
    financial_year: "2024-25",
    written_down_value: 0,
    pollution_control_exclusion: 0,
    total_turnover: 0,
    export_turnover: 0,
    gst_status: "No",
    gstin: "",

    // Step 4: Official Office Address
    flat_door_block: "",
    premises_building: "",
    village_town: "",
    block: "",
    road_street: "",
    city: "",
    state: "TAMIL NADU",
    district: "CHENNAI",
    pin: "",
    official_mobile: "",
    official_email: "",
    latitude: "",
    longitude: "",

    // Step 5: Bank Details & Plant/Unit Locations
    bank_name: "",
    bank_ifsc: "",
    bank_account_number: "",
    confirm_bank_account_number: "",
    account_holder_name: "",
    has_plant_units: false,
    units: [],

    // Step 6: Major Activity & Products (NIC)
    major_activity: "Services",
    business_activity_description: "",
    activities: [],

    // Step 7: Employment & Statutory Registrations
    male_employees: 0,
    female_employees: 0,
    other_employees: 0,
    interested_in_gem: false,
    interested_in_treds: false,
    interested_in_ncs: false,
    interested_in_nsic_b2b: false,
    interested_in_skill_india: false,
    district_industries_centre: "",
    msme_dfo: "",

    // Step 8: Declarations
    declaration_agreed: false,
  });

  // Temporary NIC selection state for Step 6
  const [selectedNic2, setSelectedNic2] = useState("");
  const [selectedNic4, setSelectedNic4] = useState("");
  const [selectedNic5, setSelectedNic5] = useState("");

  // Auto-calculated values
  const netInvestment = useMemo(() => {
    const wdv = parseFloat(form.written_down_value) || 0;
    const exc = parseFloat(form.pollution_control_exclusion) || 0;
    return Math.max(0, wdv - exc);
  }, [form.written_down_value, form.pollution_control_exclusion]);

  const netTurnover = useMemo(() => {
    const tot = parseFloat(form.total_turnover) || 0;
    const exp = parseFloat(form.export_turnover) || 0;
    return Math.max(0, tot - exp);
  }, [form.total_turnover, form.export_turnover]);

  const msmeCategory = useMemo(() => {
    if (netInvestment <= 25000000 && netTurnover <= 100000000) return "Micro";
    if (netInvestment <= 250000000 && netTurnover <= 1000000000) return "Small";
    if (netInvestment <= 1250000000 && netTurnover <= 5000000000) return "Medium";
    return "Large";
  }, [netInvestment, netTurnover]);

  const totalEmployees = useMemo(() => {
    return (
      (parseInt(form.male_employees, 10) || 0) +
      (parseInt(form.female_employees, 10) || 0) +
      (parseInt(form.other_employees, 10) || 0)
    );
  }, [form.male_employees, form.female_employees, form.other_employees]);

  // Load intake data from server
  useEffect(() => {
    if (!applicationCode || !token) return;
    fetchPublicForm(applicationCode, token)
      .then((data) => {
        if (data?.form_data) {
          const sanitized: any = {};
          for (const [k, v] of Object.entries(data.form_data)) {
            sanitized[k] = v === null || v === undefined ? "" : v;
          }
          setForm((prev: any) => ({
            ...prev,
            ...sanitized,
            // Pre-fill official contact if blank
            official_mobile: sanitized.official_mobile || sanitized.mobile_number || prev.official_mobile,
            official_email: sanitized.official_email || sanitized.email || prev.official_email,
            // Ensure boolean states
            aadhaar_consent: sanitized.aadhaar_consent !== undefined ? sanitized.aadhaar_consent : true,
            pan_consent: sanitized.pan_consent !== undefined ? sanitized.pan_consent : true,
            confirm_bank_account_number: sanitized.bank_account_number || prev.confirm_bank_account_number,
          }));
        }
        if (data?.application_status === "FORM_SUBMITTED" || data?.application_status === "COMPLETED") {
          setSubmitted(true);
        }
      })
      .catch((err) => console.error("Error loading intake form:", err))
      .finally(() => setLoading(false));
  }, [applicationCode, token]);

  async function handleAutoSave(overrideForm?: any) {
    const dataToSave = overrideForm || form;
    setSaving(true);
    try {
      await savePublicFormDraft(applicationCode, token, {
        ...dataToSave,
        net_investment: netInvestment,
        net_domestic_turnover: netTurnover,
        enterprise_classification: msmeCategory,
        total_employees: totalEmployees,
      });
    } catch (err) {
      console.error("Draft save error:", err);
    } finally {
      setTimeout(() => setSaving(false), 600);
    }
  }

  // Step Validation & Navigation
  function handleNext() {
    setErrorMessage(null);

    // STEP 1 VALIDATION
    if (currentStep === 1) {
      if (!form.aadhaar_name?.trim()) {
        setErrorMessage("Please enter the Applicant Full Name as per Aadhaar.");
        return;
      }
      const aadhaarDigits = form.aadhaar_number?.replace(/\D/g, "") || "";
      if (aadhaarDigits.length !== 12) {
        setErrorMessage("Aadhaar Number must be exactly 12 numeric digits.");
        return;
      }
      if (!form.aadhaar_consent) {
        setErrorMessage("Please provide consent to proceed with Aadhaar-based registration.");
        return;
      }
    }

    // STEP 2 VALIDATION
    else if (currentStep === 2) {
      const pan = form.pan_number?.trim().toUpperCase() || "";
      if (!/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(pan)) {
        setErrorMessage("Please enter a valid 10-character PAN (e.g. ABCDE1234F).");
        return;
      }
      if (!form.pan_name?.trim()) {
        setErrorMessage("Please enter Name as printed on PAN Card.");
        return;
      }
      if (!form.pan_consent) {
        setErrorMessage("Please authorize PAN details verification.");
        return;
      }
      if (form.itr_status === "Yes" && !form.itr_form_type) {
        setErrorMessage("Please select your filed ITR Form Type.");
        return;
      }
    }

    // STEP 3 VALIDATION
    else if (currentStep === 3) {
      const mob = form.mobile_number?.replace(/\D/g, "") || "";
      if (mob.length !== 10) {
        setErrorMessage("Please enter a valid 10-digit primary mobile number.");
        return;
      }
      if (!form.email?.trim() || !form.email.includes("@")) {
        setErrorMessage("Please enter a valid email address.");
        return;
      }
      if (!form.enterprise_name?.trim()) {
        setErrorMessage("Please enter Enterprise / Business Trade Name.");
        return;
      }
      const totTurnover = parseFloat(form.total_turnover) || 0;
      const expTurnover = parseFloat(form.export_turnover) || 0;
      if (expTurnover > totTurnover) {
        setErrorMessage("Export turnover cannot exceed Total Annual Turnover.");
        return;
      }
      if (form.gst_status === "Yes") {
        const cleanGst = form.gstin?.trim().toUpperCase() || "";
        if (cleanGst.length !== 15) {
          setErrorMessage("Please provide a valid 15-character GSTIN number.");
          return;
        }
      }
    }

    // STEP 4 VALIDATION
    else if (currentStep === 4) {
      if (!form.city?.trim() || !form.state || !form.district) {
        setErrorMessage("Please specify complete City, State, and District.");
        return;
      }
      const pinClean = form.pin?.replace(/\D/g, "") || "";
      if (pinClean.length !== 6) {
        setErrorMessage("PIN Code must be exactly 6 digits.");
        return;
      }
    }

    // STEP 5 VALIDATION
    else if (currentStep === 5) {
      if (!form.bank_name?.trim()) {
        setErrorMessage("Please provide Bank Name.");
        return;
      }
      const ifsc = form.bank_ifsc?.trim().toUpperCase() || "";
      if (ifsc.length !== 11) {
        setErrorMessage("Bank IFSC must be exactly 11 characters (e.g. SBIN0001234).");
        return;
      }
      if (!form.bank_account_number?.trim()) {
        setErrorMessage("Please provide Bank Account Number.");
        return;
      }
      if (form.bank_account_number !== form.confirm_bank_account_number) {
        setErrorMessage("Bank Account Numbers do not match. Please re-confirm.");
        return;
      }
    }

    // STEP 6 VALIDATION
    else if (currentStep === 6) {
      if (!form.major_activity) {
        setErrorMessage("Please select major activity (Services / Manufacturing / Trading).");
        return;
      }
      if (!form.business_activity_description?.trim()) {
        setErrorMessage("Please provide a brief description of your business operations.");
        return;
      }
    }

    // STEP 7 VALIDATION
    else if (currentStep === 7) {
      if (totalEmployees < 0) {
        setErrorMessage("Employee counts cannot be negative.");
        return;
      }
    }

    handleAutoSave();
    setCurrentStep((s) => Math.min(STEPS.length, s + 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handlePrev() {
    setErrorMessage(null);
    setCurrentStep((s) => Math.max(1, s - 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMessage(null);

    if (!form.declaration_agreed) {
      setErrorMessage("Please accept the statutory declaration before submitting.");
      return;
    }

    const aadhaarDigits = form.aadhaar_number?.replace(/\D/g, "") || "";
    if (aadhaarDigits.length !== 12) {
      setErrorMessage("Please provide a valid 12-digit Aadhaar number before submitting.");
      return;
    }

    const pan = form.pan_number?.trim().toUpperCase() || "";
    if (!/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(pan)) {
      setErrorMessage("Please provide a valid 10-character PAN (e.g. ABCDE1234F).");
      return;
    }

    setSubmitting(true);
    try {
      await submitPublicForm(applicationCode, token, {
        ...form,
        net_investment: netInvestment,
        net_domestic_turnover: netTurnover,
        enterprise_classification: msmeCategory,
        total_employees: totalEmployees,
      });
      setSubmitted(true);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === "object" && detail?.message) {
        setErrorMessage(detail.message + (detail.missing_fields ? ` (${detail.missing_fields.join(", ")})` : ""));
      } else {
        setErrorMessage(detail || "Submission failed. Please check required fields.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  // Plant / Unit Management Handlers
  function handleAddUnit() {
    const newUnit = {
      unit_name: `${form.enterprise_name || "Plant"} Unit ${form.units.length + 1}`,
      flat: "",
      building: "",
      village_town: "",
      block: "",
      road_street: "",
      city: form.city || "",
      state: form.state || "TAMIL NADU",
      district: form.district || "CHENNAI",
      pin: form.pin || "",
    };
    setForm({
      ...form,
      units: [...form.units, newUnit],
    });
  }

  function handleRemoveUnit(idx: number) {
    setForm({
      ...form,
      units: form.units.filter((_: any, i: number) => i !== idx),
    });
  }

  function handleUnitChange(idx: number, field: string, value: any) {
    const updated = [...form.units];
    updated[idx] = { ...updated[idx], [field]: value };
    // If state changes, reset district
    if (field === "state") {
      const districts = getDistrictsForState(value);
      updated[idx].district = districts[0] || "";
    }
    setForm({ ...form, units: updated });
  }

  // NIC Activity Management Handlers
  function handleAddNicActivity() {
    if (!selectedNic5) {
      setErrorMessage("Please select a 5-digit NIC code before adding.");
      return;
    }
    const newAct = {
      activity_type: form.major_activity,
      nic_2digit: selectedNic2,
      nic_4digit: selectedNic4,
      nic_5digit: selectedNic5,
      description: form.business_activity_description || "",
    };
    setForm({
      ...form,
      activities: [...form.activities, newAct],
    });
    setSelectedNic5("");
    setErrorMessage(null);
  }

  function handleRemoveNicActivity(idx: number) {
    setForm({
      ...form,
      activities: form.activities.filter((_: any, i: number) => i !== idx),
    });
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="text-slate-600 text-sm font-medium flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          Loading Udyam requirement intake form…
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white border border-slate-200 rounded-3xl p-8 text-center shadow-lg space-y-5">
          <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-inner">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <div className="space-y-1">
            <h1 className="text-xl font-bold text-slate-900">Requirements Received!</h1>
            <p className="text-xs text-slate-500 font-mono tracking-wide">{applicationCode}</p>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Thank you! Your verified business details have been securely recorded. Our compliance specialists will review your submission and initiate official registration on the MSME portal.
          </p>
          <div className="p-4 bg-slate-50 rounded-2xl text-xs text-slate-600 text-left space-y-2 border border-slate-100">
            <div className="font-semibold text-slate-900 flex items-center gap-1.5">
              <Info className="w-4 h-4 text-indigo-600" />
              What to expect next:
            </div>
            <p>&bull; TAXLA operations team prepares your verified file.</p>
            <p>&bull; When the portal generates your Aadhaar OTP, we will alert you immediately on WhatsApp for confirmation.</p>
            <p>&bull; Your official Udyam Certificate will be delivered directly to your email and WhatsApp upon completion.</p>
          </div>
          <div className="pt-2">
            <button
              onClick={() => setSubmitted(false)}
              className="inline-flex items-center gap-1.5 px-5 py-2.5 text-xs font-semibold text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-xl transition-colors"
            >
              Review or Update Submitted Information
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between selection:bg-indigo-500 selection:text-white">
      {/* Sticky Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white font-black text-xs flex items-center justify-center shadow-sm">
              TX
            </div>
            <div>
              <div className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                TAXLA Udyam Intake
                <span className="text-[10px] bg-indigo-50 text-indigo-700 font-semibold px-2 py-0.5 rounded-full">
                  Official 8-Step Form
                </span>
              </div>
              <div className="text-[10px] text-slate-500 font-mono">{applicationCode}</div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {saving ? (
              <span className="text-[11px] text-indigo-600 font-medium flex items-center gap-1 animate-pulse">
                <Save className="w-3 h-3" /> Saving draft…
              </span>
            ) : (
              <span className="text-[11px] text-slate-400">All changes saved</span>
            )}
            <div className="text-xs font-bold text-slate-700 bg-slate-100 px-2.5 py-1 rounded-lg">
              Step {currentStep} of {STEPS.length}
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-slate-100 h-1">
          <div
            className="bg-indigo-600 h-1 transition-all duration-300 ease-out"
            style={{ width: `${(currentStep / STEPS.length) * 100}%` }}
          />
        </div>
      </header>

      {/* Main Form Body */}
      <main className="flex-1 max-w-3xl w-full mx-auto p-4 sm:py-8">
        <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-xs">
          {/* Error notification */}
          {errorMessage && (
            <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-700 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-rose-600" />
              <div className="leading-relaxed">{errorMessage}</div>
            </div>
          )}

          {/* ================= STEP 1: OWNER IDENTIFICATION ================= */}
          {currentStep === 1 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 1: Owner Identification</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Enter applicant identity details exactly as printed on the official Aadhaar card.
                </p>
              </div>

              <div className="space-y-4 pt-1">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Applicant / Owner Full Name (as per Aadhaar) *
                  </label>
                  <input
                    type="text"
                    required
                    value={form.aadhaar_name ?? ""}
                    onChange={(e) => setForm({ ...form, aadhaar_name: e.target.value })}
                    placeholder="e.g. C KANAKARAJ"
                    className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600 transition"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">Must match the legal spelling on your Aadhaar card.</p>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    12-Digit Aadhaar Number *
                  </label>
                  <input
                    type="text"
                    required
                    maxLength={12}
                    value={form.aadhaar_number ?? ""}
                    onChange={(e) => setForm({ ...form, aadhaar_number: e.target.value.replace(/\D/g, "") })}
                    placeholder="361105197807"
                    className="w-full px-3.5 py-2.5 text-sm font-mono tracking-widest border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600 transition"
                  />
                </div>

                <div className="p-4 bg-indigo-50/70 border border-indigo-100 rounded-2xl text-xs text-indigo-900 space-y-1.5">
                  <div className="font-semibold flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-indigo-600" />
                    Security & Aadhaar OTP Information
                  </div>
                  <p className="text-indigo-800 text-[11px] leading-relaxed">
                    Aadhaar OTP is <strong>never collected on this form</strong>. During official government filing, an OTP will be dispatched to your Aadhaar-linked mobile. Our team will coordinate with you via WhatsApp to submit the OTP securely at that moment.
                  </p>
                </div>

                <div className="pt-2">
                  <label className="flex items-start gap-2.5 text-xs text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.aadhaar_consent}
                      onChange={(e) => setForm({ ...form, aadhaar_consent: e.target.checked })}
                      className="rounded text-indigo-600 focus:ring-indigo-600 mt-0.5 w-4 h-4"
                    />
                    <span className="leading-relaxed">
                      I authorize TAXLA to use my Aadhaar details for processing my Udyam MSME Registration on the official Ministry of MSME portal. *
                    </span>
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* ================= STEP 2: PAN & ORGANIZATION DETAILS ================= */}
          {currentStep === 2 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 2: PAN & Organization Details</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Specify enterprise constitution and tax identity information.
                </p>
              </div>

              <div className="space-y-4 pt-1">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Type of Organization *
                  </label>
                  <select
                    value={form.organization_type ?? "Proprietorship"}
                    onChange={(e) => setForm({ ...form, organization_type: e.target.value })}
                    className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600 bg-white"
                  >
                    <option value="Proprietorship">Proprietorship / Individual</option>
                    <option value="Partnership">Partnership Firm</option>
                    <option value="Hindu Undivided Family">Hindu Undivided Family (HUF)</option>
                    <option value="Private Limited Company">Private Limited Company</option>
                    <option value="Public Limited Company">Public Limited Company</option>
                    <option value="Limited Liability Partnership">Limited Liability Partnership (LLP)</option>
                    <option value="Cooperative Society">Cooperative Society</option>
                    <option value="Society">Society</option>
                    <option value="Trust">Trust</option>
                    <option value="Self Help Group">Self Help Group (SHG)</option>
                  </select>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      PAN Number *
                    </label>
                    <input
                      type="text"
                      required
                      maxLength={10}
                      value={form.pan_number ?? ""}
                      onChange={(e) => setForm({ ...form, pan_number: e.target.value.toUpperCase() })}
                      placeholder="ABCDE1234F"
                      className="w-full px-3.5 py-2.5 text-sm uppercase font-mono tracking-wider border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Name as per PAN *
                    </label>
                    <input
                      type="text"
                      required
                      value={form.pan_name ?? ""}
                      onChange={(e) => setForm({ ...form, pan_name: e.target.value })}
                      placeholder="e.g. C KANAKARAJ"
                      className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Date of Birth / Incorporation
                    </label>
                    <input
                      type="date"
                      value={form.date_of_birth ?? ""}
                      onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
                      className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600 bg-white"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Social Category *
                    </label>
                    <select
                      value={form.social_category ?? "General"}
                      onChange={(e) => setForm({ ...form, social_category: e.target.value })}
                      className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600 bg-white"
                    >
                      <option value="General">General</option>
                      <option value="OBC">OBC (Other Backward Classes)</option>
                      <option value="SC">SC (Scheduled Caste)</option>
                      <option value="ST">ST (Scheduled Tribe)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Gender *
                    </label>
                    <select
                      value={form.gender ?? "Male"}
                      onChange={(e) => setForm({ ...form, gender: e.target.value })}
                      className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600 bg-white"
                    >
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div className="p-3.5 border border-slate-200 rounded-2xl">
                    <label className="block text-xs font-semibold text-slate-800 mb-1">
                      Specially Abled (Divyang)?
                    </label>
                    <div className="flex items-center gap-4 mt-2">
                      <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                        <input
                          type="radio"
                          name="specially_abled"
                          checked={form.specially_abled === true}
                          onChange={() => setForm({ ...form, specially_abled: true })}
                          className="text-indigo-600"
                        />
                        <span>Yes</span>
                      </label>
                      <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                        <input
                          type="radio"
                          name="specially_abled"
                          checked={form.specially_abled === false}
                          onChange={() => setForm({ ...form, specially_abled: false })}
                          className="text-indigo-600"
                        />
                        <span>No</span>
                      </label>
                    </div>
                  </div>

                  <div className="p-3.5 border border-slate-200 rounded-2xl">
                    <label className="block text-xs font-semibold text-slate-800 mb-1">
                      Do you file Income Tax Returns (ITR)?
                    </label>
                    <div className="flex items-center gap-4 mt-2">
                      <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                        <input
                          type="radio"
                          name="itr_status"
                          checked={form.itr_status === "Yes"}
                          onChange={() => setForm({ ...form, itr_status: "Yes" })}
                          className="text-indigo-600"
                        />
                        <span>Yes</span>
                      </label>
                      <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                        <input
                          type="radio"
                          name="itr_status"
                          checked={form.itr_status === "No"}
                          onChange={() => setForm({ ...form, itr_status: "No", itr_form_type: "" })}
                          className="text-indigo-600"
                        />
                        <span>No</span>
                      </label>
                    </div>
                  </div>
                </div>

                {form.itr_status === "Yes" && (
                  <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-2 animate-fadeIn">
                    <label className="block text-xs font-semibold text-slate-700">
                      Select ITR Form Type *
                    </label>
                    <select
                      value={form.itr_form_type ?? ""}
                      onChange={(e) => setForm({ ...form, itr_form_type: e.target.value })}
                      className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-600"
                    >
                      <option value="">-- Select ITR Form --</option>
                      <option value="ITR-3">ITR-3 (Profits and gains of business/profession)</option>
                      <option value="ITR-4">ITR-4 / Sugam (Presumptive business income)</option>
                      <option value="ITR-5">ITR-5 (Partnership, LLP, AOP, BOI)</option>
                      <option value="ITR-6">ITR-6 (Companies other than exempt)</option>
                    </select>
                  </div>
                )}

                <div className="pt-2">
                  <label className="flex items-start gap-2.5 text-xs text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.pan_consent}
                      onChange={(e) => setForm({ ...form, pan_consent: e.target.checked })}
                      className="rounded text-indigo-600 focus:ring-indigo-600 mt-0.5 w-4 h-4"
                    />
                    <span className="leading-relaxed">
                      I authorize TAXLA to verify my PAN details with the official Income Tax database. *
                    </span>
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* ================= STEP 3: BUSINESS & FINANCIAL PROFILE ================= */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 3: Business, Contact & Financial Profile</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Contact details, business name, financial numbers, and automatic MSME classification.
                </p>
              </div>

              <div className="space-y-4 pt-1">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Primary Contact Mobile Number *
                    </label>
                    <input
                      type="text"
                      required
                      maxLength={10}
                      value={form.mobile_number ?? ""}
                      onChange={(e) => setForm({ ...form, mobile_number: e.target.value.replace(/\D/g, "") })}
                      placeholder="9876543210"
                      className="w-full px-3.5 py-2.5 text-sm font-mono border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Primary Email Address *
                    </label>
                    <input
                      type="email"
                      required
                      value={form.email ?? ""}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      placeholder="business@example.com"
                      className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Enterprise / Business Trade Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={form.enterprise_name ?? ""}
                    onChange={(e) => setForm({ ...form, enterprise_name: e.target.value })}
                    placeholder="e.g. RAJ ENTERPRISES"
                    className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-600"
                  />
                </div>

                {/* Financial Figures */}
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-4">
                  <div className="text-xs font-bold text-slate-900">Plant & Machinery / Equipment Investment (₹)</div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                        Written Down Value (WDV) *
                      </label>
                      <input
                        type="number"
                        min={0}
                        value={form.written_down_value ?? 0}
                        onChange={(e) => setForm({ ...form, written_down_value: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                        Exclusions (Pollution / R&D / Safety)
                      </label>
                      <input
                        type="number"
                        min={0}
                        value={form.pollution_control_exclusion ?? 0}
                        onChange={(e) => setForm({ ...form, pollution_control_exclusion: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                        Net Investment (Auto)
                      </label>
                      <div className="w-full px-3 py-2 text-sm font-bold bg-slate-200/70 border border-slate-300 rounded-lg text-slate-900">
                        ₹ {netInvestment.toLocaleString("en-IN")}
                      </div>
                    </div>
                  </div>

                  <div className="text-xs font-bold text-slate-900 pt-2 border-t border-slate-200">Turnover Details (₹)</div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                        Total Annual Turnover *
                      </label>
                      <input
                        type="number"
                        min={0}
                        value={form.total_turnover ?? 0}
                        onChange={(e) => setForm({ ...form, total_turnover: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                        Export Turnover (Exempted)
                      </label>
                      <input
                        type="number"
                        min={0}
                        value={form.export_turnover ?? 0}
                        onChange={(e) => setForm({ ...form, export_turnover: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                        Net Domestic Turnover (Auto)
                      </label>
                      <div className="w-full px-3 py-2 text-sm font-bold bg-slate-200/70 border border-slate-300 rounded-lg text-slate-900">
                        ₹ {netTurnover.toLocaleString("en-IN")}
                      </div>
                    </div>
                  </div>

                  {/* Calculated Classification Badge */}
                  <div className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-xl">
                    <div className="text-xs text-slate-600">Calculated MSME Enterprise Classification:</div>
                    <span className="px-3 py-1 bg-indigo-50 text-indigo-700 font-bold text-xs rounded-full border border-indigo-200">
                      {msmeCategory.toUpperCase()} ENTERPRISE
                    </span>
                  </div>
                </div>

                {/* GST Registration Section */}
                <div className="p-4 border border-slate-200 rounded-2xl space-y-3">
                  <div className="text-xs font-semibold text-slate-800">Do you have a GST Registration?</div>
                  <div className="flex items-center gap-6">
                    {["Yes", "No", "Exempted"].map((opt) => (
                      <label key={opt} className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                        <input
                          type="radio"
                          name="gst_status"
                          checked={form.gst_status === opt}
                          onChange={() => setForm({ ...form, gst_status: opt, gstin: opt === "Yes" ? form.gstin : "" })}
                          className="text-indigo-600"
                        />
                        <span>{opt}</span>
                      </label>
                    ))}
                  </div>

                  {form.gst_status === "Yes" && (
                    <div className="pt-2 animate-fadeIn">
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        15-Character GSTIN *
                      </label>
                      <input
                        type="text"
                        maxLength={15}
                        value={form.gstin ?? ""}
                        onChange={(e) => setForm({ ...form, gstin: e.target.value.toUpperCase() })}
                        placeholder="33ABCDE1234F1Z5"
                        className="w-full px-3.5 py-2 text-sm uppercase font-mono tracking-wider border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-600"
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ================= STEP 4: OFFICIAL OFFICE ADDRESS ================= */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 4: Official Office Address</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Official communication address of the enterprise. State & District are strictly mapped.
                </p>
              </div>

              <div className="space-y-4 pt-1">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Flat / Door / Block No.
                    </label>
                    <input
                      type="text"
                      value={form.flat_door_block ?? ""}
                      onChange={(e) => setForm({ ...form, flat_door_block: e.target.value })}
                      placeholder="e.g. 14/2, 2nd Floor"
                      className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-xl"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Premises / Building Name
                    </label>
                    <input
                      type="text"
                      value={form.premises_building ?? ""}
                      onChange={(e) => setForm({ ...form, premises_building: e.target.value })}
                      placeholder="e.g. Sri Lakshmi Complex"
                      className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-xl"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Village / Town / Area
                    </label>
                    <input
                      type="text"
                      value={form.village_town ?? ""}
                      onChange={(e) => setForm({ ...form, village_town: e.target.value })}
                      placeholder="e.g. T Nagar"
                      className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-xl"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Block
                    </label>
                    <input
                      type="text"
                      value={form.block ?? ""}
                      onChange={(e) => setForm({ ...form, block: e.target.value })}
                      placeholder="e.g. Block A"
                      className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-xl"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Road / Street / Lane
                    </label>
                    <input
                      type="text"
                      value={form.road_street ?? ""}
                      onChange={(e) => setForm({ ...form, road_street: e.target.value })}
                      placeholder="e.g. Usman Road"
                      className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-xl"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      City *
                    </label>
                    <input
                      type="text"
                      required
                      value={form.city ?? ""}
                      onChange={(e) => setForm({ ...form, city: e.target.value })}
                      placeholder="e.g. Chennai"
                      className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-xl"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      6-Digit PIN Code *
                    </label>
                    <input
                      type="text"
                      required
                      maxLength={6}
                      value={form.pin ?? ""}
                      onChange={(e) => setForm({ ...form, pin: e.target.value.replace(/\D/g, "") })}
                      placeholder="600017"
                      className="w-full px-3.5 py-2 text-sm font-mono border border-slate-300 rounded-xl"
                    />
                  </div>
                </div>

                {/* State and District Cascading Dropdowns */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      State / Union Territory *
                    </label>
                    <select
                      value={form.state ?? ""}
                      onChange={(e) => {
                        const newState = e.target.value;
                        const districts = getDistrictsForState(newState);
                        setForm({
                          ...form,
                          state: newState,
                          district: districts[0] || "",
                        });
                      }}
                      className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-xl bg-white"
                    >
                      <option value="">-- Select State --</option>
                      {INDIAN_STATES_LIST.map((st) => (
                        <option key={st} value={st}>
                          {st}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      District (Cascading) *
                    </label>
                    <select
                      value={form.district ?? ""}
                      onChange={(e) => setForm({ ...form, district: e.target.value })}
                      disabled={!form.state}
                      className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-xl bg-white disabled:bg-slate-100"
                    >
                      <option value="">-- Select District --</option>
                      {getDistrictsForState(form.state).map((dist) => (
                        <option key={dist} value={dist}>
                          {dist}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Official Contact Info for Address */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Official Contact Mobile (Pre-filled)
                    </label>
                    <input
                      type="text"
                      maxLength={10}
                      value={form.official_mobile ?? ""}
                      onChange={(e) => setForm({ ...form, official_mobile: e.target.value })}
                      placeholder="9876543210"
                      className="w-full px-3.5 py-2 text-sm font-mono border border-slate-300 rounded-xl"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Official Email Address (Pre-filled)
                    </label>
                    <input
                      type="email"
                      value={form.official_email ?? ""}
                      onChange={(e) => setForm({ ...form, official_email: e.target.value })}
                      placeholder="office@example.com"
                      className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-xl"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ================= STEP 5: BANK + PLANT / UNIT INFORMATION ================= */}
          {currentStep === 5 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 5: Bank Details & Plant / Unit Locations</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Bank account for enterprise operations and optional branch plant / unit locations.
                </p>
              </div>

              <div className="space-y-4 pt-1">
                {/* Bank Account Details */}
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
                  <div className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                    <Building2 className="w-4 h-4 text-indigo-600" />
                    Enterprise Bank Account Details
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Bank Name *
                    </label>
                    <input
                      type="text"
                      required
                      value={form.bank_name ?? ""}
                      onChange={(e) => setForm({ ...form, bank_name: e.target.value })}
                      placeholder="e.g. State Bank of India / HDFC Bank"
                      className="w-full px-3.5 py-2 text-sm border border-slate-300 rounded-xl bg-white"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Bank IFSC Code *
                    </label>
                    <input
                      type="text"
                      required
                      maxLength={11}
                      value={form.bank_ifsc ?? ""}
                      onChange={(e) => setForm({ ...form, bank_ifsc: e.target.value.toUpperCase() })}
                      placeholder="SBIN0001234"
                      className="w-full px-3.5 py-2 text-sm font-mono uppercase tracking-wider border border-slate-300 rounded-xl bg-white"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Bank Account Number *
                      </label>
                      <input
                        type="text"
                        required
                        value={form.bank_account_number ?? ""}
                        onChange={(e) => setForm({ ...form, bank_account_number: e.target.value.replace(/\D/g, "") })}
                        placeholder="123456789012"
                        className="w-full px-3.5 py-2 text-sm font-mono border border-slate-300 rounded-xl bg-white"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Confirm Bank Account Number *
                      </label>
                      <input
                        type="text"
                        required
                        value={form.confirm_bank_account_number ?? ""}
                        onChange={(e) => setForm({ ...form, confirm_bank_account_number: e.target.value.replace(/\D/g, "") })}
                        placeholder="123456789012"
                        className="w-full px-3.5 py-2 text-sm font-mono border border-slate-300 rounded-xl bg-white"
                      />
                    </div>
                  </div>
                </div>

                {/* Plant / Unit Locations Section */}
                <div className="p-4 border border-slate-200 rounded-2xl space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-bold text-slate-900">Plant / Workshop / Branch Units</div>
                      <div className="text-[11px] text-slate-500">Do you have separate manufacturing or workshop units?</div>
                    </div>

                    <div className="flex items-center gap-3">
                      <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
                        <input
                          type="radio"
                          name="has_plant_units"
                          checked={form.has_plant_units === true}
                          onChange={() => setForm({ ...form, has_plant_units: true, units: form.units.length ? form.units : [{ unit_name: `${form.enterprise_name || "Plant"} Unit 1`, city: form.city || "", state: form.state || "TAMIL NADU", district: form.district || "CHENNAI", pin: form.pin || "" }] })}
                          className="text-indigo-600"
                        />
                        <span>Yes</span>
                      </label>
                      <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
                        <input
                          type="radio"
                          name="has_plant_units"
                          checked={form.has_plant_units === false}
                          onChange={() => setForm({ ...form, has_plant_units: false, units: [] })}
                          className="text-indigo-600"
                        />
                        <span>No (Same as Office)</span>
                      </label>
                    </div>
                  </div>

                  {form.has_plant_units && (
                    <div className="space-y-4 pt-2 border-t border-slate-100">
                      {form.units.map((unit: any, idx: number) => (
                        <div key={idx} className="p-4 bg-slate-50/70 border border-slate-200 rounded-xl space-y-3 relative">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-indigo-900">Unit #{idx + 1}</span>
                            <button
                              type="button"
                              onClick={() => handleRemoveUnit(idx)}
                              className="text-slate-400 hover:text-rose-600 text-xs flex items-center gap-1"
                            >
                              <Trash2 className="w-3.5 h-3.5" /> Remove
                            </button>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                              <label className="block text-[11px] font-semibold text-slate-600 mb-1">Unit Name *</label>
                              <input
                                type="text"
                                value={unit.unit_name}
                                onChange={(e) => handleUnitChange(idx, "unit_name", e.target.value)}
                                className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg bg-white"
                              />
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-slate-600 mb-1">City *</label>
                              <input
                                type="text"
                                value={unit.city}
                                onChange={(e) => handleUnitChange(idx, "city", e.target.value)}
                                className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg bg-white"
                              />
                            </div>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            <div>
                              <label className="block text-[11px] font-semibold text-slate-600 mb-1">State *</label>
                              <select
                                value={unit.state}
                                onChange={(e) => handleUnitChange(idx, "state", e.target.value)}
                                className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg bg-white"
                              >
                                {INDIAN_STATES_LIST.map((s) => (
                                  <option key={s} value={s}>{s}</option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-slate-600 mb-1">District *</label>
                              <select
                                value={unit.district}
                                onChange={(e) => handleUnitChange(idx, "district", e.target.value)}
                                className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg bg-white"
                              >
                                {getDistrictsForState(unit.state).map((d) => (
                                  <option key={d} value={d}>{d}</option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-slate-600 mb-1">PIN Code *</label>
                              <input
                                type="text"
                                maxLength={6}
                                value={unit.pin}
                                onChange={(e) => handleUnitChange(idx, "pin", e.target.value.replace(/\D/g, ""))}
                                className="w-full px-3 py-1.5 text-xs font-mono border border-slate-300 rounded-lg bg-white"
                              />
                            </div>
                          </div>
                        </div>
                      ))}

                      <button
                        type="button"
                        onClick={handleAddUnit}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition"
                      >
                        <Plus className="w-3.5 h-3.5" /> Add Another Plant / Unit
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ================= STEP 6: MAJOR ACTIVITY & NIC ================= */}
          {currentStep === 6 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 6: Major Activity & Products (NIC)</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Classify your business activity under the National Industrial Classification (NIC) scheme.
                </p>
              </div>

              <div className="space-y-4 pt-1">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-2">
                    Major Business Activity *
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {["Services", "Manufacturing", "Trading"].map((act) => (
                      <button
                        key={act}
                        type="button"
                        onClick={() => setForm({ ...form, major_activity: act })}
                        className={`p-3.5 rounded-2xl border text-left transition-all ${
                          form.major_activity === act
                            ? "bg-indigo-50 border-indigo-600 text-indigo-950 font-bold shadow-xs ring-1 ring-indigo-600"
                            : "bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100/70"
                        }`}
                      >
                        <div className="text-sm">{act}</div>
                        <div className="text-[11px] text-slate-500 font-normal mt-0.5">
                          {act === "Services" && "IT, consultancy, logistics, hotels, hospitality"}
                          {act === "Manufacturing" && "Production, fabrication, food processing, assembly"}
                          {act === "Trading" && "Wholesale, retail, spare parts, distribution"}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Business Activity Description *
                  </label>
                  <textarea
                    rows={3}
                    required
                    value={form.business_activity_description ?? ""}
                    onChange={(e) => setForm({ ...form, business_activity_description: e.target.value })}
                    placeholder="Describe what products your business sells or services your business delivers (e.g. Software development, web design, and IT infrastructure consulting)..."
                    className="w-full px-3.5 py-2.5 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-600"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">
                    Our compliance specialists will review this description to ensure the exact 5-digit NIC code matches official MSME guidelines.
                  </p>
                </div>

                {/* Hierarchical NIC Selector */}
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
                  <div className="text-xs font-bold text-slate-900">Add 5-Digit NIC Activity Codes</div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">2-Digit Division</label>
                      <select
                        value={selectedNic2}
                        onChange={(e) => {
                          setSelectedNic2(e.target.value);
                          setSelectedNic4("");
                          setSelectedNic5("");
                        }}
                        className="w-full px-2.5 py-2 text-xs border border-slate-300 rounded-lg bg-white"
                      >
                        <option value="">-- Select 2-Digit --</option>
                        {getNic2Digits(form.major_activity).map((d) => (
                          <option key={d.code} value={d.code}>{d.label}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">4-Digit Group</label>
                      <select
                        value={selectedNic4}
                        disabled={!selectedNic2}
                        onChange={(e) => {
                          setSelectedNic4(e.target.value);
                          setSelectedNic5("");
                        }}
                        className="w-full px-2.5 py-2 text-xs border border-slate-300 rounded-lg bg-white disabled:bg-slate-100"
                      >
                        <option value="">-- Select 4-Digit --</option>
                        {getNic4Digits(selectedNic2).map((g) => (
                          <option key={g.code} value={g.code}>{g.label}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">5-Digit Sub-Class</label>
                      <select
                        value={selectedNic5}
                        disabled={!selectedNic4}
                        onChange={(e) => setSelectedNic5(e.target.value)}
                        className="w-full px-2.5 py-2 text-xs border border-slate-300 rounded-lg bg-white disabled:bg-slate-100"
                      >
                        <option value="">-- Select 5-Digit --</option>
                        {getNic5Digits(selectedNic2, selectedNic4).map((s) => (
                          <option key={s.code} value={s.code}>{s.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="pt-1">
                    <button
                      type="button"
                      disabled={!selectedNic5}
                      onClick={handleAddNicActivity}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 rounded-lg transition"
                    >
                      <Plus className="w-3.5 h-3.5" /> Add Selected NIC Activity
                    </button>
                  </div>

                  {/* List of Added NIC Activities */}
                  {form.activities?.length > 0 && (
                    <div className="space-y-2 pt-2 border-t border-slate-200">
                      <div className="text-[11px] font-semibold text-slate-700">Selected NIC Codes:</div>
                      {form.activities.map((act: any, idx: number) => (
                        <div key={idx} className="p-2.5 bg-white border border-slate-200 rounded-lg flex items-center justify-between text-xs">
                          <div>
                            <span className="font-mono font-bold text-indigo-700">{act.nic_5digit}</span>
                            <span className="text-slate-500 ml-2">({act.activity_type})</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleRemoveNicActivity(idx)}
                            className="text-slate-400 hover:text-rose-600 text-xs"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ================= STEP 7: EMPLOYMENT & STATUTORY REGISTRATIONS ================= */}
          {currentStep === 7 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 7: Employment & Statutory Registrations</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Employment headcounts and optional enrollment in official government MSME portals.
                </p>
              </div>

              <div className="space-y-4 pt-1">
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
                  <div className="text-xs font-bold text-slate-900">Total Persons Employed</div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">Male *</label>
                      <input
                        type="number"
                        min={0}
                        value={form.male_employees ?? 0}
                        onChange={(e) => setForm({ ...form, male_employees: parseInt(e.target.value, 10) || 0 })}
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">Female *</label>
                      <input
                        type="number"
                        min={0}
                        value={form.female_employees ?? 0}
                        onChange={(e) => setForm({ ...form, female_employees: parseInt(e.target.value, 10) || 0 })}
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">Other *</label>
                      <input
                        type="number"
                        min={0}
                        value={form.other_employees ?? 0}
                        onChange={(e) => setForm({ ...form, other_employees: parseInt(e.target.value, 10) || 0 })}
                        className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">Total (Auto)</label>
                      <div className="w-full px-3 py-2 text-sm font-bold bg-slate-200/70 border border-slate-300 rounded-lg text-slate-900">
                        {totalEmployees}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Statutory Portal Interests */}
                <div className="space-y-2 pt-2">
                  <div className="text-xs font-bold text-slate-900 mb-2">Optional Government Portal Linkages:</div>

                  {[
                    { key: "interested_in_gem", title: "Government e-Marketplace (GeM)", desc: "Direct selling to central/state government departments and PSUs without tender." },
                    { key: "interested_in_treds", title: "Trade Receivables Discounting System (TReDS)", desc: "Discount trade receivables through multiple financiers for immediate liquidity." },
                    { key: "interested_in_ncs", title: "National Career Service (NCS)", desc: "Recruit skilled workforce from the national employment portal." },
                    { key: "interested_in_nsic_b2b", title: "NSIC B2B Portal", desc: "Access national and international tenders and business opportunities." },
                    { key: "interested_in_skill_india", title: "Skill India Digital Portal", desc: "Train apprentices and access government-subsidized upskilling programs." },
                  ].map((portal) => (
                    <label
                      key={portal.key}
                      className="flex items-start gap-3 p-3.5 border border-slate-200 hover:border-slate-300 rounded-2xl cursor-pointer bg-white transition"
                    >
                      <input
                        type="checkbox"
                        checked={form[portal.key] ?? false}
                        onChange={(e) => setForm({ ...form, [portal.key]: e.target.checked })}
                        className="rounded text-indigo-600 focus:ring-indigo-600 mt-0.5 w-4 h-4"
                      />
                      <div>
                        <div className="text-xs font-bold text-slate-900">{portal.title}</div>
                        <div className="text-[11px] text-slate-500 mt-0.5">{portal.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ================= STEP 8: REVIEW & SUBMIT ================= */}
          {currentStep === 8 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 8: Review & Final Confirmation</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Verify all information before final submission. Sensitive IDs are securely masked.
                </p>
              </div>

              {/* Review sections */}
              <div className="space-y-4">
                {/* 1. Owner & PAN */}
                <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 text-xs space-y-2">
                  <div className="font-bold text-slate-900 pb-1 border-b border-slate-200 flex justify-between">
                    <span>1. Applicant Identity & Tax Profile</span>
                    <button type="button" onClick={() => setCurrentStep(1)} className="text-indigo-600 font-semibold text-[11px]">Edit</button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div><span className="text-slate-500">Applicant Name:</span> <strong>{form.aadhaar_name}</strong></div>
                    <div><span className="text-slate-500">Aadhaar:</span> <strong className="font-mono">•••• •••• {form.aadhaar_number?.slice(-4)}</strong></div>
                    <div><span className="text-slate-500">Organization:</span> <strong>{form.organization_type}</strong></div>
                    <div><span className="text-slate-500">PAN:</span> <strong className="font-mono">{form.pan_number}</strong></div>
                    <div><span className="text-slate-500">Category / Gender:</span> <strong>{form.social_category} / {form.gender}</strong></div>
                    <div><span className="text-slate-500">ITR Filed:</span> <strong>{form.itr_status} {form.itr_form_type ? `(${form.itr_form_type})` : ""}</strong></div>
                  </div>
                </div>

                {/* 2. Business & Contact */}
                <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 text-xs space-y-2">
                  <div className="font-bold text-slate-900 pb-1 border-b border-slate-200 flex justify-between">
                    <span>2. Business & Financial Profile</span>
                    <button type="button" onClick={() => setCurrentStep(3)} className="text-indigo-600 font-semibold text-[11px]">Edit</button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div><span className="text-slate-500">Enterprise Name:</span> <strong>{form.enterprise_name}</strong></div>
                    <div><span className="text-slate-500">Contact:</span> <strong>{form.mobile_number} | {form.email}</strong></div>
                    <div><span className="text-slate-500">Net Investment:</span> <strong>₹ {netInvestment.toLocaleString("en-IN")}</strong></div>
                    <div><span className="text-slate-500">Net Turnover:</span> <strong>₹ {netTurnover.toLocaleString("en-IN")}</strong></div>
                    <div><span className="text-slate-500">Classification:</span> <span className="font-bold text-indigo-700">{msmeCategory}</span></div>
                    <div><span className="text-slate-500">GST Status:</span> <strong>{form.gst_status} {form.gstin ? `(${form.gstin})` : ""}</strong></div>
                  </div>
                </div>

                {/* 3. Official Address & Units */}
                <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 text-xs space-y-2">
                  <div className="font-bold text-slate-900 pb-1 border-b border-slate-200 flex justify-between">
                    <span>3. Official Address & Units</span>
                    <button type="button" onClick={() => setCurrentStep(4)} className="text-indigo-600 font-semibold text-[11px]">Edit</button>
                  </div>
                  <div>
                    <span className="text-slate-500">Address:</span>{" "}
                    <strong>
                      {[form.flat_door_block, form.premises_building, form.road_street, form.city, form.district, form.state, form.pin]
                        .filter(Boolean)
                        .join(", ")}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500">Registered Plants / Units:</span>{" "}
                    <strong>{form.has_plant_units ? `${form.units.length} unit(s)` : "1 unit (Primary Office Location)"}</strong>
                  </div>
                </div>

                {/* 4. Bank & Activities */}
                <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 text-xs space-y-2">
                  <div className="font-bold text-slate-900 pb-1 border-b border-slate-200 flex justify-between">
                    <span>4. Bank & Activities</span>
                    <button type="button" onClick={() => setCurrentStep(5)} className="text-indigo-600 font-semibold text-[11px]">Edit</button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div><span className="text-slate-500">Bank:</span> <strong>{form.bank_name} ({form.bank_ifsc})</strong></div>
                    <div><span className="text-slate-500">Account:</span> <strong className="font-mono">••••••••{form.bank_account_number?.slice(-4)}</strong></div>
                    <div><span className="text-slate-500">Major Activity:</span> <strong>{form.major_activity}</strong></div>
                    <div><span className="text-slate-500">Employees:</span> <strong>{totalEmployees} (Male: {form.male_employees}, Female: {form.female_employees}, Other: {form.other_employees})</strong></div>
                  </div>
                </div>
              </div>

              {/* Solemn Declaration */}
              <div className="pt-2">
                <label className="flex items-start gap-3 text-xs text-slate-800 cursor-pointer p-4 bg-indigo-50/60 border border-indigo-200 rounded-2xl">
                  <input
                    type="checkbox"
                    checked={form.declaration_agreed}
                    onChange={(e) => setForm({ ...form, declaration_agreed: e.target.checked })}
                    className="rounded text-indigo-600 focus:ring-indigo-600 mt-0.5 w-4 h-4"
                  />
                  <span className="leading-relaxed">
                    I solemnly declare that the information provided above is true and correct to the best of my knowledge and belief. I authorize TAXLA and its compliance representatives to verify these particulars and process my Udyam Registration on the official Ministry of MSME portal.
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* Navigation Controls */}
          <div className="pt-6 mt-8 border-t border-slate-100 flex items-center justify-between">
            {currentStep > 1 ? (
              <button
                type="button"
                onClick={handlePrev}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-xl transition"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Previous</span>
              </button>
            ) : (
              <div />
            )}

            {currentStep < STEPS.length ? (
              <button
                type="button"
                onClick={handleNext}
                className="inline-flex items-center gap-2 px-6 py-2.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-sm transition"
              >
                <span>Save & Continue</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitting || !form.declaration_agreed}
                className="inline-flex items-center gap-2 px-7 py-3 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 rounded-xl shadow-md transition"
              >
                {submitting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Submitting Requirements…</span>
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4 stroke-[3]" />
                    <span>Submit Requirements</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center py-4 text-xs text-slate-400 border-t border-slate-200/60 bg-white">
        TAXLA Secure Customer Requirement Intake &bull; 256-Bit Encrypted &bull; Official Ministry of MSME Compliance
      </footer>
    </div>
  );
}
