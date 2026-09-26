"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { getSession } from "@/lib/session";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace(getSession() ? "/campaigns" : "/login");
  }, [router]);
  return <main className="min-h-screen bg-[#f8f1e9]" />;
}
