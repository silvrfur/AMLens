"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Download, FilePlus2, Fingerprint, PlayCircle, UserCheck, XCircle } from "lucide-react";
import { PageHeader, Panel, StatusBadge, CopyableId, ErrorPanel, LoadingRows, EmptyState } from "@/components/shared";
import { api } from "@/lib/api/client";
import { downloadCsv, formatAccountToken, formatDate } from "@/lib/format";

function EventIcon({ action }: { action: string }) {
  if (action === "CREATED") return <FilePlus2 aria-hidden="true" />;
  if (action === "AGENT_RUN_REQUESTED") return <PlayCircle aria-hidden="true" />;
  if (action === "AGENT_RUN_FINISHED") return <CheckCircle2 aria-hidden="true" />;
  if (action === "AGENT_RUN_FAILED") return <XCircle aria-hidden="true" />;
  if (action === "DECISION_RECORDED") return <UserCheck aria-hidden="true" />;
  return <Fingerprint aria-hidden="true" />;
}

function safeDetails(value: unknown): string {
  const sensitive = /account_id|account_number|iban|email|phone|customer_name|full_name|address|pan|card_number|tax_id|date_of_birth/i;
  const scrub = (input: unknown, key = ""): unknown => {
    if (typeof input === "string" && /account/i.test(key)) return formatAccountToken(input);
    if (Array.isArray(input)) return input.map((item) => scrub(item, key));
    if (input && typeof input === "object") return Object.fromEntries(Object.entries(input).map(([childKey, item]) => [childKey, sensitive.test(childKey) ? "[REDACTED]" : scrub(item, childKey)]));
    return input;
  };
  return JSON.stringify(scrub(value), null, 2);
}

export function AuditPage({ initialId = "" }: { initialId?: string }) {
  const [selected, setSelected] = useState(initialId);
  const [eventFilter, setEventFilter] = useState("all");
  const investigationsQuery = useQuery({ queryKey: ["investigations"], queryFn: () => api.getInvestigations() });
  const selectedId = selected || initialId || investigationsQuery.data?.[0]?.investigation_id || "";
  const auditQuery = useQuery({ queryKey: ["audit", selectedId], queryFn: () => api.getAudit(selectedId), enabled: Boolean(selectedId) });
  const events = useMemo(() => (auditQuery.data ?? []).filter((event) => eventFilter === "all" || event.action === eventFilter).slice().sort((a, b) => a.created_at.localeCompare(b.created_at)), [auditQuery.data, eventFilter]);
  return <>
    <PageHeader eyebrow="GOVERNANCE & CONTROLS" title="Audit trail" description="Chronological, append-only case activity for investigation runs and analyst decisions." action={<button className="button-secondary" disabled={!events.length} onClick={() => downloadCsv("amlens-audit-events.csv", events.map((event) => ({ event_id: event.event_id, investigation_id: String(event.details.investigation_id ?? selectedId), action: event.action, created_at: event.created_at, details: safeDetails(event.details) })))}><Download />Export events</button>} />
    <div className="audit-controls"><label><span className="field-label">Investigation</span><select className="control-select" aria-label="Select investigation" value={selectedId} onChange={(event) => setSelected(event.target.value)}><option value="" disabled>Select a case</option>{investigationsQuery.data?.map((item) => <option key={item.investigation_id} value={item.investigation_id}>{item.investigation_id} · {item.alert_id}</option>)}</select></label><label><span className="field-label">Event type</span><select className="control-select" aria-label="Filter audit event type" value={eventFilter} onChange={(event) => setEventFilter(event.target.value)}><option value="all">All events</option><option value="CREATED">Case created</option><option value="AGENT_RUN_REQUESTED">Agent run requested</option><option value="AGENT_RUN_FINISHED">Agent run finished</option><option value="AGENT_RUN_FAILED">Agent run failed</option><option value="DECISION_RECORDED">Decision recorded</option></select></label></div>
    <Panel title="Case events" description={selectedId ? `${events.length} event${events.length === 1 ? "" : "s"} · ${selectedId}` : "Select an investigation to view events."}>
      {investigationsQuery.isLoading || auditQuery.isLoading ? <LoadingRows count={5} /> : investigationsQuery.isError ? <ErrorPanel message={investigationsQuery.error.message} onRetry={() => investigationsQuery.refetch()} /> : auditQuery.isError ? <ErrorPanel message={auditQuery.error.message} onRetry={() => auditQuery.refetch()} /> : !selectedId ? <EmptyState title="No investigation selected" description="Start from an investigation to view its recorded events." /> : events.length === 0 ? <EmptyState title="No events found" description="No events match this filter for the selected investigation." /> : <div className="audit-timeline">{events.map((event) => <article className="audit-event" key={event.event_id}><span className={`audit-event-icon action-${event.action.toLowerCase()}`}><EventIcon action={event.action} /></span><div className="audit-event-body"><div className="audit-event-head"><strong>{event.action.replaceAll("_", " ")}</strong><span className="subtle">{formatDate(event.created_at, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit", timeZoneName: "short" })}</span></div><div className="audit-event-meta"><CopyableId value={event.event_id} /><StatusBadge status={event.action} /><span className="subtle">Actor: {String(event.details.actor ?? "system")}</span></div><details className="audit-details"><summary>View sanitized event details</summary><pre>{safeDetails(event.details)}</pre></details></div></article>)}</div>}
    </Panel>
    <p className="field-hint" style={{ marginTop: 9 }}>Event details are displayed with common direct identifiers redacted. The backend remains authoritative for audit immutability and retention controls.</p>
  </>;
}
