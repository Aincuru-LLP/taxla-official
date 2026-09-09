"use client";

import { useState } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, KeyRound } from "lucide-react";

import { useSubmitOTP } from "@/lib/api-client";

/**
 * Phase 11 — OTPInputModal.
 *
 * Six-digit code entry for the OTP_REQUIRED state. The portal worker is
 * blocked until this resolves. We force digits-only via ``inputMode="numeric"``
 * plus the regex filter (some Android keyboards ignore inputMode).
 *
 * Submission goes through ``useSubmitOTP`` so we inherit React Query's
 * loading + error handling for free.
 */

interface OTPInputModalProps {
  application: { id: string; status: string };
  onUpdate?: () => void;
}

function otpTypeFor(status: string): string {
  switch (status?.toUpperCase()) {
    case "AADHAAR_OTP_REQUIRED":
    case "AADHAAR_OTP":
      return "AADHAAR";
    case "OTP_REQUIRED":
      return "AADHAAR";
    case "PAN_VERIFICATION":
      return "PAN";
    default:
      return "AADHAAR";
  }
}

export default function OTPInputModal({ application, onUpdate }: OTPInputModalProps) {
  const [code, setCode] = useState("");
  const submit = useSubmitOTP(application.id);
  const otpType = otpTypeFor(application.status);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (code.length !== 6) return;
    try {
      await submit.mutateAsync({ otp_type: otpType, code });
      setCode("");
      onUpdate?.();
    } catch (err) {
      console.error("[OTPInputModal] submit failed", err);
    }
  };

  const loading = submit.isPending;

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md bg-slate-900/80 border-violet-500/50 shadow-2xl shadow-violet-500/20">
        <form onSubmit={handleSubmit}>
          <CardHeader className="text-center space-y-2">
            <div className="mx-auto bg-violet-500/20 p-3 rounded-full w-16 h-16 flex items-center justify-center mb-2">
              <KeyRound className="w-8 h-8 text-violet-300" />
            </div>
            <CardTitle className="text-2xl text-slate-100">OTP Required</CardTitle>
            <CardDescription className="text-base text-slate-300">
              The automation engine is paused waiting for the {otpType} OTP.
              Please enter the 6-digit code sent to the client&apos;s registered
              mobile number.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex justify-center mt-4">
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                className="w-full max-w-[240px] text-center text-4xl tracking-[0.5em] font-mono bg-slate-950 border-b-2 border-violet-500/50 focus:border-violet-400 outline-none py-2 text-slate-100 transition-colors"
                placeholder="000000"
                autoFocus
                aria-label="One-time password"
              />
            </div>
          </CardContent>
          <CardFooter className="flex justify-center pt-6 pb-8">
            <Button
              type="submit"
              size="lg"
              className="w-full max-w-[240px]"
              disabled={code.length !== 6 || loading}
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : null}
              Submit OTP &amp; Resume
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}