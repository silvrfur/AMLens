"use client";

import Link from "next/link";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Activity, AlertCircle, ArrowRight, CheckCircle2, CircleHelp, Clock3, FileCheck2, ShieldAlert, ShieldCheck, Upload } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { api } from "@/lib/api/client";
import { Panel, PageHeader, MetricCard, StatusBadge, ErrorPanel, LoadingRows } from "@/components/shared";
import { formatDate, humanize } from "@/lib/format";

const ruleChartConfig = {
  high_value: { label: "High value", color: "var(--chart-1)" },
  repeated_pair: { label: "Repeated pair", color: "var(--chart-2)" },
  rapid_movement_candidate: { label: "Rapid movement", color: "var(--chart-3)" },
} satisfies ChartConfig;
const statusChartConfig = {
  completed: { label: "Completed", color: "var(--chart-1)" },
  running: { label: "In progress", color: "var(--chart-2)" },
  incomplete: { label: "Incomplete", color: "var(--chart-3)" },
  failed: { label: "Failed", color: "var(--chart-4)" },
} satisfies ChartConfig;
const statusKeys = ["completed", "running", "incomplete", "failed"] as const;

export function DashboardPage() {
  const alertsQuery = useQuery({ queryKey: ["alerts", 200, 0], queryFn: () => api.getAlerts(200, 0) });
  const investigationsQuery = useQuery({ queryKey: ["investigations"], queryFn: () => api.getInvestigations() });
  const healthQuery = useQuery({ queryKey: ["health"], queryFn: () => api.getHealth(), refetchInterval: 60_000 });
  const investigations = investigationsQuery.data ?? [];
  const auditQueries = useQueries({ queries: investigations.slice(0, 4).map((item) => ({ queryKey: ["audit", item.investigation_id], queryFn: () => api.getAudit(item.investigation_id) })) });
  const alerts = alertsQuery.data?.items ?? [];
  const openCount = alerts.filter((item) => item.status === "OPEN").length;
  const pendingCount = investigations.filter((item) => item.execution_status === "running" || item.execution_status === "pending").length;
  const awaitingDecisionCount = investigations.filter((item) => item.execution_status !== "running" && item.execution_status !== "pending" && !item.decision).length;
  const decisionsCount = investigations.filter((item) => Boolean(item.decision)).length;
  const verifiedCount = investigations.filter((item) => item.verification.passed).length;
  const verificationRate = investigations.length ? Math.round((verifiedCount / investigations.length) * 100) : 0;
  const ruleData = Object.entries(alerts.reduce<Record<string, number>>((counts, item) => { counts[item.rule_id] = (counts[item.rule_id] ?? 0) + 1; return counts; }, {})).map(([rule_id, count]) => ({ rule_id, ruleKey: rule_id.toLowerCase(), label: humanize(rule_id), count }));
  const statusData = statusKeys.map((key) => ({ key, label: statusChartConfig[key].label ?? humanize(key), count: investigations.filter((item) => item.execution_status === key).length }));
  const recentActivity = auditQueries.flatMap((query, index) => (query.data ?? []).map((event) => ({ ...event, investigationId: investigations[index]?.investigation_id ?? "" }))).sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 6);
  const health = healthQuery.data;

  return <>
    <PageHeader eyebrow="AML OPERATIONS" title="Compliance overview" description="Current transaction-alert workload, agent activity, and service health." action={<Link className="button-primary" href="/upload"><Upload />Upload transactions</Link>} />
    <div className="metric-grid metric-grid-five">
      <MetricCard label="Open alerts" value={alertsQuery.isLoading || alertsQuery.isError ? "—" : String(openCount)} detail="Awaiting review · latest 200 loaded" icon={<AlertCircle />} accent="accent-amber" />
      <MetricCard label="Pending agent run" value={investigationsQuery.isLoading || investigationsQuery.isError ? "—" : String(pendingCount)} detail="Queued or running" icon={<Activity />} accent="accent-blue" />
      <MetricCard label="Reports awaiting decision" value={investigationsQuery.isLoading || investigationsQuery.isError ? "—" : String(awaitingDecisionCount)} detail="Human review required" icon={<FileCheck2 />} />
      <MetricCard label="Decisions recorded" value={investigationsQuery.isLoading || investigationsQuery.isError ? "—" : String(decisionsCount)} detail="Investigator dispositions" icon={<CheckCircle2 />} accent="accent-teal" />
      <MetricCard label="Verification pass rate" value={investigationsQuery.isLoading || investigationsQuery.isError ? "—" : `${verificationRate}%`} detail={`${verifiedCount} of ${investigations.length} reports passed`} icon={<ShieldCheck />} accent="accent-teal" />
    </div>
    <div className="dashboard-grid">
      <Panel title="Alerts by rule" description={`Distribution across ${alerts.length} loaded alerts (up to 200)`} action={<Link href="/alerts" className="inline-link">Open queue <ArrowRight /></Link>}>
        {alertsQuery.isLoading ? <LoadingRows count={4} /> : alertsQuery.isError ? <ErrorPanel message={alertsQuery.error.message} onRetry={() => alertsQuery.refetch()} /> : ruleData.length ? <ChartContainer config={ruleChartConfig} className="chart-shell">
          <BarChart accessibilityLayer data={ruleData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="count" name="Alerts" radius={[4, 4, 0, 0]}>{ruleData.map((item) => <Cell key={item.rule_id} fill={`var(--color-${item.ruleKey})`} />)}</Bar>
          </BarChart>
        </ChartContainer> : <div className="empty-state"><strong>No alert data</strong><p>Alerts appear here after transactions are evaluated.</p></div>}
      </Panel>
      <Panel title="Investigations by status" description="Execution status for the current case set">
        {investigationsQuery.isLoading ? <LoadingRows count={4} /> : investigationsQuery.isError ? <ErrorPanel message={investigationsQuery.error.message} onRetry={() => investigationsQuery.refetch()} /> : investigations.length ? <div className="donut-layout"><ChartContainer config={statusChartConfig} className="donut-chart">
          <PieChart accessibilityLayer><ChartTooltip content={<ChartTooltipContent />} /><Pie data={statusData} dataKey="count" nameKey="label" innerRadius={54} outerRadius={82} paddingAngle={3} stroke="none">{statusData.map((item) => <Cell key={item.key} fill={`var(--color-${item.key})`} />)}</Pie></PieChart>
        </ChartContainer><div className="donut-legend">{statusData.map((item) => <div className="donut-legend-row" key={item.key}><span><i style={{ background: `var(--chart-${statusKeys.indexOf(item.key) + 1})` }} />{item.label}</span><strong>{item.count}</strong></div>)}</div></div> : <div className="empty-state"><CircleHelp /><strong>No investigations yet</strong><p>Start an investigation from an alert detail page.</p></div>}
      </Panel>
    </div>
    <div className="dashboard-grid dashboard-grid-bottom">
      <Panel title="Recent activity" description="Latest audit events across investigations" action={<Link href="/audit" className="inline-link">View audit trail <ArrowRight /></Link>}>
        {investigationsQuery.isLoading || auditQueries.some((query) => query.isLoading) ? <LoadingRows count={4} /> : investigationsQuery.isError ? <ErrorPanel message={investigationsQuery.error.message} onRetry={() => investigationsQuery.refetch()} /> : auditQueries.some((query) => query.isError) ? <ErrorPanel message={auditQueries.find((query) => query.isError)?.error?.message ?? "Audit events could not be loaded."} onRetry={() => auditQueries.forEach((query) => { void query.refetch(); })} /> : recentActivity.length ? <div className="activity-feed">{recentActivity.map((event) => <Link className="activity-feed-row" href={`/investigations/${event.investigationId}`} key={event.event_id}><span className={`activity-feed-icon ${event.action === "DECISION_RECORDED" ? "success" : ""}`}>{event.action === "DECISION_RECORDED" ? <CheckCircle2 /> : event.action.includes("FAILED") ? <ShieldAlert /> : <Clock3 />}</span><span className="activity-feed-copy"><strong>{humanize(event.action)}</strong><small>{event.details.analyst_id ? `Analyst ${String(event.details.analyst_id)}` : event.details.actor ? String(event.details.actor) : "System"} · {event.investigationId}</small></span><time>{formatDate(event.created_at, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</time></Link>)}</div> : <div className="empty-state"><CircleHelp /><strong>No audit activity</strong><p>Investigation events will appear here.</p></div>}
      </Panel>
      <Panel title="System health" description="Live status from GET /health" action={<Activity aria-hidden="true" />}>
        {healthQuery.isLoading ? <LoadingRows count={4} /> : healthQuery.isError ? <ErrorPanel message={healthQuery.error.message} onRetry={() => healthQuery.refetch()} /> : health ? <div className="health-list">{(["backend", "agent", "rag", "queue"] as const).map((key) => <div className="health-list-row" key={key}><span>{key === "backend" ? "Backend API" : key === "agent" ? "Agent service" : key === "rag" ? "RAG service" : "Azure Service Bus queue"}</span><StatusBadge status={health[key]} /></div>)}<p className="field-hint">Last checked {formatDate(health.checked_at, { hour: "numeric", minute: "2-digit", second: "2-digit" })}</p></div> : null}
      </Panel>
    </div>
  </>;
}
