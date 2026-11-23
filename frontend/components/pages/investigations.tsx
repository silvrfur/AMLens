"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Search } from "lucide-react";
import { PageHeader, Panel, StatusBadge, CopyableId, ErrorPanel, LoadingRows, EmptyState } from "@/components/shared";
import { api } from "@/lib/api/client";
import { downloadCsv, formatDate } from "@/lib/format";

export function InvestigationsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const query = useQuery({ queryKey: ["investigations"], queryFn: () => api.getInvestigations() });
  const items = useMemo(() => (query.data ?? []).filter((item) => (!search || `${item.investigation_id} ${item.alert_id}`.toLowerCase().includes(search.toLowerCase())) && (status === "all" || item.status === status || item.execution_status.toUpperCase() === status)), [query.data, search, status]);
  return <>
    <PageHeader eyebrow="CASE MANAGEMENT" title="Investigations" description="Review AI-generated drafts, validation results, and human decisions. The in-memory list is marked TODO: backend list endpoint." action={<button className="button-secondary" onClick={() => downloadCsv("amlens-investigations.csv", items.map((item) => ({ investigation_id: item.investigation_id, alert_id: item.alert_id, status: item.status, execution_status: item.execution_status, verification_passed: item.verification.passed, decision: item.decision?.decision ?? "", created_at: item.created_at })))}><Download />Export CSV</button>} />
    <Panel title="Investigation records" description={`${items.length} records match the current filters`}>
      <div className="table-toolbar"><div className="toolbar-left"><label className="input-with-icon filter-search"><Search aria-hidden="true" /><input className="control-input" aria-label="Search investigation IDs" placeholder="Search investigation or alert ID…" value={search} onChange={(event) => setSearch(event.target.value)} /></label><select className="control-select" aria-label="Filter by execution status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option><option value="PENDING_AGENT">Pending agent</option><option value="RUNNING">Running</option><option value="COMPLETED">Completed</option><option value="INCOMPLETE">Incomplete</option><option value="FAILED">Failed</option><option value="APPROVE">Approved</option><option value="REJECT">Rejected</option><option value="ESCALATE">Escalated</option></select></div></div>
      {query.isLoading ? <LoadingRows count={6} /> : query.isError ? <ErrorPanel message={query.error.message} onRetry={() => query.refetch()} /> : items.length === 0 ? <EmptyState title="No investigations match" description="Try another filter or begin a review from the alert queue." action={<Link href="/alerts" className="button-secondary">Open alert queue</Link>} /> : <div className="table-wrap"><table className="data-table" aria-label="Investigations"><thead><tr><th>Investigation ID</th><th>Alert ID</th><th>Status</th><th>Execution status</th><th>Verification</th><th>Human decision</th><th>Created</th><th /></tr></thead><tbody>{items.map((item) => <tr key={item.investigation_id}><td><Link className="copyable-id" href={`/investigations/${item.investigation_id}`}>{item.investigation_id}</Link></td><td><Link className="copyable-id" href={`/alerts/${item.alert_id}`}>{item.alert_id}</Link></td><td><StatusBadge status={item.status} /></td><td><StatusBadge status={item.execution_status} /></td><td><StatusBadge status={item.verification.passed ? "supported" : item.execution_status === "failed" ? "failed" : "warning"} label={item.verification.passed ? "Passed" : item.verification.errors.length ? "Failed" : "Warnings"} /></td><td>{item.decision ? <StatusBadge status={item.decision.decision} /> : <span className="subtle">Not recorded</span>}</td><td>{formatDate(item.created_at, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" })}</td><td><Link className="inline-link" href={`/investigations/${item.investigation_id}`}>Review</Link></td></tr>)}</tbody></table></div>}
    </Panel>
  </>;
}
