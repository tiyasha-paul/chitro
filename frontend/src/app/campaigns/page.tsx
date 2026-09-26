"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { Badge, Button, Card, EmptyState, LoadingState, PageHeader, StatusBadge } from "@/components/ui";
import { api, ApiError, type Campaign } from "@/lib/api";

function CampaignList({ token }: { token: string }) {
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try { setCampaigns(await api.listCampaigns(token)); }
    catch (caught: unknown) { setError(caught instanceof ApiError ? caught.message : "Campaigns could not be loaded."); }
  }, [token]);
  useEffect(() => { void load(); }, [load]);

  if (campaigns === null && !error) return <LoadingState label="Finding your campaigns…" />;
  if (error) return <EmptyState title="Your campaign room is unavailable" detail={error} action={<Button onClick={() => void load()}>Try again</Button>} />;
  if (campaigns?.length === 0) return <EmptyState title="Start with a strong brief" detail="Create your first campaign to turn an editorial idea into a generated, reviewable content workflow." action={<Link href="/campaigns/new"><Button>Create campaign</Button></Link>} />;

  return <div className="mt-8 grid gap-5 lg:grid-cols-2">{campaigns?.map((campaign) => {
    const posts = campaign.posts ?? [];
    return <Link key={campaign.id} href={`/campaigns/${campaign.id}`} className="group rounded-3xl focus:outline-none focus:ring-2 focus:ring-[#8f1029] focus:ring-offset-4"><Card className="h-full transition duration-200 group-hover:-translate-y-0.5 group-hover:border-[#bf7c80]"><div className="flex items-start justify-between gap-3"><Badge tone="warm">{posts.length} {posts.length === 1 ? "post" : "posts"}</Badge><time className="text-xs text-[#886a69]">{new Date(campaign.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</time></div><h2 className="mt-5 font-serif text-3xl leading-tight text-[#321d20]">{campaign.name}</h2><p className="mt-3 line-clamp-2 text-sm leading-6 text-[#77595a]">{campaign.objective || "No objective recorded yet."}</p><p className="mt-4 border-t border-[#f0e1d8] pt-4 text-sm text-[#6f5051]"><span className="font-semibold text-[#493033]">Audience: </span>{campaign.target_audience || "Not specified"}</p>{posts[0] && <div className="mt-4"><StatusBadge status={posts[0].status} /></div>}</Card></Link>;
  })}</div>;
}

export default function CampaignsPage() {
  return <AppShell>{(session) => <><PageHeader eyebrow={`${session.workspace.name} · Campaign room`} title="Make the next story move."><Link href="/campaigns/new"><Button>Create campaign</Button></Link></PageHeader><CampaignList token={session.access_token} /></>}</AppShell>;
}
