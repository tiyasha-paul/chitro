"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { Badge, Button, Card, EmptyState, LoadingState, PageHeader, StatusBadge, Textarea } from "@/components/ui";
import { api, ApiError, type Campaign, type PlatformPost } from "@/lib/api";

const workflowStages = ["generated", "validated", "pending_approval", "approved", "scheduled", "published"];

function WorkflowProgress({ status }: { status: string }) {
  const currentStage = workflowStages.indexOf(status);
  const exception = status === "rejected" || status === "validation_failed";
  return <div aria-label={`Workflow status: ${status}`} className="mt-5"><div className="flex overflow-x-auto pb-2">{workflowStages.map((stage, index) => {
    const reached = currentStage >= index;
    return <div key={stage} className="flex min-w-24 flex-1 items-center last:flex-none"><div className={`grid size-7 shrink-0 place-items-center rounded-full border text-xs font-bold ${reached ? "border-[#8f1029] bg-[#8f1029] text-white" : "border-[#d8c6bc] bg-[#fffdf9] text-[#997a77]"}`}>{reached ? "✓" : index + 1}</div>{index < workflowStages.length - 1 && <div className={`h-px min-w-4 flex-1 ${reached && currentStage > index ? "bg-[#8f1029]" : "bg-[#dfcec3]"}`} />}</div>;
  })}</div><div className="mt-1 flex min-w-[38rem] justify-between text-[10px] font-bold uppercase tracking-[0.1em] text-[#805d5f]">{workflowStages.map((stage) => <span key={stage} className="w-24 text-center">{stage.replaceAll("_", " ")}</span>)}</div>{exception && <p className="mt-3 rounded-xl bg-[#f7dce0] px-3 py-2 text-sm font-semibold text-[#861a31]">{status === "rejected" ? "Review rejected this attempt. Regenerate to create a new version." : "Validation found issues in this attempt. Regenerate to try again."}</p>}</div>;
}

