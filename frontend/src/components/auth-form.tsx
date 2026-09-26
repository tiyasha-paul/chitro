"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { saveSession } from "@/lib/session";
import { Button, Input } from "./ui";

interface AuthFormProps {
  mode: "login" | "register";
}

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      if (mode === "register") {
        const res = await api.register({
          email,
          password,
          display_name: displayName || undefined,
        });
        saveSession(res);
      } else {
        const res = await api.login({ email, password });
        saveSession(res);
      }
      router.replace("/campaigns");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Left Panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 bg-[#8f1029] text-[#fff4dd]">
        <div>
          <div className="flex items-center gap-3 mb-16">
            <div className="bg-[#fff4dd] text-[#8f1029] w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xl leading-none pt-1">
              চী
            </div>
            <span className="font-serif text-2xl font-semibold tracking-tight">Chitro</span>
          </div>
          <div className="max-w-md">
            <div className="text-xs font-medium uppercase tracking-widest text-[#fff4dd]/70 mb-4">
              Editorial operations, in motion
            </div>
            <h1 className="text-5xl font-serif leading-[1.1] mb-6">
              From the first brief to the next sharp insight.
            </h1>
            <p className="text-lg text-[#fff4dd]/80 leading-relaxed">
              A working room for campaigns, content, approvals, and the decisions behind them.
            </p>
          </div>
        </div>
        <div className="text-sm text-[#fff4dd]/60">
          Built for teams making culture move.
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 flex flex-col justify-center items-center p-8 bg-surface">
        <div className="w-full max-w-md">
          <div className="mb-8">
            <div className="text-xs font-medium uppercase tracking-widest text-text-muted mb-3">
              Welcome to your workspace
            </div>
            <h2 className="text-3xl font-serif">
              {mode === "register" ? "Create your workspace" : "Pick up where you left off"}
            </h2>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="p-3 bg-danger/10 text-danger rounded-xl text-sm">
                {error}
              </div>
            )}

            {mode === "register" && (
              <div className="space-y-1.5">
                <label className="field-label" htmlFor="displayName">
                  Display Name (Optional)
                </label>
                <Input
                  id="displayName"
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="How should we call you?"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <label className="field-label" htmlFor="email">
                Email Address
              </label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
              />
            </div>

            <div className="space-y-1.5">
              <label className="field-label" htmlFor="password">
                Password
              </label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>

            <Button
              type="submit"
              className="w-full"
              loading={submitting}
            >
              {mode === "register" ? "Create Account" : "Sign In"}
            </Button>
          </form>

          <div className="mt-8 text-center text-sm text-text-muted">
            {mode === "register" ? (
              <>
                Already have an account?{" "}
                <Link href="/login" className="text-text hover:text-brand font-medium underline underline-offset-4">
                  Sign in
                </Link>
              </>
            ) : (
              <>
                Don't have an account?{" "}
                <Link href="/register" className="text-text hover:text-brand font-medium underline underline-offset-4">
                  Create one
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
