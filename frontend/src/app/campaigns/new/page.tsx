"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { Button, Card, Input, PageHeader, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

export default function NewCampaignPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", title: "", objective: "", audience: "", genre: "", themes: "", tone: "", cta: "", releaseDate: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const update = (key: keyof typeof form) => (value: string) => setForm((current) => ({ ...current, [key]: value }));

  async function submit(event: FormEvent<HTMLFormElement>, token: string) {
    event.preventDefault(); setSubmitting(true); setError("");
    try {
      const campaign = await api.createCampaign({ name: form.name || undefined, brief: { title: form.title, objective: form.objective, audience: form.audience, genre: form.genre, key_themes: form.themes.split(",").map((theme) => theme.trim()).filter(Boolean), tone: form.tone, cta: form.cta, release_date: form.releaseDate, language: "bn" } }, token);
      router.push(`/campaigns/${campaign.id}`);
    } catch (caught: unknown) { setError(caught instanceof ApiError ? caught.message : "This brief could not be created."); }
    finally { setSubmitting(false); }
  }

  return <AppShell>{(session) => <><PageHeader eyebrow={session.workspace.name} title="New campaign" /><form className="mt-8" onSubmit={(event) => void submit(event, session.access_token)}><Card className="max-w-4xl"><div className="grid gap-6 md:grid-cols-2"><label className="block md:col-span-2"><span className="field-label">Campaign name <span className="font-normal text-[#9a7676]">(optional)</span></span><Input value={form.name} onChange={(event) => update("name")(event.target.value)} placeholder="Defaults to the brief title" /></label><label className="block"><span className="field-label">Brief title</span><Input value={form.title} onChange={(event) => update("title")(event.target.value)} placeholder="e.g. Byomkesh: a new case" required /></label><label className="block"><span className="field-label">Genre</span><Input value={form.genre} onChange={(event) => update("genre")(event.target.value)} placeholder="e.g. Mystery thriller" required /></label><label className="block md:col-span-2"><span className="field-label">Objective</span><Textarea value={form.objective} onChange={(event) => update("objective")(event.target.value)} placeholder="What should this campaign make possible?" required /></label><label className="block md:col-span-2"><span className="field-label">Target audience</span><Input value={form.audience} onChange={(event) => update("audience")(event.target.value)} placeholder="Who should feel this story is for them?" required /></label><label className="block"><span className="field-label">Key themes</span><Input value={form.themes} onChange={(event) => update("themes")(event.target.value)} placeholder="Mystery, memory, family" required /><span className="mt-1 block text-xs text-[#886a69]">Separate themes with commas.</span></label><label className="block"><span className="field-label">Tone</span><Input value={form.tone} onChange={(event) => update("tone")(event.target.value)} placeholder="Tense, cinematic, intimate" required /></label><label className="block"><span className="field-label">Call to action</span><Input value={form.cta} onChange={(event) => update("cta")(event.target.value)} placeholder="Watch the trailer on hoichoi" required /></label><label className="block"><span className="field-label">Release moment</span><Input value={form.releaseDate} onChange={(event) => update("releaseDate")(event.target.value)} placeholder="This Friday" required /></label></div>{error && <p role="alert" className="mt-6 rounded-xl bg-[#f7dce0] px-4 py-3 text-sm text-[#861a31]">{error}</p>}<div className="mt-8 flex flex-wrap justify-end gap-3"><Button type="button" variant="secondary" onClick={() => router.back()}>Cancel</Button><Button type="submit" disabled={submitting}>{submitting ? "Creating campaign…" : "Create campaign"}</Button></div></Card></form></>}</AppShell>;
}
