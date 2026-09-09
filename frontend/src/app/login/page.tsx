"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Lock, Mail, ArrowRight, ShieldCheck } from "lucide-react";

import { loginRequest } from "@/api/workflow";
import { useAuthStore } from "@/stores/authStore";

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginForm />
    </Suspense>
  );
}

function LoginFallback() {
  return (
    <main className="min-h-screen w-full flex items-center justify-center bg-slate-50 px-4">
      <div className="text-slate-500 text-sm font-medium">Loading session…</div>
    </main>
  );
}

function LoginForm() {
  const router = useRouter();
  const search = useSearchParams();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const user = useAuthStore((s) => s.user);
  useEffect(() => {
    if (user) router.replace("/");
  }, [user, router]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { user: u, accessToken } = await loginRequest(email, password);
      setAuth({ user: u, accessToken });
      const next = search.get("next") || "/";
      router.replace(next);
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 401) {
        setError("Invalid email address or password.");
      } else {
        setError("Unable to authenticate. Please verify backend connection.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  // Quick filler for local development testing
  function fillDevCredentials(userEmail: string, pass: string) {
    setEmail(userEmail);
    setPassword(pass);
  }

  return (
    <main className="min-h-screen w-full flex items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md">
        {/* Header Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-indigo-600 text-white font-black text-xl shadow-md mb-3">
            TX
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            TAXLA Operations
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Enterprise MSME / Udyam Registration Platform
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-7">
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label
                htmlFor="email"
                className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
              >
                Employee Email
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  id="email"
                  type="email"
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={submitting}
                  placeholder="operator@taxla.com"
                  className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-slate-300 rounded-lg text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 transition-colors"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={submitting}
                  placeholder="••••••••••••"
                  className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-slate-300 rounded-lg text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 transition-colors"
                />
              </div>
            </div>

            {error && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs font-medium flex items-center gap-2">
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={submitting || !email || !password}
              className="w-full mt-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-semibold rounded-lg shadow-sm transition-colors flex items-center justify-center gap-2"
            >
              <span>{submitting ? "Authenticating…" : "Sign In to Operations"}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* Local Development Seed Credentials Help */}
          <div className="mt-6 pt-5 border-t border-slate-100">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 mb-2">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
              <span>Local Dev Seed Accounts:</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => fillDevCredentials("admin@taxla.com", "Admin@123")}
                className="p-2 text-left bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded transition-colors"
              >
                <div className="font-semibold text-slate-800">Admin</div>
                <div className="text-[11px] text-slate-500">admin@taxla.com</div>
              </button>
              <button
                type="button"
                onClick={() => fillDevCredentials("operator@taxla.com", "Operator@123")}
                className="p-2 text-left bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded transition-colors"
              >
                <div className="font-semibold text-slate-800">Operator</div>
                <div className="text-[11px] text-slate-500">operator@taxla.com</div>
              </button>
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-slate-400 mt-6">
          TAXLA Internal Operations &copy; {new Date().getFullYear()}
        </p>
      </div>
    </main>
  );
}