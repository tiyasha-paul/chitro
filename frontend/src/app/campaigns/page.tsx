"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Badge, Button, Card, EmptyState, LoadingState, PageHeader, StatusBadge } from "@/components/ui";
import { api, ApiError, type Campaign } from "@/lib/api";
import { getSession } from "@/lib/session";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCampaigns = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const session = getSession();
      if (!session) return;
      const data = await api.listCampaigns(session.access_token);
      setCampaigns(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load campaigns");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  // Helper to format date
  const formatDate = (isoString: string) => {
    try {
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric"
      }).format(new Date(isoString));
    } catch {
      return isoString;
    }
  };

  return (
    <AppShell requireAuth>
      <div className="max-w-5xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-8">
        <PageHeader
          eyebrow="CONTENT OPERATIONS"
          title="Campaigns"
          description="From brief to published content and measurable learning."
          action={
            <Button asChild>
              <Link href="/campaigns/new">New Campaign</Link>
            </Button>
          }
        />

        {loading ? (
          <LoadingState message="Loading your campaigns..." />
        ) : error ? (
          <div className="p-4 bg-danger/10 text-danger rounded-xl">
            {error}
            <div className="mt-2">
              <Button variant="outline" size="sm" onClick={loadCampaigns}>
                Try again
              </Button>
            </div>
          </div>
        ) : campaigns.length === 0 ? (
          <EmptyState
            title="No campaigns yet"
            description="Create your first campaign to start briefing and generating content."
            action={
              <Button asChild>
                <Link href="/campaigns/new">Create Campaign</Link>
              </Button>
            }
          />
        ) : (
          <div className="grid gap-4">
            {/* Desktop Header */}
            <div className="hidden md:grid md:grid-cols-12 gap-4 px-6 py-2 text-xs font-medium text-text-muted uppercase tracking-wider border-b border-border">
              <div className="col-span-4">Campaign</div>
              <div className="col-span-3">Objective & Audience</div>
              <div className="col-span-3">Status</div>
              <div className="col-span-2 text-right">Created</div>
            </div>

            {/* Campaign List */}
            {campaigns.map((campaign) => (
              <Link key={campaign.id} href={`/campaigns/${campaign.id}`} className="block group">
                <Card className="px-6 py-5 transition-colors group-hover:bg-surface-alt border border-border group-hover:border-border-strong rounded-xl">
                  <div className="flex flex-col md:grid md:grid-cols-12 gap-4 md:items-center">

                    {/* Name & Basic Info */}
                    <div className="col-span-4">
                      <h3 className="font-serif text-xl text-text mb-1 group-hover:text-brand transition-colors">
                        {campaign.name}
                      </h3>
                      <div className="text-sm text-text-muted">
                        {campaign.posts?.length || 0} {(campaign.posts?.length === 1) ? 'post' : 'posts'}
                      </div>
                    </div>

                    {/* Objective & Audience */}
                    <div className="col-span-3">
                      <div className="text-sm text-text line-clamp-1 mb-1">
                        {campaign.objective}
                      </div>
                      {campaign.target_audience && (
                        <div className="text-xs text-text-muted line-clamp-1">
                          Audience: {campaign.target_audience}
                        </div>
                      )}
                    </div>

                    {/* Workflow Summary / Status */}
                    <div className="col-span-3 flex flex-col items-start gap-1">
                      {campaign.posts && campaign.posts.length > 0 ? (
                        <>
                          <StatusBadge status={campaign.posts[0].status} />
                          <div className="text-xs text-text-muted">
                            {Object.entries(
                              campaign.posts.reduce((acc, post) => {
                                acc[post.status] = (acc[post.status] || 0) + 1;
                                return acc;
                              }, {} as Record<string, number>)
                            )
                              .map(([status, count]) => `${count} ${status}`)
                              .join(", ")}
                          </div>
                        </>
                      ) : (
                        <Badge variant="secondary">Drafting</Badge>
                      )}
                    </div>

                    {/* Creation Date */}
                    <div className="col-span-2 text-sm text-text-muted md:text-right mt-2 md:mt-0">
                      {formatDate(campaign.created_at)}
                    </div>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
