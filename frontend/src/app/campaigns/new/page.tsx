"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Button, Card, Input, PageHeader, Textarea } from "@/components/ui";
import { api, ApiError, type AuthResponse, type Campaign } from "@/lib/api";
import { getSession } from "@/lib/session";

export default function NewCampaignPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Learning carry-forward state
  const [availableCampaigns, setAvailableCampaigns] = useState<Campaign[]>([]);
  const [sourceCampaignId, setSourceCampaignId] = useState("");

  const [form, setForm] = useState({
    name: "",
    title: "",
    objective: "",
    audience: "",
    genre: "",
    themes: "",
    tone: "",
    cta: "",
    releaseDate: "",
  });

  useEffect(() => {
    async function loadCampaigns() {
      try {
        const session = getSession();
        if (!session) return;
        const campaigns = await api.listCampaigns(session.access_token);
        // Filter campaigns with non-empty previous_insights
        const learningCampaigns = campaigns.filter(c => c.previous_insights && Object.keys(c.previous_insights).length > 0);
        setAvailableCampaigns(learningCampaigns);
      } catch (err) {
        console.error("Failed to load campaigns for learning:", err);
      }
    }
    loadCampaigns();
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        name: form.name || undefined,
        previous_insights: sourceCampaignId || undefined,
        brief: {
          title: form.title,
          objective: form.objective,
          audience: form.audience,
          genre: form.genre,
          key_themes: form.themes.split(',').map(t => t.trim()).filter(Boolean),
          tone: form.tone,
          cta: form.cta,
          release_date: form.releaseDate,
          language: 'bn' as const,
        },
      };

      const session = getSession();
      if (!session) {
        setError("You must be logged in to create a campaign.");
        setLoading(false);
        return;
      }

      const campaign = await api.createCampaign(payload, session.access_token);
      router.push(`/campaigns/${campaign.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to create campaign. Please try again.");
      }
      setLoading(false);
    }
  };

  const handleChange = (field: keyof typeof form) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 pb-20">
        <PageHeader
          eyebrow="NEW CAMPAIGN"
          title="Start with a brief"
          description="Chitro turns your brief into platform-specific content ready for review."
        />

        {error && (
          <div className="mb-8 p-4 bg-red-50/50 border border-red-100 rounded-md">
            <p className="text-sm font-medium text-red-800">{error}</p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 mt-8">
          {/* LEFT COLUMN - Form */}
          <div className="lg:col-span-7 xl:col-span-8">
            <form onSubmit={handleSubmit} className="space-y-8">

              {/* Campaign Identity */}
              <Card className="p-8 border-[#d8c6bc] bg-[#fffaf3] shadow-sm">
                <h3 className="text-lg font-medium text-[#321d20] mb-6 font-serif">Campaign Identity</h3>
                <div className="space-y-5">
                  <div className="field">
                    <label htmlFor="name" className="field-label text-[#493033]">
                      Campaign Name (Optional)
                    </label>
                    <Input
                      id="name"
                      placeholder="e.g. Pohela Boishakh 2025"
                      value={form.name}
                      onChange={handleChange("name")}
                      className="border-[#ead9cf] focus:border-[#8f1029]"
                    />
                    <p className="text-sm text-[#77595a] mt-1.5">
                      Internal reference name. If omitted, the brief title will be used.
                    </p>
                  </div>
                </div>
              </Card>

              {/* Content Brief */}
              <Card className="p-8 border-[#d8c6bc] bg-[#fffaf3] shadow-sm">
                <h3 className="text-lg font-medium text-[#321d20] mb-6 font-serif">Content Brief</h3>

                <div className="space-y-6">
                  <div className="field">
                    <label htmlFor="title" className="field-label text-[#493033]">
                      Title / Core Idea *
                    </label>
                    <Input
                      id="title"
                      required
                      placeholder="e.g. Traditional values in a modern world"
                      value={form.title}
                      onChange={handleChange("title")}
                      className="border-[#ead9cf] focus:border-[#8f1029]"
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="field">
                      <label htmlFor="genre" className="field-label text-[#493033]">
                        Genre *
                      </label>
                      <Input
                        id="genre"
                        required
                        placeholder="e.g. Romance, Drama, Comedy"
                        value={form.genre}
                        onChange={handleChange("genre")}
                        className="border-[#ead9cf] focus:border-[#8f1029]"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="tone" className="field-label text-[#493033]">
                        Tone *
                      </label>
                      <Input
                        id="tone"
                        required
                        placeholder="e.g. Nostalgic, Uplifting, Humorous"
                        value={form.tone}
                        onChange={handleChange("tone")}
                        className="border-[#ead9cf] focus:border-[#8f1029]"
                      />
                    </div>
                  </div>

                  <div className="field">
                    <label htmlFor="objective" className="field-label text-[#493033]">
                      Objective *
                    </label>
                    <Textarea
                      id="objective"
                      required
                      rows={3}
                      placeholder="What is the goal of this campaign?"
                      value={form.objective}
                      onChange={handleChange("objective")}
                      className="border-[#ead9cf] focus:border-[#8f1029]"
                    />
                  </div>

                  <div className="field">
                    <label htmlFor="audience" className="field-label text-[#493033]">
                      Target Audience *
                    </label>
                    <Textarea
                      id="audience"
                      required
                      rows={2}
                      placeholder="Describe the target demographic and psychographic"
                      value={form.audience}
                      onChange={handleChange("audience")}
                      className="border-[#ead9cf] focus:border-[#8f1029]"
                    />
                  </div>

                  <div className="field">
                    <label htmlFor="themes" className="field-label text-[#493033]">
                      Key Themes (comma separated) *
                    </label>
                    <Input
                      id="themes"
                      required
                      placeholder="e.g. Family, Nostalgia, Celebration"
                      value={form.themes}
                      onChange={handleChange("themes")}
                      className="border-[#ead9cf] focus:border-[#8f1029]"
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="field">
                      <label htmlFor="cta" className="field-label text-[#493033]">
                        Call to Action *
                      </label>
                      <Input
                        id="cta"
                        required
                        placeholder="e.g. Watch now, Buy today"
                        value={form.cta}
                        onChange={handleChange("cta")}
                        className="border-[#ead9cf] focus:border-[#8f1029]"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="releaseDate" className="field-label text-[#493033]">
                        Release Date/Moment *
                      </label>
                      <Input
                        id="releaseDate"
                        required
                        placeholder="e.g. Mid-April, Eid 2025"
                        value={form.releaseDate}
                        onChange={handleChange("releaseDate")}
                        className="border-[#ead9cf] focus:border-[#8f1029]"
                      />
                    </div>
                  </div>
                </div>
              </Card>

              {/* Learning Carry-forward */}
              {availableCampaigns.length > 0 && (
                <Card className="p-8 border-[#d8c6bc] bg-[#fffaf3] shadow-sm relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-1 h-full bg-[#8f1029]" />
                  <h3 className="text-lg font-medium text-[#321d20] mb-2 font-serif">Carry learning from a previous campaign</h3>
                  <p className="text-sm text-[#77595a] mb-6">
                    Saved insights from a past campaign will guide AI generation for this new brief.
                  </p>

                  <div className="field">
                    <select
                      id="sourceCampaign"
                      value={sourceCampaignId}
                      onChange={(e) => setSourceCampaignId(e.target.value)}
                      className="w-full bg-white border border-[#ead9cf] text-[#321d20] text-sm rounded-md focus:ring-[#8f1029] focus:border-[#8f1029] block p-2.5"
                    >
                      <option value="">Do not carry forward learning (Start fresh)</option>
                      {availableCampaigns.map((camp) => (
                        <option key={camp.id} value={camp.id}>
                          {camp.name || "Untitled Campaign"}
                        </option>
                      ))}
                    </select>
                  </div>

                  {sourceCampaignId && (
                    <div className="mt-4 p-4 bg-[#f8f1e9] border border-[#ead9cf] rounded-md">
                      <p className="text-sm text-[#493033]">
                        <strong>Note:</strong> Performance data and feedback insights from the selected campaign will influence the style and messaging of the generated content.
                      </p>
                    </div>
                  )}
                </Card>
              )}

              <div className="flex items-center justify-end gap-4 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => router.back()}
                  disabled={loading}
                  className="border-[#d8c6bc] text-[#493033] hover:bg-[#f8f1e9]"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={loading}
                  className="bg-[#8f1029] hover:bg-[#730d21] text-white"
                >
                  {loading ? "Creating..." : "Create Campaign"}
                </Button>
              </div>
            </form>
          </div>

          {/* RIGHT COLUMN - Sticky Sidebar */}
          <div className="lg:col-span-5 xl:col-span-4">
            <div className="sticky top-10">
              <Card className="p-8 border-[#d8c6bc] bg-[#fffaf3] shadow-sm">
                <h3 className="text-lg font-medium text-[#321d20] mb-6 font-serif">What happens next</h3>

                <div className="space-y-6 relative before:absolute before:inset-0 before:ml-3.5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-[#ead9cf]">
                  {/* Step 1 */}
                  <div className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group">
                    <div className="flex items-center justify-center w-7 h-7 rounded-full border-2 border-[#8f1029] bg-[#fffaf3] text-[#8f1029] text-xs font-bold shrink-0 z-10 shadow-sm">
                      1
                    </div>
                    <div className="w-[calc(100%-2.5rem)] md:w-[calc(50%-2rem)] p-4 rounded-md border border-[#8f1029] bg-[#fffaf3] shadow-sm ml-4 md:ml-0 md:mr-8 md:group-odd:mr-0 md:group-odd:ml-8">
                      <h4 className="font-semibold text-[#321d20] text-sm">Brief</h4>
                      <p className="text-xs text-[#77595a] mt-1">Define your campaign direction and audience</p>
                    </div>
                  </div>

                  {/* Step 2 */}
                  <div className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group">
                    <div className="flex items-center justify-center w-7 h-7 rounded-full border-2 border-[#ead9cf] bg-white text-[#805d5f] text-xs font-bold shrink-0 z-10">
                      2
                    </div>
                    <div className="w-[calc(100%-2.5rem)] md:w-[calc(50%-2rem)] p-4 rounded-md border border-[#ead9cf] bg-white ml-4 md:ml-0 md:mr-8 md:group-odd:mr-0 md:group-odd:ml-8">
                      <h4 className="font-medium text-[#493033] text-sm">Generate</h4>
                      <p className="text-xs text-[#77595a] mt-1">AI creates platform-specific content in বাংলা or English</p>
                    </div>
                  </div>

                  {/* Step 3 */}
                  <div className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group">
                    <div className="flex items-center justify-center w-7 h-7 rounded-full border-2 border-[#ead9cf] bg-white text-[#805d5f] text-xs font-bold shrink-0 z-10">
                      3
                    </div>
                    <div className="w-[calc(100%-2.5rem)] md:w-[calc(50%-2rem)] p-4 rounded-md border border-[#ead9cf] bg-white ml-4 md:ml-0 md:mr-8 md:group-odd:mr-0 md:group-odd:ml-8">
                      <h4 className="font-medium text-[#493033] text-sm">Review</h4>
                      <p className="text-xs text-[#77595a] mt-1">Approve, reject, or regenerate each piece</p>
                    </div>
                  </div>

                  {/* Step 4 */}
                  <div className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group">
                    <div className="flex items-center justify-center w-7 h-7 rounded-full border-2 border-[#ead9cf] bg-white text-[#805d5f] text-xs font-bold shrink-0 z-10">
                      4
                    </div>
                    <div className="w-[calc(100%-2.5rem)] md:w-[calc(50%-2rem)] p-4 rounded-md border border-[#ead9cf] bg-white ml-4 md:ml-0 md:mr-8 md:group-odd:mr-0 md:group-odd:ml-8">
                      <h4 className="font-medium text-[#493033] text-sm">Publish</h4>
                      <p className="text-xs text-[#77595a] mt-1">Schedule and publish through channel adapters</p>
                    </div>
                  </div>

                  {/* Step 5 */}
                  <div className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group">
                    <div className="flex items-center justify-center w-7 h-7 rounded-full border-2 border-[#ead9cf] bg-white text-[#805d5f] text-xs font-bold shrink-0 z-10">
                      5
                    </div>
                    <div className="w-[calc(100%-2.5rem)] md:w-[calc(50%-2rem)] p-4 rounded-md border border-[#ead9cf] bg-white ml-4 md:ml-0 md:mr-8 md:group-odd:mr-0 md:group-odd:ml-8">
                      <h4 className="font-medium text-[#493033] text-sm">Learn</h4>
                      <p className="text-xs text-[#77595a] mt-1">Evidence-backed insights carry into your next campaign</p>
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
