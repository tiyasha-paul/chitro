"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  LoadingState,
  PageHeader,
  StatusBadge,
  Textarea,
} from "@/components/ui";
import {
  api,
  ApiError,
  type AnalyticsComparison,
  type Campaign,
  type Insight,
  type MetricSnapshot,
  type MetricSnapshotInput,
  type PerformanceReport,
  type PlatformPost,
} from "@/lib/api";

const stages = ["generated", "validated", "pending_approval", "approved", "scheduled", "published"];
const errorMessage = (value: unknown, fallback: string) =>
  value instanceof ApiError ? value.message : fallback;

function ProductTimeline({ posts }: { posts: PlatformPost[] }) {
  const statuses = new Set(posts.map((post) => post.status));
  const complete = (stage: string) =>
    stage === "brief" ||
    (stage === "generate" && posts.length > 0) ||
    (stage === "review" &&
      posts.some((post) =>
        ["pending_approval", "approved", "scheduled", "published", "rejected"].includes(post.status)
      )) ||
    (stage === "approve" &&
      posts.some((post) =>
        ["approved", "scheduled", "published"].includes(post.status)
      ));
  const stages = ["Brief", "Create", "Review", "Approve", "Schedule", "Publish", "Measure", "Learn"];

  return (
    <div className="mt-6 rounded-2xl border border-[#ead9cf] bg-[#fffaf3] p-4 sm:p-5">
      <p className="eyebrow">Campaign progress</p>
      <div className="mt-4 overflow-x-auto pb-2 -mx-1 px-1">
        <div className="grid grid-cols-8 min-w-[540px] sm:min-w-0 w-full">
          {stages.map((stage, index) => {
            const key = stage.toLowerCase() === "create" ? "generate" : stage.toLowerCase();
            const done =
              complete(key) ||
              (key === "schedule" && (statuses.has("scheduled") || statuses.has("published"))) ||
              (key === "publish" && statuses.has("published")) ||
              (key === "measure" && statuses.has("published")) ||
              (key === "learn" && statuses.has("published"));

            return (
              <div key={stage} className="relative flex flex-col items-center text-center px-1 min-w-0">
                <div className="relative flex items-center justify-center w-full h-8">
                  {index < stages.length - 1 && (
                    <div
                      className={`absolute left-1/2 w-full top-1/2 -translate-y-1/2 h-0.5 z-0 ${
                        done ? "bg-[#b75b68]" : "bg-[#dfcec3]"
                      }`}
                    />
                  )}
                  <span
                    className={`relative z-10 grid size-7 place-items-center rounded-full text-xs font-bold shrink-0 ${
                      done
                        ? "bg-[#8f1029] text-white"
                        : "border border-[#d8c6bc] bg-[#fffaf3] text-[#805d5f]"
                    }`}
                  >
                    {done ? "✓" : index + 1}
                  </span>
                </div>
                <span className="mt-2 text-[10px] sm:text-xs font-bold uppercase tracking-wider text-[#67474a] leading-tight text-center break-words max-w-full">
                  {stage}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function Report({ campaignId, token }: { campaignId: string; token: string }) {
  const [report, setReport] = useState<PerformanceReport | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  async function generate() {
    setGenerating(true);
    setError("");
    try {
      setReport(await api.generateWeeklyReport(campaignId, token));
    } catch (e: unknown) {
      setError(errorMessage(e, "The weekly report could not be generated."));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <section className="mt-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Performance report</p>
          <h2 className="mt-2 font-serif text-3xl">Weekly report</h2>
          <p className="mt-1 text-sm text-[#77595a]">
            Review what happened, what the numbers show, and what to try next.
          </p>
        </div>
        <Button disabled={generating} onClick={() => void generate()}>
          {generating ? "Generating weekly report…" : "Generate weekly report"}
        </Button>
      </div>
      {error && (
        <p role="alert" className="mt-4 rounded-xl bg-[#f7dce0] p-3 text-sm text-[#861a31]">
          {error}
        </p>
      )}
      {report && (
        <Card className="mt-6 p-6 sm:p-8 min-w-0">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <h3 className="font-serif text-2xl leading-snug break-words [overflow-wrap:anywhere] text-[#321d20]">
                {report.title}
              </h3>
              <p className="mt-1 text-sm text-[#77595a] break-words [overflow-wrap:anywhere]">
                {new Date(report.period_start).toLocaleDateString()} –{" "}
                {new Date(report.period_end).toLocaleDateString()}
              </p>
            </div>
            <div className="shrink-0 self-start">
              <Badge tone="success" className="whitespace-nowrap">Evidence checked</Badge>
            </div>
          </div>

          <section className="mt-6 rounded-2xl bg-[#fff8e8] p-5 sm:p-6 min-w-0">
            <p className="eyebrow">Executive summary</p>
            <p className="mt-2 leading-7 text-[#4f3638] break-words [overflow-wrap:anywhere]">
              {report.executive_summary}
            </p>
          </section>

          <div className="mt-6 space-y-6">
            {report.sections.map((section) => (
              <section key={section.heading} className="min-w-0">
                <h4 className="font-serif text-xl break-words [overflow-wrap:anywhere] text-[#321d20]">
                  {section.heading}
                </h4>
                <p className="mt-1 text-sm leading-6 text-[#77595a] break-words [overflow-wrap:anywhere]">
                  {section.summary}
                </p>
                {section.claims.map((claim) => (
                  <article
                    key={claim.claim_id}
                    className="mt-3 rounded-2xl border border-[#ead9cf] p-4 sm:p-5 bg-[#fffdf9] min-w-0"
                  >
                    <p className="font-medium text-[#321d20] break-words [overflow-wrap:anywhere]">{claim.text}</p>
                    <div className="mt-3 border-t border-[#ead9cf] pt-3">
                      <p className="eyebrow">Supporting data</p>
                      {claim.citations.map((citation, index) => (
                        <a
                          key={`${citation.post_id}-${citation.snapshot_id}-${index}`}
                          href={`#post-${citation.post_id}`}
                          className="mt-2 block rounded-lg bg-[#f8f1e9] px-3 py-2 text-sm text-[#67474a] hover:bg-[#f4e5dc] break-words [overflow-wrap:anywhere]"
                        >
                          View {citation.metric_field.replaceAll("_", " ")} for this post
                        </a>
                      ))}
                    </div>
                  </article>
                ))}
              </section>
            ))}
          </div>

          <section className="mt-6 border-t border-[#ead9cf] pt-6 min-w-0">
            <h4 className="font-serif text-xl break-words [overflow-wrap:anywhere] text-[#321d20]">
              Recommendations
            </h4>
            {report.recommendations.length ? (
              <ul className="mt-3 space-y-2">
                {report.recommendations.map((item) => (
                  <li
                    key={item.recommendation_id}
                    className="rounded-xl bg-[#f4ebe5] p-3 sm:p-4 text-sm break-words [overflow-wrap:anywhere]"
                  >
                    <strong className="text-[#321d20]">{item.text}</strong>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-[#77595a]">No recommendations are available for this period.</p>
            )}
          </section>
        </Card>
      )}
    </section>
  );
}

function Progress({ status }: { status: string }) {
  const current = stages.indexOf(status);
  const exceptional = status === "rejected" || status === "validation_failed";
  const labels = ["Created", "Checked", "Ready for review", "Approved", "Scheduled", "Published"];

  return (
    <div className="mt-4" aria-label="Content progress">
      <div className="overflow-x-auto pb-2 -mx-1 px-1">
        <div className="grid grid-cols-6 min-w-[460px] sm:min-w-0 w-full">
          {stages.map((stage, i) => {
            const done = current >= i;
            const lineDone = current > i;
            return (
              <div key={stage} className="relative flex flex-col items-center text-center px-1 min-w-0">
                <div className="relative flex items-center justify-center w-full h-8">
                  {i < stages.length - 1 && (
                    <div
                      className={`absolute left-1/2 w-full top-1/2 -translate-y-1/2 h-0.5 z-0 ${
                        lineDone ? "bg-[#8f1029]" : "bg-[#dfcec3]"
                      }`}
                    />
                  )}
                  <span
                    className={`relative z-10 grid size-7 place-items-center rounded-full text-xs font-bold shrink-0 ${
                      done
                        ? "bg-[#8f1029] text-white"
                        : "border border-[#d8c6bc] bg-[#fffaf3] text-[#997a77]"
                    }`}
                  >
                    {done ? "✓" : i + 1}
                  </span>
                </div>
                <span className="mt-1.5 text-[9px] sm:text-[10px] font-bold uppercase tracking-wider text-[#805d5f] leading-tight text-center break-words max-w-full">
                  {labels[i]}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      {exceptional && (
        <p className="mt-3 rounded-xl bg-[#f7dce0] px-3 py-2 text-sm font-semibold text-[#861a31]">
          {status === "rejected"
            ? "This version needs changes. Update the feedback and create a new version."
            : "This version needs another attempt. Create a new version to continue."}
        </p>
      )}
    </div>
  );
}

function Metrics({ post, token }: { post: PlatformPost; token: string }) {
  const [metrics, setMetrics] = useState<MetricSnapshot[]>([]);
  const [form, setForm] = useState<Record<string, string>>({});
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setMetrics(await api.getMetrics(post.id, token));
    } catch (e: unknown) {
      setError(errorMessage(e, "Metrics could not be loaded."));
    }
  }, [post.id, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const latest = metrics.at(-1);

  async function save() {
    const input = Object.fromEntries(
      Object.entries(form)
        .filter(([, value]) => value !== "")
        .map(([key, value]) => [key, Number(value)])
    ) as MetricSnapshotInput;
    if (!Object.keys(input).length) {
      setError("Enter at least one metric.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.recordMetrics(post.id, input, token);
      setForm({});
      setOpen(false);
      await load();
    } catch (e: unknown) {
      setError(errorMessage(e, "Metrics could not be saved."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-6 border-t border-[#ead9cf] pt-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">Performance</p>
          <p className="mt-1 text-sm text-[#77595a]">Add the latest results for this post.</p>
        </div>
        <Button variant="secondary" onClick={() => setOpen(!open)}>
          {open ? "Close metrics" : "Add metrics"}
        </Button>
      </div>
      {latest ? (
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(["impressions", "reach", "likes", "comments", "shares", "engagement_rate"] as const).map(
            (key) =>
              latest[key] !== null && (
                <div key={key} className="rounded-xl bg-[#f8f1e9] p-3 text-sm min-w-0">
                  <p className="text-xs uppercase text-[#805d5f] truncate">{key.replaceAll("_", " ")}</p>
                  <strong className="break-words">
                    {key === "engagement_rate"
                      ? `${(latest[key] * 100).toFixed(2)}%`
                      : latest[key]?.toLocaleString()}
                  </strong>
                </div>
              )
          )}
        </div>
      ) : (
        <p className="mt-4 text-sm text-[#805d5f]">No metrics recorded yet.</p>
      )}
      {open && (
        <div className="mt-5 grid gap-3 rounded-2xl bg-[#fff8e8] p-4 sm:grid-cols-3">
          {["impressions", "reach", "likes", "comments", "shares", "saves", "clicks"].map((key) => (
            <label key={key} className="block text-sm font-semibold capitalize text-[#493033]">
              {key}
              <Input
                className="mt-1"
                type="number"
                min="0"
                value={form[key] ?? ""}
                onChange={(event) => setForm({ ...form, [key]: event.target.value })}
              />
            </label>
          ))}
          <div className="flex items-end">
            <Button disabled={busy} onClick={() => void save()}>
              {busy ? "Saving…" : "Save snapshot"}
            </Button>
          </div>
        </div>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-[#861a31]">{error}</p>}
    </section>
  );
}

function PostCard({
  post,
  token,
  refresh,
}: {
  post: PlatformPost;
  token: string;
  refresh: () => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [schedule, setSchedule] = useState("");
  const [scheduling, setScheduling] = useState(false);
  const [action, setAction] = useState("");
  const [error, setError] = useState("");

  async function act(kind: "approve" | "reject" | "regenerate" | "publish") {
    if (kind === "reject" && !reason.trim()) {
      setError("Add a review reason before rejecting.");
      return;
    }
    setAction(kind);
    setError("");
    try {
      if (kind === "approve") await api.approvePost(post.id, token);
      if (kind === "reject") await api.rejectPost(post.id, reason.trim(), token);
      if (kind === "regenerate") await api.regeneratePost(post.id, token);
      if (kind === "publish") await api.publishPost(post.id, token);
      setReviewing(false);
      await refresh();
    } catch (e: unknown) {
      setError(errorMessage(e, "This workflow action could not be completed."));
    } finally {
      setAction("");
    }
  }

  async function schedulePost() {
    if (!schedule) {
      setError("Choose a future date and time.");
      return;
    }
    setScheduling(true);
    setError("");
    try {
      await api.schedulePost(post.id, new Date(schedule).toISOString(), token);
      await refresh();
    } catch (e: unknown) {
      setError(errorMessage(e, "Scheduling failed."));
    } finally {
      setScheduling(false);
    }
  }

  const pending = post.status === "pending_approval";
  const retry = post.status === "rejected" || post.status === "validation_failed";

  return (
    <Card className="overflow-hidden p-0 min-w-0">
      <article id={`post-${post.id}`}>
        <header className="border-b border-[#ead9cf] bg-[#fffaf3] px-4 sm:px-6 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex flex-wrap items-center gap-2 min-w-0">
              <StatusBadge status={post.status} />
              <Badge>{post.platform} · {post.language}</Badge>
            </div>
            {post.generation_attempt > 1 && (
              <span className="text-sm font-semibold text-[#805d5f] shrink-0">
                Version {post.generation_attempt}
              </span>
            )}
          </div>
          <Progress status={post.status} />
        </header>
        <div className="px-4 sm:px-6 py-6 min-w-0">
          {post.hook && (
            <p className="font-serif text-2xl leading-snug break-words [overflow-wrap:anywhere]">
              {post.hook}
            </p>
          )}
          {post.caption && (
            <p className="mt-4 whitespace-pre-wrap leading-7 text-[#4f3638] break-words [overflow-wrap:anywhere]">
              {post.caption}
            </p>
          )}
          {post.hashtags && (
            <p className="mt-4 text-sm font-semibold text-[#8f1029] break-words [overflow-wrap:anywhere]">
              {post.hashtags.join(" ")}
            </p>
          )}
          {post.cta && (
            <p className="mt-3 border-l-2 border-[#f0c85a] pl-3 text-sm break-words [overflow-wrap:anywhere]">
              <strong>CTA · </strong>
              {post.cta}
            </p>
          )}
          {post.rejection_reason && (
            <p className="mt-4 rounded-xl bg-[#f7dce0] p-3 text-sm text-[#861a31] break-words [overflow-wrap:anywhere]">
              <strong>Review feedback · </strong>
              {post.rejection_reason}
            </p>
          )}

          {pending && !reviewing && (
            <div className="mt-6 flex flex-wrap gap-3 border-t border-[#ead9cf] pt-5">
              <Button disabled={!!action} onClick={() => void act("approve")}>
                {action === "approve" ? "Approving…" : "Approve"}
              </Button>
              <Button variant="secondary" onClick={() => setReviewing(true)}>
                Reject with feedback
              </Button>
            </div>
          )}
          {pending && reviewing && (
            <div className="mt-6 rounded-2xl bg-[#fff8f4] p-4 sm:p-5">
              <label className="field-label" htmlFor={`reason-${post.id}`}>
                Feedback for the next attempt
              </label>
              <Textarea
                id={`reason-${post.id}`}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="CTA doesn't fit the campaign objective"
              />
              <div className="mt-3 flex flex-wrap gap-3">
                <Button disabled={!reason.trim() || !!action} onClick={() => void act("reject")}>
                  {action === "reject" ? "Rejecting…" : "Reject"}
                </Button>
                <Button variant="quiet" onClick={() => setReviewing(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
          {retry && (
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-[#ead9cf] pt-5">
              <p className="text-sm text-[#77595a]">Feedback is retained and used in the next generation.</p>
              <Button disabled={!!action} onClick={() => void act("regenerate")}>
                {action === "regenerate" ? "Regenerating…" : "Regenerate"}
              </Button>
            </div>
          )}
          {post.status === "approved" && (
            <div className="mt-6 rounded-2xl bg-[#fff8e8] p-4 sm:p-5">
              <label className="field-label" htmlFor={`schedule-${post.id}`}>
                Schedule mock publication
              </label>
              <div className="flex flex-wrap gap-3">
                <Input
                  id={`schedule-${post.id}`}
                  className="max-w-xs"
                  type="datetime-local"
                  value={schedule}
                  onChange={(e) => setSchedule(e.target.value)}
                  required
                />
                <Button disabled={scheduling} onClick={() => void schedulePost()}>
                  {scheduling ? "Scheduling…" : "Schedule"}
                </Button>
              </div>
            </div>
          )}
          {post.status === "scheduled" && (
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-[#fff8e8] p-4 sm:p-5">
              <p className="text-sm text-[#67474a]">
                Scheduled for {post.scheduled_at ? new Date(post.scheduled_at).toLocaleString() : "the selected time"}.
                This publishes through Chitro’s mock channel adapter.
              </p>
              <Button disabled={!!action} onClick={() => void act("publish")}>
                {action === "publish" ? "Mock publishing…" : "Mock publish"}
              </Button>
            </div>
          )}
          {post.status === "published" && (
            <>
              <div className="mt-6 rounded-2xl bg-[#dff0df] p-4 text-sm text-[#285f35]">
                <strong>Mock channel published.</strong>
                {post.publish_result?.url && (
                  <a className="ml-2 font-semibold underline" href={post.publish_result.url} target="_blank" rel="noreferrer">
                    View mock URL
                  </a>
                )}
              </div>
              <Metrics post={post} token={token} />
            </>
          )}
          {error && <p role="alert" className="mt-4 text-sm text-[#861a31]">{error}</p>}
          {post.generation_history?.length ? (
            <details className="mt-5 border-t border-[#ead9cf] pt-4">
              <summary className="cursor-pointer text-sm font-semibold">
                Earlier attempts ({post.generation_history.length})
              </summary>
              {post.generation_history.map((item) => (
                <p className="mt-2 text-sm" key={`${item.attempt}-${item.timestamp}`}>
                  Attempt {item.attempt}: {item.status}
                  {item.rejection_reason ? ` — ${item.rejection_reason}` : ""}
                </p>
              ))}
            </details>
          ) : null}
        </div>
      </article>
    </Card>
  );
}

function Learning({ campaignId, token }: { campaignId: string; token: string }) {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [comparison, setComparison] = useState<AnalyticsComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [saved, compared] = await Promise.all([
        api.getInsights(campaignId, token),
        api.getComparison(campaignId, token),
      ]);
      setInsights(saved);
      setComparison(compared);
    } catch (e: unknown) {
      setError(errorMessage(e, "Performance data could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [campaignId, token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function generate() {
    setGenerating(true);
    setError("");
    try {
      setInsights(await api.generateInsights(campaignId, token));
      await load();
    } catch (e: unknown) {
      setError(errorMessage(e, "Insights could not be generated."));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <section className="mt-10 space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Performance & learning</p>
          <h2 className="mt-2 font-serif text-3xl">Measure the response. Carry the learning.</h2>
        </div>
        <Button disabled={generating} onClick={() => void generate()}>
          {generating ? "Generating insight…" : "Generate insight"}
        </Button>
      </div>

      <Card className="p-5 sm:p-6 min-w-0">
        {loading ? (
          <LoadingState label="Loading performance data…" />
        ) : (
          <>
            <h3 className="font-serif text-2xl">Cross-platform comparison</h3>
            {comparison && comparison.posts.length > 1 ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {comparison.posts.map((post) => (
                  <div key={post.post_id} className="rounded-xl bg-[#f8f1e9] p-4 min-w-0">
                    <strong className="capitalize">{post.platform}</strong>
                    <p className="mt-2 text-sm text-[#77595a]">
                      Reach: {post.reach?.toLocaleString() ?? "—"} · Engagement:{" "}
                      {post.engagement_rate !== null ? `${(post.engagement_rate * 100).toFixed(2)}%` : "—"}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-[#77595a]">
                {comparison?.summary ||
                  "Publish and record comparable metrics on more than one platform to see a like-for-like comparison."}
              </p>
            )}
          </>
        )}
      </Card>

      <Card className="p-5 sm:p-6 min-w-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-serif text-2xl">Evidence-backed insights</h3>
          <span className="text-sm text-[#77595a]">No unsupported claims</span>
        </div>
        {insights.length ? (
          <div className="mt-5 space-y-4">
            {insights.map((insight) => (
              <article key={insight.id} className="rounded-2xl bg-[#fff8e8] p-5 sm:p-6 min-w-0">
                <p className="font-medium leading-6 text-[#321d20] break-words [overflow-wrap:anywhere]">{insight.summary}</p>
                <div className="mt-4 border-t border-[#ead9cf] pt-3">
                  <p className="eyebrow">Evidence</p>
                  {insight.evidence.map((evidence, index) => (
                    <p
                      className="mt-2 text-sm text-[#67474a] break-words [overflow-wrap:anywhere]"
                      key={`${evidence.post_id}-${evidence.metric_field}-${index}`}
                    >
                      Post {evidence.post_id.slice(0, 8)} · <strong>{evidence.metric_field}</strong>:{" "}
                      {typeof evidence.value === "object" ? JSON.stringify(evidence.value) : String(evidence.value)}
                    </p>
                  ))}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-[#77595a]">
            Publish content and record metrics before generating evidence-backed insights.
          </p>
        )}
        <p className="mt-6 rounded-xl bg-[#f4ebe5] p-3 text-sm text-[#67474a] leading-relaxed">
          <strong>Next brief learning:</strong> choose this campaign from the New Campaign form to carry its
          saved insights into the next generation.
        </p>
        {error && <p role="alert" className="mt-3 text-sm text-[#861a31]">{error}</p>}
      </Card>
    </section>
  );
}

function Detail({ id, token }: { id: string; token: string }) {
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [platform, setPlatform] = useState<"instagram" | "x">("instagram");
  const [language, setLanguage] = useState<"bn" | "en">("bn");

  const load = useCallback(async () => {
    setError("");
    try {
      setCampaign(await api.getCampaign(id, token));
    } catch (e: unknown) {
      setError(errorMessage(e, "This campaign could not be loaded."));
    }
  }, [id, token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function generate() {
    setGenerating(true);
    try {
      await api.generateCampaignContent(id, token, platform, language);
      await load();
    } catch (e: unknown) {
      setError(errorMessage(e, "Content generation failed."));
    } finally {
      setGenerating(false);
    }
  }

  if (!campaign && !error) return <LoadingState label="Opening campaign…" />;
  if (!campaign)
    return (
      <EmptyState
        title="Campaign not found"
        detail={error}
        action={<Button onClick={() => void load()}>Try again</Button>}
      />
    );

  return (
    <>
      <PageHeader eyebrow="Campaign workflow" title={campaign.name}>
        <div className="flex flex-wrap items-end gap-2 rounded-2xl bg-[#fff8e8] p-3">
          <label className="text-xs font-bold uppercase tracking-wider text-[#67474a]">
            Platform
            <select
              className="ml-2 rounded-lg border border-[#d8c6bc] bg-white px-2 py-2 text-sm"
              value={platform}
              onChange={(event) => setPlatform(event.target.value as "instagram" | "x")}
            >
              <option value="instagram">Instagram</option>
              <option value="x">X</option>
            </select>
          </label>
          <label className="text-xs font-bold uppercase tracking-wider text-[#67474a]">
            Language
            <select
              className="ml-2 rounded-lg border border-[#d8c6bc] bg-white px-2 py-2 text-sm"
              value={language}
              onChange={(event) => setLanguage(event.target.value as "bn" | "en")}
            >
              <option value="bn">বাংলা</option>
              <option value="en">English</option>
            </select>
          </label>
          <Button disabled={generating} onClick={() => void generate()}>
            {generating
              ? "Generating…"
              : `Generate ${platform === "x" ? "X" : "Instagram"} · ${language === "bn" ? "বাংলা" : "English"}`}
          </Button>
        </div>
      </PageHeader>

      <ProductTimeline posts={campaign.posts} />

      <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-4 items-start">
        <Card className="p-5 sm:p-6 min-w-0 min-h-[100px]">
          <strong className="block text-xs font-bold uppercase tracking-wider text-[#67474a]">
            Objective
          </strong>
          <p className="mt-2 text-sm leading-relaxed text-[#77595a] break-words [overflow-wrap:anywhere]">
            {campaign.objective || "Not recorded"}
          </p>
        </Card>
        <Card className="p-5 sm:p-6 min-w-0 min-h-[100px]">
          <strong className="block text-xs font-bold uppercase tracking-wider text-[#67474a]">
            Audience
          </strong>
          <p className="mt-2 text-sm leading-relaxed text-[#77595a] break-words [overflow-wrap:anywhere]">
            {campaign.target_audience || "Not recorded"}
          </p>
        </Card>
      </div>

      {error && <p role="alert" className="mt-5 text-[#861a31]">{error}</p>}

      <section className="mt-10">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-serif text-3xl">Content workflow</h2>
          <span className="text-sm text-[#77595a]">
            Real backend state · {campaign.posts.length} versions
          </span>
        </div>
        {campaign.posts.length ? (
          <div className="space-y-5">
            {campaign.posts.map((post) => (
              <PostCard key={post.id} post={post} token={token} refresh={load} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="The brief is ready."
            detail="Choose an Instagram or X voice in বাংলা or English to begin review."
          />
        )}
      </section>

      <Learning campaignId={id} token={token} />
      <Report campaignId={id} token={token} />
    </>
  );
}

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  return <AppShell>{(session) => <Detail id={params.id} token={session.access_token} />}</AppShell>;
}
