// OBSTACK Phase C.0 — full FlowsDetail panel (commit C.4).
//
// Renders 4 panels fetched in parallel from L4 /v1/business-flows/*:
//   1. Summary (status / duration / layer counts / interrupted layer)
//   2. Sessions (matched session_ids for this business key)
//   3. Timeline (chronological events across all layers)
//   4. Evaluation (FlowEvaluationReport + OptimizationHint list)
//
// Each panel handles its own loading/error state so a slow endpoint
// doesn't block the others.

import { useCallback, useEffect, useState } from "react";
import { X, Clock, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { flowsApi, type TimelineEvent, type SessionsResponse, type SummaryResponse, type EvaluationReport } from "@/api/flows";
import { cn } from "@/lib/utils";

interface FlowsDetailProps {
  businessKey: string;
  onClose: () => void;
}

function formatTimestamp(ts: number | null): string {
  if (ts === null) return "—";
  return new Date(ts * 1000).toLocaleString();
}

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = s / 60;
  if (m < 60) return `${m.toFixed(1)}m`;
  return `${(m / 60).toFixed(1)}h`;
}

// ─── Loading / Error mini components ───────────────────────────────────

function MiniLoading({ label }: { label: string }) {
  return (
    <p className="flex items-center gap-2 text-xs text-muted-foreground">
      <Loader2 className="h-3 w-3 animate-spin" />
      {label}…
    </p>
  );
}

function MiniError({ msg }: { msg: string }) {
  return (
    <p className="flex items-center gap-2 text-xs text-red-600 dark:text-red-400">
      <AlertTriangle className="h-3 w-3" />
      {msg}
    </p>
  );
}

// ─── Sub-panels ───────────────────────────────────────────────────────