function PostCard({ post, token, onRefresh }: { post: PlatformPost; token: string; onRefresh: () => Promise<void> }) {
  const [reviewing, setReviewing] = useState(false);
  const [reason, setReason] = useState("");
  const [action, setAction] = useState<"approve" | "reject" | "regenerate" | null>(null);
  const [error, setError] = useState("");
  const pendingApproval = post.status === "pending_approval";
  const canRegenerate = post.status === "rejected" || post.status === "validation_failed";

  async function runAction(kind: "approve" | "reject" | "regenerate") {
    if (kind === "reject" && !reason.trim()) {
      setError("Add a review reason before rejecting this version.");
      return;
    }
    setAction(kind); setError("");
    try {
      if (kind === "approve") await api.approvePost(post.id, token);
      if (kind === "reject") await api.rejectPost(post.id, reason.trim(), token);
      if (kind === "regenerate") await api.regeneratePost(post.id, token);
      setReviewing(false); setReason("");
      await onRefresh();
    } catch (caught: unknown) {
      setError(caught instanceof ApiError ? caught.message : "This workflow action could not be completed.");
    } finally { setAction(null); }
  }

  return <Card className="overflow-hidden p-0"><article><header className="border-b border-[#ead9cf] bg-[#fffaf3] px-6 py-5"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap items-center gap-2"><StatusBadge status={post.status} /><Badge>{post.platform} · {post.language}</Badge></div><span className="text-sm font-semibold text-[#805d5f]">Generation attempt {post.generation_attempt}</span></div><WorkflowProgress status={post.status} /></header><div className="px-6 py-6">{post.hook && <p className="font-serif text-2xl leading-snug text-[#321d20]">{post.hook}</p>}{post.caption && <p className="mt-5 whitespace-pre-wrap leading-7 text-[#4f3638]">{post.caption}</p>}{post.hashtags && <p className="mt-5 text-sm font-semibold text-[#8f1029]">{post.hashtags.join(" ")}</p>}{post.cta && <p className="mt-4 border-l-2 border-[#f0c85a] pl-3 text-sm text-[#67474a]"><span className="font-semibold">CTA · </span>{post.cta}</p>}{post.rejection_reason && <section className="mt-5 rounded-2xl bg-[#f7dce0] p-4 text-sm text-[#861a31]"><h3 className="font-semibold">Review feedback</h3><p className="mt-1">{post.rejection_reason}</p></section>}
        {pendingApproval && !reviewing && <div className="mt-7 flex flex-wrap gap-3 border-t border-[#ead9cf] pt-5"><Button disabled={action !== null} onClick={() => void runAction("approve")}>{action === "approve" ? "Approving…" : "Approve content"}</Button><Button variant="secondary" disabled={action !== null} onClick={() => setReviewing(true)}>Reject with feedback</Button></div>}
        {pendingApproval && reviewing && <form className="mt-7 rounded-2xl border border-[#e5c7c5] bg-[#fff8f4] p-5" onSubmit={(event) => { event.preventDefault(); void runAction("reject"); }}><label htmlFor={`reason-${post.id}`} className="field-label">What should change in the next generation?</label><Textarea id={`reason-${post.id}`} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="CTA doesn't fit the campaign objective" required autoFocus /><div className="mt-4 flex flex-wrap gap-3"><Button type="submit" disabled={action !== null || !reason.trim()}>{action === "reject" ? "Sending feedback…" : "Reject this version"}</Button><Button type="button" variant="quiet" disabled={action !== null} onClick={() => { setReviewing(false); setError(""); }}>Cancel</Button></div></form>}
        {canRegenerate && <div className="mt-7 flex flex-wrap items-center justify-between gap-3 border-t border-[#ead9cf] pt-5"><p className="max-w-md text-sm text-[#77595a]">Regeneration keeps this feedback in the workflow and creates a distinct new attempt.</p><Button disabled={action !== null} onClick={() => void runAction("regenerate")}>{action === "regenerate" ? "Regenerating…" : "Regenerate content"}</Button></div>}
        {error && <p role="alert" className="mt-5 rounded-xl bg-[#f7dce0] px-4 py-3 text-sm text-[#861a31]">{error}</p>}
        {post.generation_history && post.generation_history.length > 0 && <details className="mt-6 border-t border-[#ead9cf] pt-4"><summary className="cursor-pointer text-sm font-semibold text-[#67474a]">Earlier attempts ({post.generation_history.length})</summary><ul className="mt-3 space-y-3">{post.generation_history.map((attempt) => <li key={`${attempt.attempt}-${attempt.timestamp}`} className="rounded-xl bg-[#f8f1e9] p-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">Attempt {attempt.attempt}</span><StatusBadge status={attempt.status} /></div>{attempt.rejection_reason && <p className="mt-2 text-[#861a31]">Feedback: {attempt.rejection_reason}</p>}</li>)}</ul></details>}
      </div></article></Card>;
}

function CampaignDetail({ id, token }: { id: string; token: string }) {
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const load = useCallback(async () => { setError(""); try { setCampaign(await api.getCampaign(id, token)); } catch (caught: unknown) { setError(caught instanceof ApiError ? caught.message : "This campaign could not be loaded."); } }, [id, token]);
  useEffect(() => { void load(); }, [load]);
  async function generate() { setGenerating(true); setError(""); try { await api.generateCampaignContent(id, token); await load(); } catch (caught: unknown) { setError(caught instanceof ApiError ? caught.message : "Content generation failed."); } finally { setGenerating(false); } }

  if (!campaign && !error) return <LoadingState label="Opening campaign…" />;
  if (!campaign) return <EmptyState title="Campaign not found" detail={error || "It may have been moved or you may not have access to it."} action={<Button onClick={() => void load()}>Try again</Button>} />;
  const payload = campaign.brief_payload;
  return <><PageHeader eyebrow="Campaign workflow" title={campaign.name}><Button onClick={() => void generate()} disabled={generating}>{generating ? "Generating content…" : "Generate content"}</Button></PageHeader>{error && <p role="alert" className="mt-6 rounded-xl bg-[#f7dce0] px-4 py-3 text-sm text-[#861a31]">{error}</p>}<div className="mt-8 grid gap-6 lg:grid-cols-[0.9fr_1.5fr]"><aside className="space-y-6"><Card><p className="eyebrow">Brief direction</p><dl className="mt-5 space-y-5 text-sm"><div><dt className="font-semibold text-[#493033]">Objective</dt><dd className="mt-1 leading-6 text-[#77595a]">{campaign.objective || "Not recorded"}</dd></div><div><dt className="font-semibold text-[#493033]">Audience</dt><dd className="mt-1 leading-6 text-[#77595a]">{campaign.target_audience || "Not recorded"}</dd></div><div><dt className="font-semibold text-[#493033]">Context</dt><dd className="mt-1 leading-6 text-[#77595a]">{campaign.brief_context || "No context recorded"}</dd></div>{typeof payload?.genre === "string" && <div><dt className="font-semibold text-[#493033]">Genre</dt><dd className="mt-1 text-[#77595a]">{payload.genre}</dd></div>}</dl></Card><Card><p className="eyebrow">Workflow pulse</p><p className="mt-3 font-serif text-4xl">{campaign.posts.length}</p><p className="text-sm text-[#77595a]">generated content {campaign.posts.length === 1 ? "piece" : "pieces"}</p></Card></aside><section><div className="mb-4 flex items-center justify-between"><h2 className="font-serif text-3xl">Generated content</h2><span className="text-sm text-[#77595a]">Review uses real workflow state</span></div>{campaign.posts.length === 0 ? <EmptyState title="The brief is ready." detail="Generate the first platform post to begin the validation and approval workflow." /> : <div className="space-y-5">{campaign.posts.map((post) => <PostCard key={post.id} post={post} token={token} onRefresh={load} />)}</div>}</section></div></>;
}

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  return <AppShell>{(session) => <CampaignDetail id={params.id} token={session.access_token} />}</AppShell>;
}
