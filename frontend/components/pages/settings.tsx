"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, CircleHelp, Database, Moon, Network, RotateCw, Shield, ShieldAlert, Sun } from "lucide-react";
import { PageHeader, Panel, StatusBadge, ErrorPanel, LoadingRows } from "@/components/shared";
import { api, appConfig } from "@/lib/api/client";
import type { HealthStatus } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

const services: { key: keyof HealthStatus; label: string; description: string }[] = [
  { key: "backend", label: "API backend", description: "FastAPI health and alert endpoints" },
  { key: "agent", label: "Investigation agent", description: "Agent execution and report generation" },
  { key: "rag", label: "AML knowledge retrieval", description: "Vector search service and indexed guidance" },
  { key: "queue", label: "Task queue", description: "Runs execute in-process; no background queue is configured" },
];

export function SettingsPage() {
  const [compact, setCompact] = useState(false);
  const [notifications, setNotifications] = useState(true);
  const health = useQuery({ queryKey: ["health"], queryFn: () => api.getHealth(), refetchInterval: 30000 });
  const [theme, setTheme] = useState(typeof document !== "undefined" && document.documentElement.classList.contains("dark") ? "dark" : "light");
  function updateTheme(next: string) { setTheme(next); document.documentElement.classList.toggle("dark", next === "dark"); document.documentElement.classList.toggle("light", next !== "dark"); window.dispatchEvent(new CustomEvent("amlens-theme-change", { detail: next === "dark" })); }
  return <>
    <PageHeader eyebrow="WORKSPACE CONFIGURATION" title="Settings" description="Review service connectivity, runtime mode, and local workspace preferences." action={<button className="button-secondary" onClick={() => health.refetch()} disabled={health.isFetching}><RotateCw />Refresh health</button>} />
    <div className="two-column settings-layout">
      <Panel title="Service health" description="Health checks refresh every 30 seconds.">
        {health.isError ? <ErrorPanel message={health.error.message} onRetry={() => health.refetch()} /> : !health.data ? <LoadingRows count={4} /> : <div className="service-health-list">{services.map((service) => <div className="service-health-row" key={service.key}><span className="source-icon"><Network /></span><div className="service-health-copy"><strong>{service.label}</strong><span>{service.description}</span></div><StatusBadge status={health.data[service.key]} /></div>)}</div>}
        {health.data && <p className="field-hint">Last checked {formatDate(health.data.checked_at, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit" })}</p>}
      </Panel>
      <Panel title="Workspace configuration" description="Configuration values are loaded from the deployment environment.">
        <div className="config-list"><div className="config-row"><span className="config-icon"><Database /></span><div><strong>FastAPI base URL</strong><span className="mono">{appConfig.apiBase}</span></div><StatusBadge status="configured" /></div><div className="config-row"><span className="config-icon"><Database /></span><div><strong>RAG service URL</strong><span className="mono">{appConfig.ragBase}</span></div><StatusBadge status="configured" /></div><div className="config-row"><span className="config-icon"><Shield /></span><div><strong>Data mode</strong><span>{appConfig.mocks ? "Mock fixtures enabled — no external service calls" : "Live API mode"}</span></div><StatusBadge status={appConfig.mocks ? "warning" : "supported"} label={appConfig.mocks ? "Demo" : "Live"} /></div></div>
        <p className="field-hint">Requests go through this app&apos;s server-side proxy; set <span className="mono">AMLENS_BACKEND_URL</span> and <span className="mono">AMLENS_RAG_URL</span> on the frontend server, and build with <span className="mono">NEXT_PUBLIC_USE_MOCKS=false</span> to use live services. Never add secrets to client-visible variables.</p>
      </Panel>
    </div>
    <Panel title="Analyst preferences" description="These preferences apply to this browser session and are not persisted to the backend.">
      <div className="preferences-list"><label className="preference-row"><span className="preference-icon">{theme === "dark" ? <Moon /> : <Sun />}</span><span><strong>Appearance</strong><small>Choose a light or dark workspace theme</small></span><select className="control-select preference-select" aria-label="Appearance theme" value={theme} onChange={(event) => updateTheme(event.target.value)}><option value="light">Light</option><option value="dark">Dark</option></select></label><label className="preference-row"><span className="preference-icon"><Check /></span><span><strong>Compact table density</strong><small>Reduce row height on dense data tables</small></span><input type="checkbox" checked={compact} onChange={(event) => { setCompact(event.target.checked); document.documentElement.classList.toggle("compact-density", event.target.checked); }} /></label><label className="preference-row"><span className="preference-icon"><CircleHelp /></span><span><strong>Investigation notifications</strong><small>Show in-app notifications when runs complete</small></span><input type="checkbox" checked={notifications} onChange={(event) => setNotifications(event.target.checked)} /></label></div>
      <p className="field-hint">Notification preference is a UI placeholder until notification delivery is configured.</p>
    </Panel>
    <Panel title="About AMLens" description="A review workspace for transaction alerts; not a production monitoring or filing system.">
      <div className="scope-boundary-grid"><div><ShieldAlert /><strong>Draft support only</strong><span>AI-generated reports are advisory drafts for investigator review.</span></div><div><ShieldAlert /><strong>No autonomous decisions</strong><span>Only a human investigator can record a disposition.</span></div><div><ShieldAlert /><strong>No SAR / STR filing</strong><span>This workspace does not create or submit regulatory filings.</span></div><div><ShieldAlert /><strong>No detection or real-time monitoring</strong><span>It does not include a detection model or live transaction monitoring.</span></div></div>
    </Panel>
  </>;
}
