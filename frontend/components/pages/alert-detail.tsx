"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Clock3, FileSearch, LoaderCircle, ShieldAlert, ShieldCheck, Sparkles, Target, WalletCards } from "lucide-react";
import { CartesianGrid, Line, LineChart, ReferenceDot, Tooltip, XAxis, YAxis } from "recharts";
import { ChartContainer, type ChartConfig } from "@/components/ui/chart";
import { toast } from "sonner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader, Panel, StatusBadge, CopyableId, LoadingRows, ErrorPanel, DisclaimerCallout } from "@/components/shared";
import { api } from "@/lib/api/client";
import type { GapStatus } from "@/lib/api/types";
import { formatAccountToken, formatDate, formatMoneyString, humanize } from "@/lib/format";

const gapNames: Record<GapStatus, string> = { confirmed_missing: "Confirmed missing", not_provided: "Not provided", not_applicable: "Not applicable", available_verified: "Available / verified" };
const steps = ["Transaction Analysis", "AML Knowledge Retrieval", "Evidence Correlation", "Information Gap", "Report Drafting", "Verifier"];
const timelineChartConfig = { plotAmount: { label: "Amount paid", color: "var(--chart-1)" } } satisfies ChartConfig;

function safeEvidenceValue(key: string, value: unknown): unknown {
  if (/account/i.test(key)) return typeof value === "string" ? formatAccountToken(value) : "[redacted]";
  if (Array.isArray(value)) return value.map((item) => safeEvidenceValue(key, item));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([childKey, childValue]) => [childKey, safeEvidenceValue(childKey, childValue)]));
  return value;
}

function amountForPlot(value: string) {
  // This is a hidden chart coordinate; every visible amount uses the original decimal string.
  const [whole = "0", fraction = ""] = value.split(".");
  const cents = `${(whole || "0").replace(/^0+(?=\d)/, "")}${fraction.padEnd(2, "0").slice(0, 2)}`.replace(/^0+(?=\d)/, "");
  return Number(cents || "0");
}

