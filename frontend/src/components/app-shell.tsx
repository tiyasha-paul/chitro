"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { api, ApiError, type AuthResponse } from "@/lib/api";
import { clearSession, getSession, saveSession } from "@/lib/session";
import { Button, LoadingState } from "./ui";

export function AppShell({ children }: { children: (session: AuthResponse) => ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const stored = getSession();
    if (!stored) {
      router.replace("/login");
      return;
    }
    api.me(stored.access_token)
      .then((verified) => {
        saveSession(verified);
        setSession(verified);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 0) {
          setSession(stored);
          return;
        }
        clearSession();
        router.replace("/login");
      })
      .finally(() => setChecking(false));
  }, [router]);

  function logout() {
    clearSession();
    router.replace("/login");
  }

  if (checking || !session) return <main className="min-h-screen bg-[#f8f1e9]"><LoadingState label="Opening your workspace…" /></main>;

  return (
    <div className="min-h-screen bg-[#f8f1e9] text-[#321d20]">
      <header className="border-b border-[#ead9cf] bg-[#fffaf3]">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <Link href="/campaigns" className="group flex items-center gap-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8f1029]">
            <span className="grid size-10 place-items-center rounded-2xl bg-[#8f1029] font-serif text-xl font-bold text-[#fff4dd]">চি</span>
            <span><strong className="block font-serif text-xl leading-5">Chitro</strong><span className="text-xs text-[#805d5f]">Content operations</span></span>
          </Link>
          <nav aria-label="Workspace navigation" className="hidden items-center gap-1 sm:flex">
            <Link className={`rounded-full px-4 py-2 text-sm font-semibold ${pathname === "/campaigns" ? "bg-[#f6e5dc] text-[#8f1029]" : "text-[#67474a] hover:bg-[#f6e5dc]"}`} href="/campaigns">Campaigns</Link>
            <Link className={`rounded-full px-4 py-2 text-sm font-semibold ${pathname === "/campaigns/new" ? "bg-[#f6e5dc] text-[#8f1029]" : "text-[#67474a] hover:bg-[#f6e5dc]"}`} href="/campaigns/new">New brief</Link>
          </nav>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block"><p className="max-w-40 truncate text-sm font-semibold">{session.user.display_name}</p><p className="max-w-40 truncate text-xs text-[#805d5f]">{session.workspace.name}</p></div>
            <Button variant="quiet" className="px-3" onClick={logout}>Log out</Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-5 py-9 sm:px-8">{children(session)}</main>
    </div>
  );
}