function SummaryPanel({ data, loading, error }: {
  data: SummaryResponse["summary"] | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <MiniLoading label="Loading summary" />;
  if (error) return <MiniError msg={error} />;
  if (!data) return null;
  const Icon =
    data.status === "failed" ? AlertTriangle : data.status === "running" ? Clock : CheckCircle2;
  return (
    <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
      <Field label="Status" value={
        <span className={cn(
          "inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-medium",
          data.status === "failed"
            ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
            : data.status === "running"
              ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
              : "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
        )}>
          <Icon className="h-3 w-3" />
          {data.status}
        </span>
      } />
      <Field label="Events" value={data.event_count} />
      <Field label="Duration" value={formatDuration(data.total_duration_ms)} />
      <Field
        label="Layers"
        value={Object.entries(data.layer_counts)
          .map(([k, v]) => `${k}=${v}`)
          .join(" ") || "—"}
      />
      <Field label="Started" value={formatTimestamp(data.started_at)} />
      <Field label="Completed" value={formatTimestamp(data.completed_at)} />
      <Field
        label="Interrupted at"
        value={data.interrupted_layer ?? "—"}
      />
    </div>
  );
}

function SessionsPanel({ data, loading, error }: {
  data: SessionsResponse | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <MiniLoading label="Loading sessions" />;
  if (error) return <MiniError msg={error} />;
  if (!data) return null;
  return (
    <ul className="space-y-1 text-xs">
      {data.session_ids.map((s) => (
        <li
          key={s.session_id}
          className="flex items-center justify-between rounded-md bg-secondary/40 px-2 py-1 font-mono"
        >
          <span className="truncate">{s.session_id}</span>
          <span className="ml-2 shrink-0 text-muted-foreground">
            {s.status} · {formatTimestamp(s.created_at)}
          </span>
        </li>
      ))}
      {data.session_ids.length === 0 && (
        <li className="text-muted-foreground">No sessions for this key.</li>
      )}
    </ul>
  );
}

function TimelinePanel({ data, loading, error }: {
  data: TimelineEvent[] | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <MiniLoading label="Loading timeline" />;
  if (error) return <MiniError msg={error} />;
  if (!data) return null;
  return (
    <ol className="space-y-1 text-xs">
      {data.slice(0, 30).map((ev, idx) => (
        <li
          key={`${ev.ts}-${idx}`}
          className="flex items-start gap-2 rounded-md bg-secondary/40 px-2 py-1"
        >
          <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] font-medium text-primary">
            {ev.layer}
          </span>
          <span className="flex-1">
            <span className="font-mono">{ev.event_type}</span>
            {ev.duration_ms !== null && (
              <span className="ml-2 text-muted-foreground">
                {formatDuration(ev.duration_ms)}
              </span>
            )}
          </span>
          <time className="shrink-0 text-muted-foreground">
            {formatTimestamp(ev.ts)}
          </time>
        </li>
      ))}
      {data.length === 0 && (
        <li className="text-muted-foreground">No timeline events yet.</li>
      )}
      {data.length > 30 && (
        <li className="text-center text-muted-foreground">
          … {data.length - 30} more (timeline truncated to 30 events)
        </li>
      )}
    </ol>
  );
}

function EvaluationPanel({ data, loading, error }: {
  data: EvaluationReport | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <MiniLoading label="Loading evaluation" />;
  if (error) return <MiniError msg={error} />;
  if (!data) return null;
  return (
    <div className="space-y-3 text-xs">
      <p className="font-semibold uppercase tracking-wide text-muted-foreground">
        Optimization guidance
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="Total flows" value={data.total_flows} />
        <Field
          label="Completion rate"
          value={`${(data.completion_rate * 100).toFixed(0)}%`}
        />
        <Field
          label="Status"
          value={Object.entries(data.status_counts)
            .map(([k, v]) => `${k}=${v}`)
            .join(" ") || "—"}
        />
      </div>
      {data.hints.length > 0 && (
        <ul className="space-y-1">
          {data.hints.map((h, idx) => (
            <li
              key={idx}
              className={cn(
                "rounded-md px-2 py-1",
                h.severity === "critical"
                  ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
                  : h.severity === "warn"
                    ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300"
                    : "bg-secondary/40 text-foreground",
              )}
            >
              <span className="font-mono text-[10px] uppercase tracking-wide">
                {h.severity}
              </span>
              <span className="ml-2">{h.recommendation}</span>
            </li>
          ))}
        </ul>
      )}
      {data.hints.length === 0 && (
        <p className="text-muted-foreground">No optimization hints.</p>
      )}
    </div>
  );
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableJson).join(",")}]`;
  }
  if (value !== null && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableJson(object[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value) ?? "undefined";
}

function eventIdentity(event: TimelineEvent): string {
  return stableJson([
    event.ts,
    event.layer,
    event.component,
    event.event_type,
    event.payload,
  ]);
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">{value}</dd>
    </div>
  );
}

// ─── Main panel ───────────────────────────────────────────────────────

type LoadState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; data: T }
  | { status: "error"; error: string };

function useFetcher<T>(loader: () => Promise<T>, key: string): {
  state: LoadState<T>;
  reload: () => void;
} {
  const [state, setState] = useState<LoadState<T>>({ status: "idle" });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    loader()
      .then((data) => {
        if (!cancelled) setState({ status: "ok", data });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : "request failed";
        setState({ status: "error", error: msg });
      });
    return () => {
      cancelled = true;
    };
    // `key` is the loader identity; re-running on tick triggers reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { state, reload };
}

export function FlowsDetail({ businessKey, onClose }: FlowsDetailProps) {
  const summary = useFetcher<SummaryResponse>(
    () => flowsApi.summary(businessKey),
    `summary:${businessKey}`,
  );
  const sessions = useFetcher<SessionsResponse>(
    () => flowsApi.sessions(businessKey),
    `sessions:${businessKey}`,
  );
  const timeline = useFetcher<TimelineEvent[]>(
    () => flowsApi.timeline(businessKey).then((r) => r.events),
    `timeline:${businessKey}`,
  );
  const evaluation = useFetcher<EvaluationReport>(
    () => flowsApi.evaluation(businessKey).then((r) => r.report),
    `evaluation:${businessKey}`,
  );
  const [liveStatus, setLiveStatus] = useState<"connected" | "error">("connected");

  useEffect(() => {
    const controller = new AbortController();
    const seenEvents = new Set<string>();
    setLiveStatus("connected");

    void flowsApi.stream(
      businessKey,
      (event) => {
        const identity = eventIdentity(event);
        if (seenEvents.has(identity)) return;
        seenEvents.add(identity);
        summary.reload();
        timeline.reload();
        evaluation.reload();
      },
      controller.signal,
    ).catch(() => {
      if (!controller.signal.aborted) setLiveStatus("error");
    });

    return () => controller.abort();
  }, [businessKey, evaluation.reload, summary.reload, timeline.reload]);

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <h2 className="truncate font-mono text-sm font-semibold">{businessKey}</h2>
          <p
            className={liveStatus === "connected" ? "text-xs text-green-600 dark:text-green-400" : "text-xs text-red-600 dark:text-red-400"}
            role="status"
          >
            {liveStatus === "connected" ? "Live updates connected" : "Live updates unavailable"}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close detail panel"
          className="rounded-md p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </header>

      <Section title="Summary">
        <SummaryPanel
          data={summary.state.status === "ok" ? summary.state.data.summary : null}
          loading={summary.state.status === "loading"}
          error={summary.state.status === "error" ? summary.state.error : null}
        />
      </Section>

      <Section title="Sessions">
        <SessionsPanel
          data={sessions.state.status === "ok" ? sessions.state.data : null}
          loading={sessions.state.status === "loading"}
          error={sessions.state.status === "error" ? sessions.state.error : null}
        />
      </Section>

      <Section title="Timeline">
        <TimelinePanel
          data={timeline.state.status === "ok" ? timeline.state.data : null}
          loading={timeline.state.status === "loading"}
          error={timeline.state.status === "error" ? timeline.state.error : null}
        />
      </Section>

      <Section title="Evaluation">
        <EvaluationPanel
          data={evaluation.state.status === "ok" ? evaluation.state.data : null}
          loading={evaluation.state.status === "loading"}
          error={evaluation.state.status === "error" ? evaluation.state.error : null}
        />
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-md border border-border bg-card/50 p-3">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      {children}
    </section>
  );
}
