"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { saveSession } from "@/lib/session";
import { Button, Input } from "./ui";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const isRegister = mode === "register";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const session = isRegister
        ? await api.register({ email, password, ...(displayName.trim() ? { display_name: displayName.trim() } : {}) })
        : await api.login({ email, password });
      saveSession(session);
      router.replace("/campaigns");
    } catch (caught: unknown) {
      setError(caught instanceof ApiError ? caught.message : "We couldn’t sign you in. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-[#f8f1e9] lg:grid-cols-[1.1fr_0.9fr]">
      <section className="hidden bg-[#8f1029] p-12 text-[#fff4dd] lg:flex lg:flex-col lg:justify-between"><div className="flex items-center gap-3"><span className="grid size-11 place-items-center rounded-2xl bg-[#fff0b8] font-serif text-xl font-bold text-[#8f1029]">চি</span><strong className="font-serif text-2xl">Chitro</strong></div><div><p className="eyebrow text-[#ffd7c5]">Editorial operations, in motion</p><h1 className="mt-4 max-w-xl text-6xl leading-[1.02]">From the first brief to the next sharp insight.</h1><p className="mt-6 max-w-lg text-lg leading-8 text-[#ffd7c5]">A working room for campaigns, content, approvals, and the decisions behind them.</p></div><p className="text-sm text-[#ffd7c5]">Built for teams making culture move.</p></section>
      <section className="flex items-center justify-center px-5 py-12 sm:px-10"><div className="w-full max-w-md"><Link href="/" className="font-serif text-2xl text-[#8f1029] lg:hidden">Chitro</Link><p className="eyebrow mt-10">Welcome to your workspace</p><h2 className="mt-2 text-4xl text-[#321d20]">{isRegister ? "Create your workspace" : "Pick up where you left off"}</h2><p className="mt-3 text-[#77595a]">{isRegister ? "Set up your workspace and start creating campaigns." : "Sign in to manage your campaigns and content."}</p>
        <form className="mt-8 space-y-5" onSubmit={submit}>
          {isRegister && <label className="block"><span className="field-label">Your name <span className="font-normal text-[#9a7676]">(optional)</span></span><Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="name" /></label>}
          <label className="block"><span className="field-label">Email</span><Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required /></label>
          <label className="block"><span className="field-label">Password</span><Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={isRegister ? "new-password" : "current-password"} minLength={isRegister ? 8 : 1} required /></label>
          {error && <p role="alert" className="rounded-xl bg-[#f7dce0] px-4 py-3 text-sm text-[#861a31]">{error}</p>}
          <Button type="submit" className="w-full" disabled={submitting}>{submitting ? "Working…" : isRegister ? "Create workspace" : "Sign in"}</Button>
        </form>
        <p className="mt-6 text-center text-sm text-[#77595a]">{isRegister ? "Already have a workspace? " : "New to Chitro? "}<Link className="font-semibold text-[#8f1029] underline underline-offset-4" href={isRegister ? "/login" : "/register"}>{isRegister ? "Sign in" : "Create an account"}</Link></p>
      </div></section>
    </main>
  );
}