export function AlertDetailPage() {
  const { alertId } = useParams<{ alertId: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [activeStep, setActiveStep] = useState(-1);
  const alertQuery = useQuery({ queryKey: ["alert", alertId], queryFn: () => api.getAlert(alertId), enabled: Boolean(alertId) });
  const investigationsQuery = useQuery({ queryKey: ["investigations"], queryFn: () => api.getInvestigations() });
  const existing = useMemo(() => investigationsQuery.data?.find((item) => item.alert_id === alertId), [investigationsQuery.data, alertId]);
  const reportQuery = useQuery({ queryKey: ["investigation-report", existing?.investigation_id], queryFn: () => api.getInvestigationReport(existing!.investigation_id), enabled: Boolean(existing && existing.execution_status !== "running") });
  const accountToken = formatAccountToken(String(alertQuery.data?.evidence.anchor_account_token ?? ""));
  const hasAccountToken = accountToken !== "Tokenized reference unavailable";
  const transactionsQuery = useQuery({ queryKey: ["account-history", accountToken], queryFn: () => api.getAccountHistory(accountToken, 100), enabled: hasAccountToken });
  const runMutation = useMutation({
    mutationFn: async () => {
      if (!alertQuery.data) throw new Error("Alert is not available.");
      setActiveStep(0);
      const investigation = existing?.execution_status === "running"
        ? { investigation_id: existing.investigation_id }
        : await api.investigateAlert(alertQuery.data.id);
      setActiveStep(1);
      await queryClient.invalidateQueries({ queryKey: ["investigations"] });
      setActiveStep(2);
      const report = await api.runInvestigation(investigation.investigation_id);
      setActiveStep(5);
      return { id: investigation.investigation_id, report };
    },
    onSuccess: ({ id }) => { queryClient.invalidateQueries({ queryKey: ["investigations"] }); router.push(`/investigations/${id}`); },
    onError: (error) => { const status = (error as Error & { status?: number }).status; setActiveStep(-1); if (!status) toast.error("Investigation could not be completed", { description: error.message }); },
  });

  if (alertQuery.isLoading) return <><PageHeader title="Alert detail" /><Panel title="Loading alert"><LoadingRows count={4} /></Panel></>;
  if (alertQuery.isError || !alertQuery.data) return <><PageHeader backHref="/alerts" title="Alert not found" description="This alert could not be loaded." /><ErrorPanel message={alertQuery.error?.message ?? "Alert not found."} onRetry={() => alertQuery.refetch()} /></>;
  const alert = alertQuery.data;
  const transactionIds = Array.isArray(alert.evidence.transaction_ids) ? alert.evidence.transaction_ids as string[] : [alert.transaction_id];
  const createdAt = String(alert.evidence.created_at);
  const amount = String(alert.evidence.amount_paid);
  const chartRows = (transactionsQuery.data ?? []).slice().sort((a, b) => a.timestamp.localeCompare(b.timestamp)).map((transaction) => ({ ...transaction, plotAmount: amountForPlot(transaction.amount_paid), isAnchor: transaction.transaction_id === alert.transaction_id }));
  const anchorPoint = chartRows.find((transaction) => transaction.isAnchor);

  return <>
    <PageHeader backHref="/alerts" eyebrow="ALERT REVIEW" title={<span className="detail-title-row"><span>{alert.id}</span><StatusBadge status={alert.rule_id} label={humanize(alert.rule_id)} /><StatusBadge status={alert.status} /></span>} description={`${humanize(alert.rule_id)} · Created ${formatDate(createdAt)}`} action={existing ? <Link className="button-secondary" href={`/investigations/${existing.investigation_id}`}>{existing.execution_status === "running" ? "Open running investigation" : "Open investigation"}<ArrowRight /></Link> : <button className="button-primary" disabled={runMutation.isPending || investigationsQuery.isLoading} onClick={() => runMutation.mutate()}>{runMutation.isPending ? <><LoaderCircle className="progress-spinner" />Running investigation…</> : <><Sparkles />Investigate with AI</>}</button>} />
    {runMutation.isPending && <Panel title="Investigation in progress" description="The agent is preparing a draft report. No decision will be made automatically."><div className="run-steps">{steps.map((label, index) => <div className={`run-step ${index < activeStep ? "done" : index === activeStep ? "active" : ""}`} key={label}><span className="step-indicator">{index < activeStep ? <ShieldCheck /> : index === activeStep ? <LoaderCircle className="progress-spinner" /> : index + 1}</span>{label}</div>)}</div></Panel>}
    {runMutation.isError && <div className={`investigation-run-error ${(runMutation.error as Error & { status?: number }).status === 503 ? "service-error" : ""}`} role="alert"><div><strong>{(runMutation.error as Error & { status?: number }).status === 409 ? "Investigation already running or linked elsewhere" : (runMutation.error as Error & { status?: number }).status === 503 ? "Agent service unavailable" : "Investigation could not be completed"}</strong><p>{runMutation.error.message}</p></div><button type="button" className="button-secondary" onClick={() => runMutation.mutate()}>Retry run</button></div>}
    <div className="detail-layout" style={{ marginTop: 13 }}>
      <div className="detail-main">
        <Panel title="Alert summary" description={alert.description}>
          <div className="detail-summary-grid">
            <div className="detail-summary-item"><span>Transaction amount</span><strong className="detail-amount">{formatMoneyString(amount, String(alert.evidence.currency))}</strong></div>
            <div className="detail-summary-item"><span>Anchor account</span><strong className="mono">{accountToken}</strong></div>
            <div className="detail-summary-item"><span>Monitoring rule</span><strong>{humanize(alert.rule_id)}</strong></div>
            <div className="detail-summary-item"><span>Payment rail</span><strong>{String(alert.evidence.payment_format)}</strong></div>
          </div>
          <div className="report-meta"><span className="subtle">Alert ID</span><CopyableId value={alert.id} /><span className="subtle">Primary transaction</span><CopyableId value={alert.transaction_id} /></div>
        </Panel>
        <Panel title="Evidence" description="The supplied evidence payload, rendered as labeled fields with account identifiers protected.">
          <dl className="alert-evidence-grid">{Object.entries(alert.evidence).map(([key, value]) => { const safeValue = safeEvidenceValue(key, value); const rendered = safeValue === null || safeValue === undefined ? "Not supplied" : typeof safeValue === "object" ? JSON.stringify(safeValue) : String(safeValue); return <div className="alert-evidence-item" key={key}><dt>{humanize(key)}</dt><dd className={/token|transaction|account/i.test(key) ? "mono" : ""}>{rendered}</dd></div>; })}</dl>
        </Panel>
        <Panel title="Related transactions" description="Account history around the alert, with the triggering transaction highlighted.">
          <Tabs defaultValue="transactions" className="tabs-strip">
            <TabsList><TabsTrigger value="transactions">Transaction history</TabsTrigger><TabsTrigger value="signals">Alert signals</TabsTrigger><TabsTrigger value="report">Investigation draft</TabsTrigger></TabsList>
            <TabsContent value="transactions">{transactionsQuery.isLoading ? <LoadingRows count={4} /> : transactionsQuery.isError ? <ErrorPanel message={transactionsQuery.error.message} onRetry={() => transactionsQuery.refetch()} /> : <div className="section-stack"><div className="timeline-chart-heading"><strong>Amount paid over time</strong><span className="timeline-key"><i />Alert transaction</span></div>{chartRows.length ? <ChartContainer config={timelineChartConfig} className="transaction-timeline"><LineChart accessibilityLayer data={chartRows} margin={{ top: 10, right: 16, left: 4, bottom: 0 }}><CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" /><XAxis dataKey="timestamp" tickFormatter={(value) => formatDate(String(value), { month: "short", day: "numeric" })} tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} minTickGap={28} /><YAxis hide domain={["dataMin", "dataMax"]} /><Tooltip content={({ active, payload }) => { if (!active || !payload?.length) return null; const point = payload[0]?.payload as typeof chartRows[number] | undefined; return point ? <div className="timeline-tooltip"><strong>{formatDate(point.timestamp, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" })}</strong><span>{formatMoneyString(point.amount_paid, point.payment_currency)}</span>{point.isAnchor && <em>Alert transaction</em>}</div> : null; }} /><Line dataKey="plotAmount" type="monotone" stroke="var(--color-plotAmount)" strokeWidth={2} dot={({ cx, cy, payload }) => cx == null || cy == null ? null : <circle cx={cx} cy={cy} r={payload?.isAnchor ? 5 : 3} fill={payload?.isAnchor ? "var(--accent-amber)" : "var(--color-plotAmount)"} stroke="var(--background)" strokeWidth={2} />} activeDot={{ r: 5 }} />{anchorPoint && <ReferenceDot x={anchorPoint.timestamp} y={anchorPoint.plotAmount} r={7} fill="var(--accent-amber)" stroke="var(--background)" strokeWidth={3} />}</LineChart></ChartContainer> : <div className="empty-state"><strong>No transaction history</strong><p>No related transaction records were returned.</p></div>}<div className="table-wrap"><table className="data-table compact transaction-table" aria-label="Related transaction history"><thead><tr><th>Transaction ID</th><th>Timestamp</th><th>Sender token</th><th>Receiver token</th><th>Amount paid</th><th>Payment currency</th><th>Amount received</th><th>Receiving currency</th><th>Payment format</th></tr></thead><tbody>{chartRows.map((txn) => <tr key={txn.transaction_id} className={txn.isAnchor ? "anchor-transaction-row" : ""}><td><div className="transaction-id-cell"><CopyableId value={txn.transaction_id} />{txn.isAnchor && <span className="transaction-anchor-label">Alert transaction</span>}</div></td><td>{formatDate(txn.timestamp, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" })}</td><td className="mono">{txn.sender_token}</td><td className="mono">{txn.receiver_token}</td><td className="tabular-nums">{formatMoneyString(txn.amount_paid, txn.payment_currency)}</td><td>{txn.payment_currency}</td><td className="tabular-nums">{formatMoneyString(txn.amount_received, txn.receiving_currency)}</td><td>{txn.receiving_currency}</td><td>{txn.payment_format}</td></tr>)}</tbody></table></div></div>}</TabsContent>
            <TabsContent value="signals"><div className="three-column"><div className="help-item"><Target /><div><strong>Rule match</strong><p>{humanize(alert.rule_id)} fired for this transaction. Compare the rule threshold against customer context.</p></div></div><div className="help-item"><WalletCards /><div><strong>Observed window</strong><p>{String(alert.evidence.observed_window ?? "Not supplied")} · Use account history to validate timing.</p></div></div><div className="help-item"><ShieldAlert /><div><strong>Review note</strong><p>A rule match is a screening signal and is not proof of suspicious activity.</p></div></div></div><div style={{ marginTop: 12 }}><span className="field-label">Linked transaction references</span><div className="inline-row">{transactionIds.map((id) => <CopyableId key={id} value={id} />)}</div></div></TabsContent>
            <TabsContent value="report">{reportQuery.isLoading ? <LoadingRows count={4} /> : reportQuery.isError ? <div className="empty-state"><span className="empty-icon"><FileSearch /></span><strong>No investigation draft yet</strong><p>Run an investigation to create an evidence-linked draft for human review.</p><button className="button-primary" onClick={() => runMutation.mutate()}><Sparkles />Start investigation</button></div> : reportQuery.data ? <div className="section-stack"><DisclaimerCallout>{reportQuery.data.report.human_review_disclaimer}</DisclaimerCallout><div className="inline-row"><StatusBadge status={reportQuery.data.execution_status} label={`Run ${reportQuery.data.execution_status}`} /><StatusBadge status={reportQuery.data.verification.passed ? "supported" : "warning"} label={reportQuery.data.verification.passed ? "Verified structure" : "Verification issues"} /><Link className="inline-link" href={`/investigations/${reportQuery.data.investigation_id}`}>Open full review <ArrowRight /></Link></div><p className="subtle">The investigation draft is advisory. A human analyst must review the evidence and record any final disposition.</p></div> : <p className="field-hint">No report available.</p>}</TabsContent>
          </Tabs>
        </Panel>
      </div>
      <aside className="detail-side" aria-label="Alert context">
        <Panel title="Alert metadata"><div className="health-list"><div className="health-list-row"><span className="subtle">Alert status</span><StatusBadge status={alert.status} /></div><div className="health-list-row"><span className="subtle">Rule ID</span><span className="mono">{alert.rule_id}</span></div><div className="health-list-row"><span className="subtle">Received</span><span>{formatDate(createdAt, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span></div><div className="health-list-row"><span className="subtle">Related records</span><strong>{transactionIds.length} transactions</strong></div></div></Panel>
        {existing && <Panel title="Latest investigation" description="Human review status"><div className="health-list"><div className="health-list-row"><span className="subtle">Investigation</span><CopyableId value={existing.investigation_id} /></div><div className="health-list-row"><span className="subtle">Run status</span><StatusBadge status={existing.execution_status} /></div><div className="health-list-row"><span className="subtle">Decision</span><strong>{existing.decision?.decision ?? "Not recorded"}</strong></div></div></Panel>}
        <Panel title="Investigator checklist"><div className="health-list"><div className="health-list-row"><span>Review linked transactions</span><ShieldCheck style={{ width: 13, height: 13, color: "var(--accent-teal)" }} /></div><div className="health-list-row"><span>Validate customer context</span><Clock3 style={{ width: 13, height: 13, color: "var(--muted-foreground)" }} /></div><div className="health-list-row"><span>Record rationale</span><Clock3 style={{ width: 13, height: 13, color: "var(--muted-foreground)" }} /></div></div></Panel>
      </aside>
    </div>
  </>;
}
