"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api, ApiError, type AuthResponse } from "@/lib/api";
import { clearSession, getSession, saveSession } from "@/lib/session";
import { Button, LoadingState } from "./ui";

interface AppShellProps {
  children: (session: AuthResponse) => ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    async function checkAuth() {
      try {
        const stored = getSession();
        if (!stored) {
          router.push("/login");
          return;
        }

        try {
          const fresh = await api.me();
          saveSession(fresh);
          setSession(fresh);
        } catch (err) {
          if (err instanceof ApiError && err.status === 0) {
            // Network error (status 0), fallback to stored session
            setSession(stored);
          } else {
            // Unauthenticated or other error, clear and redirect
            clearSession();
            router.push("/login");
          }
        }
      } finally {
        setLoading(false);
      }
    }

    checkAuth();
  }, [router]);

  const handleLogout = async () => {
    try {
      await api.logout();
    } finally {
      clearSession();
      router.push("/login");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#f8f1e9] flex items-center justify-center">
        <LoadingState text="Loading session..." />
      </div>
    );
  }

  if (!session) {
    return null;
  }

  const navLinks = [
    { name: "Campaigns", href: "/campaigns" },
  ];

  return (
    <div className="min-h-screen bg-[#f8f1e9] flex flex-col lg:flex-row text-[#321d20]">
      {/* Mobile Header */}
      <header className="lg:hidden bg-[#fffaf3] border-b border-[#ead9cf] p-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold text-[#8f1029]">চী</span>
          <span className="font-semibold text-lg text-[#321d20]">Chitro</span>
        </div>
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-2 rounded-md hover:bg-[#f6e5dc] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#8f1029] text-[#8f1029]"
          aria-expanded={mobileMenuOpen}
          aria-label="Toggle mobile menu"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={mobileMenuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
          </svg>
        </button>
      </header>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="lg:hidden bg-[#fffaf3] border-b border-[#ead9cf] p-4 flex flex-col gap-4 shadow-sm">
          <nav aria-label="Mobile Navigation" className="flex flex-col gap-2">
            {navLinks.map((link) => {
              const isActive = pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`px-4 py-2 rounded-md font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-[#8f1029] transition-colors ${
                    isActive
                      ? "bg-[#f6e5dc] text-[#8f1029]"
                      : "text-[#321d20] hover:bg-[#f6e5dc] hover:text-[#8f1029]"
                  }`}
                >
                  {link.name}
                </Link>
              );
            })}
          </nav>
          <div className="pt-4 border-t border-[#ead9cf]">
            <div className="font-medium text-[#321d20] mb-1 px-2">{session.user.display_name}</div>
            <div className="text-sm text-[#805d5f] mb-4 px-2">{session.workspace.name}</div>
            <Button onClick={handleLogout} className="w-full">
              Log out
            </Button>
          </div>
        </div>
      )}

      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-56 flex-col bg-[#fffaf3] border-r border-[#ead9cf] fixed inset-y-0 left-0 z-10">
        <div className="p-6">
          <div className="flex items-center gap-3 mb-1">
            <span className="text-3xl font-bold text-[#8f1029]">চী</span>
            <span className="text-xl font-bold tracking-tight text-[#321d20]">Chitro</span>
          </div>
          <p className="text-xs text-[#67474a] font-medium tracking-wide uppercase">Content operations</p>
        </div>

        <nav aria-label="Desktop Navigation" className="flex-1 px-4 mt-6">
          <ul className="space-y-2">
            {navLinks.map((link) => {
              const isActive = pathname.startsWith(link.href);
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className={`block px-4 py-2 rounded-md font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-[#8f1029] transition-colors ${
                      isActive
                        ? "bg-[#f6e5dc] text-[#8f1029]"
                        : "text-[#321d20] hover:bg-[#f6e5dc] hover:text-[#8f1029]"
                    }`}
                  >
                    {link.name}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="p-4 border-t border-[#ead9cf]">
          <div className="mb-4 px-2">
            <div className="font-medium text-[#321d20] truncate">{session.user.display_name}</div>
            <div className="text-sm text-[#805d5f] truncate">{session.workspace.name}</div>
          </div>
          <Button onClick={handleLogout} className="w-full">
            Log out
          </Button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-h-screen lg:ml-56">
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          {children(session)}
        </main>
      </div>
    </div>
  );
}
