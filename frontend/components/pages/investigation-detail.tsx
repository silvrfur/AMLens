"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, ArrowRight, CheckCircle2, CircleHelp, Download, ExternalLink, FileCheck2, Printer, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader, Panel, StatusBadge, CopyableId, LoadingRows, ErrorPanel, DisclaimerCallout } from "@/components/shared";
import { api, appConfig } from "@/lib/api/client";
import type { Decision, EvidenceFinding, GapStatus, Guideline, ReportResponse } from "@/lib/api/types";
import { downloadJson, formatAccountToken, formatCitation, formatDate, humanize } from "@/lib/format";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const decisionSchema = z.object({ decision: z.enum(["APPROVE", "REJECT", "ESCALATE"]), rationale: z.string().trim().min(10, "Provide at least 10 characters of rationale.").max(5000, "Keep rationale under 5,000 characters."), analyst_id: z.string().trim().min(3, "Enter the signed-in analyst ID.").max(80) });
type DecisionFields = z.infer<typeof decisionSchema>;
const gapLabels: Record<GapStatus, string> = { confirmed_missing: "Confirmed missing", not_provided: "Not provided", not_applicable: "Not applicable", available_verified: "Available / verified" };
const claimLabels: Record<EvidenceFinding["claim_type"], string> = { observed_fact: "Observed fact", supported_interpretation: "Supported interpretation", unsupported_assumption: "Unsupported assumption", potential_concern: "Potential concern" };
const decisionOptions = [
  { value: "APPROVE", label: "Approve report", description: "Accept the reviewed report after verification passes.", icon: CheckCircle2 },
  { value: "REJECT", label: "Reject / close as false positive", description: "Record a human decision to close this alert.", icon: XCircle },
  { value: "ESCALATE", label: "Escalate", description: "Request additional review or context.", icon: ArrowRight },
] as const;

function safeAccountToken(value: string) { return formatAccountToken(value); }

function redactSensitiveIdentifiers(value: unknown, key = ""): unknown {
  if (typeof value === "string" && /account/i.test(key) && !/\*{2,}/.test(value)) return "[redacted]";
  if (Array.isArray(value)) return value.map((item) => redactSensitiveIdentifiers(item, key));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([childKey, childValue]) => [childKey, redactSensitiveIdentifiers(childValue, childKey)]));
  return value;
}

function Citation({ guideline, onSelect }: { guideline: Guideline; onSelect: (guideline: Guideline) => void }) {
  return <button className="citation-link" type="button" onClick={() => onSelect(guideline)} aria-label={`Open citation ${formatCitation(guideline)}`}>{guideline.chunk_id}</button>;
}

function DecisionPanel({ response, existingDecision, decisionStateUnavailable, onDecisionSaved }: { response: ReportResponse; existingDecision: Decision | null; decisionStateUnavailable: boolean; onDecisionSaved: () => void }) {
  const { investigation_id: id, execution_status, verification } = response;
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState<DecisionFields["decision"] | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const alreadyDecided = Boolean(existingDecision);
  const { register, handleSubmit, setValue, watch, trigger, formState: { errors } } = useForm<DecisionFields>({ resolver: zodResolver(decisionSchema), defaultValues: { decision: "ESCALATE", rationale: "", analyst_id: "ANL-2048" } });
  const analystId = watch("analyst_id");
  const rationale = watch("rationale") ?? "";
  const mutation = useMutation({
    mutationFn: (input: DecisionFields) => api.submitDecision(id, { ...input, created_at: new Date().toISOString() }),
    onSuccess: () => { toast.success("Investigator decision recorded"); setConfirmOpen(false); onDecisionSaved(); queryClient.invalidateQueries({ queryKey: ["investigation", id] }); queryClient.invalidateQueries({ queryKey: ["investigation-report", id] }); queryClient.invalidateQueries({ queryKey: ["investigations"] }); queryClient.invalidateQueries({ queryKey: ["audit", id] }); },
    onError: (error) => { if (!(error as Error & { status?: number }).status) toast.error(error.message); },
  });
  const canRecord = !decisionStateUnavailable && !alreadyDecided;
  const canApprove = execution_status === "completed" && verification.passed && canRecord;
  async function stageDecision(value: DecisionFields["decision"]) {
    setValue("decision", value, { shouldValidate: true });
    setDecision(value);
    if (await trigger(["rationale", "analyst_id"])) setConfirmOpen(true);
  }
  const submit = handleSubmit((values) => mutation.mutate(values));
  const inlineError = mutation.error as (Error & { status?: number }) | null;
  return <>
    <div className="decision-card"><div className="decision-header"><h2>Human investigator decision</h2><p>The agent cannot record or authorize a decision.</p></div><div className="decision-content">
      {alreadyDecided ? <div className="decision-note">A human disposition has already been recorded. It cannot be overwritten here.</div> : <>
        <div className="decision-note">{decisionStateUnavailable ? "The existing case state could not be confirmed. Decision actions are disabled." : execution_status !== "completed" ? "This run is not complete. Approval is disabled; review or escalate as appropriate." : !verification.passed ? "Verification did not pass. Approval is disabled until a valid report is available." : "Review the report and evidence before recording a disposition."}</div>
        <FieldGroup className="form-stack">
          <Field data-invalid={Boolean(errors.rationale)}>
            <FieldLabel htmlFor={`rationale-${id}`}>Investigator rationale <span className="subtle">(required)</span></FieldLabel>
            <Textarea id={`rationale-${id}`} className="control-textarea" maxLength={5000} placeholder="Summarize the evidence reviewed and basis for your disposition…" {...register("rationale")} aria-invalid={Boolean(errors.rationale)} aria-describedby={`rationale-help-${id} rationale-count-${id}`} />
            <div className="rationale-meta"><FieldDescription id={`rationale-help-${id}`}>10–5,000 characters. Explain the evidence reviewed and the basis for the decision.</FieldDescription><span id={`rationale-count-${id}`} className="char-counter" aria-live="polite">{rationale.trim().length} / 5,000</span></div>
            <FieldError errors={[errors.rationale]} />
          </Field>
          <Field data-invalid={Boolean(errors.analyst_id)}>
            <FieldLabel htmlFor={`analyst-${id}`}>Analyst ID</FieldLabel>
            <Input id={`analyst-${id}`} className="control-input" {...register("analyst_id")} aria-invalid={Boolean(errors.analyst_id)} />
            <FieldDescription>Placeholder analyst identity; bind to the authenticated analyst in production.</FieldDescription>
            <FieldError errors={[errors.analyst_id]} />
          </Field>
        </FieldGroup>
        <fieldset className="decision-option-list" disabled={!canRecord || mutation.isPending} aria-label="Choose a human disposition">
          {decisionOptions.map((option) => { const Icon = option.icon; const approvalDisabled = option.value === "APPROVE" && !canApprove; return <label className={`decision-option ${decision === option.value ? "selected" : ""} ${approvalDisabled ? "disabled" : ""}`} key={option.value} title={approvalDisabled ? "Approval requires a completed report with verification passed." : undefined}><input type="radio" name={`decision-${id}`} value={option.value} checked={decision === option.value} disabled={approvalDisabled} onChange={() => stageDecision(option.value)} aria-describedby={option.value === "APPROVE" ? `approval-help-${id}` : undefined} /><span className="decision-option-mark" aria-hidden="true" /><span className="decision-option-copy"><strong><Icon aria-hidden="true" />{option.label}</strong><small>{option.description}</small>{option.value === "APPROVE" && <small id={`approval-help-${id}`} className="decision-option-help">Enabled only when execution is completed and verification passes.</small>}</span></label>; })}
        </fieldset>
      </>}
      {mutation.isError && <div className="decision-error" role="alert"><strong>{inlineError?.status === 409 ? "Decision conflict" : "Decision not recorded"}</strong><p>{mutation.error.message}</p></div>}
    </div></div>
    <Dialog open={confirmOpen} onOpenChange={(open) => { if (!mutation.isPending) setConfirmOpen(open); }}>
      <DialogContent className="confirm-modal" aria-describedby={`decision-confirm-description-${id}`}>
        <DialogHeader><DialogTitle>Confirm {decision?.toLowerCase()} disposition</DialogTitle><DialogDescription id={`decision-confirm-description-${id}`}>This action will be recorded in the audit trail under analyst ID {analystId}. Review your rationale before confirming.</DialogDescription></DialogHeader>
        <p><strong>AI output does not make or authorize this decision.</strong> This is a human investigator action.</p>
        <DialogFooter className="confirm-modal-actions"><button type="button" className="button-secondary" onClick={() => setConfirmOpen(false)} disabled={mutation.isPending}>Go back</button><button type="button" className={decision === "REJECT" ? "button-danger" : "button-primary"} onClick={submit} disabled={mutation.isPending || !decision}>{mutation.isPending ? "Recording…" : `Confirm ${decision?.toLowerCase()}`}</button></DialogFooter>
      </DialogContent>
    </Dialog>
  </>;
}

function VerificationStrip({ response }: { response: ReportResponse }) {
  const { execution_status, verification } = response;
  const isFailed = execution_status === "failed" || verification.errors.length > 0;
  const isWarning = !isFailed && (execution_status === "incomplete" || !verification.passed || verification.warnings.length > 0);
  const tone = isFailed ? "error" : isWarning ? "warning" : "success";
  const label = isFailed ? "Verification failed" : isWarning ? `Review required · ${execution_status}` : "Verification passed";
  return <section className={`verification-strip ${tone}`} role={isFailed || isWarning ? "alert" : "status"} aria-live="polite"><div className="verification-strip-heading"><span className="verification-strip-icon">{isFailed ? <XCircle /> : isWarning ? <AlertTriangle /> : <CheckCircle2 />}</span><div><strong>{label}</strong><p>{verification.errors.length} error{verification.errors.length === 1 ? "" : "s"} · {verification.warnings.length} warning{verification.warnings.length === 1 ? "" : "s"}</p></div><StatusBadge status={execution_status} /><StatusBadge status={verification.passed ? "supported" : "warning"} label={verification.passed ? "Verification passed" : "Verification failed"} /></div>{(verification.errors.length > 0 || verification.warnings.length > 0) && <ul className="verification-issue-list">{verification.errors.map((item) => <li key={`error-${item}`} className="error-item"><strong>Error:</strong> {item}</li>)}{verification.warnings.map((item) => <li key={`warning-${item}`} className="warning-item"><strong>Warning:</strong> {item}</li>)}</ul>}</section>;
}

function ReferenceCard({ guideline, onCitation }: { guideline: Guideline; onCitation: (guideline: Guideline) => void }) {
  const score = Math.max(0, Math.min(100, guideline.relevance_score * 100));
  return <article className="evidence-card reference-card"><div className="evidence-card-head"><h3>{guideline.source} · {guideline.section}</h3><span className="evidence-ref">{score.toFixed(0)}% relevance</span></div><div className="relevance-bar" role="img" aria-label={`Relevance ${score.toFixed(0)} percent`}><span style={{ width: `${score}%` }} /></div><p className="citation-text">{guideline.text}</p><div className="evidence-meta"><button type="button" className="citation-link" onClick={() => onCitation(guideline)}>{formatCitation(guideline)}</button><span className="evidence-ref">{humanize(guideline.typology)}</span></div></article>;
}

function ReportPanel({ response, onCitation }: { response: ReportResponse; onCitation: (guideline: Guideline) => void }) {
  const report = response.report;
  const referencesByChunk = new Map(report.aml_guidance_and_evidence.references.map((reference) => [reference.chunk_id, reference]));
  const disclaimer = <DisclaimerCallout>{report.human_review_disclaimer}</DisclaimerCallout>;
  const transactionAnalysis = report.transaction_analysis;
  const guidance = report.aml_guidance_and_evidence;
  const questions = report.missing_information_and_questions;
  const narrative = report.investigation_narrative;
  return <div className="report-sections">
    <Tabs defaultValue="summary" className="tabs-strip">
      <TabsList aria-label="Investigation report sections"><TabsTrigger value="summary">Alert Summary</TabsTrigger><TabsTrigger value="analysis">Transaction Analysis</TabsTrigger><TabsTrigger value="guidance">Guidance &amp; Evidence</TabsTrigger><TabsTrigger value="gaps">Missing Info &amp; Questions</TabsTrigger><TabsTrigger value="narrative">Narrative</TabsTrigger></TabsList>
      <TabsContent value="summary"><div className="section-stack"><div className="detail-summary-grid"><div className="detail-summary-item"><span>Alert ID</span><Link className="copyable-id" href={`/alerts/${report.alert_summary.alert_id}`}>{report.alert_summary.alert_id}</Link></div><div className="detail-summary-item"><span>Typology</span><strong>{humanize(report.alert_summary.typology)}</strong></div><div className="detail-summary-item"><span>Account token</span><strong className="mono">{safeAccountToken(report.alert_summary.account_id)}</strong></div><div className="detail-summary-item"><span>Verification</span><StatusBadge status={response.verification.passed ? "supported" : "warning"} label={response.verification.passed ? "Passed" : "Needs review"} /></div></div><p className="report-summary-text">{report.alert_summary.summary}</p>{disclaimer}</div></TabsContent>
      <TabsContent value="analysis"><div className="section-stack"><div className="statistics-grid">{Object.entries(transactionAnalysis.computed_statistics).map(([key, value]) => <div className="statistic-card" key={key}><span>{humanize(key)}</span><strong className="mono">{String(value)}</strong></div>)}</div><section><div className="section-heading"><div><h2>Observed patterns</h2><p>Computed from the retrieved transaction sample.</p></div></div>{transactionAnalysis.observed_patterns.length ? <div className="pattern-list">{transactionAnalysis.observed_patterns.map((pattern) => <article className="evidence-card" key={pattern.pattern_id}><div className="evidence-card-head"><h3>{pattern.description}</h3><span className="evidence-ref mono">{pattern.pattern_id}</span></div><p>Metric <span className="mono">{pattern.metric_key}</span></p><div className="evidence-meta">{pattern.transaction_ids.map((transactionId) => <CopyableId key={transactionId} value={transactionId} />)}</div></article>)}</div> : <div className="empty-state"><strong>No observed patterns</strong><p>No patterns were supported by the available sample.</p></div>}</section><div className="three-column analysis-support-grid"><article className="evidence-card"><h3>Potential red flags</h3>{transactionAnalysis.potential_red_flags.length ? <ul>{transactionAnalysis.potential_red_flags.map((value) => <li key={value}>{value}</li>)}</ul> : <p className="field-hint">None reported.</p>}</article><article className="evidence-card"><h3>Supporting transaction IDs</h3><div className="evidence-meta">{transactionAnalysis.supporting_transaction_ids.map((value) => <CopyableId key={value} value={value} />)}</div></article><article className="evidence-card"><h3>Limitations</h3>{transactionAnalysis.limitations.length ? <ul>{transactionAnalysis.limitations.map((value) => <li key={value}>{value}</li>)}</ul> : <p className="field-hint">None reported.</p>}</article></div>{disclaimer}</div></TabsContent>
      <TabsContent value="guidance"><div className="section-stack"><section><div className="section-heading"><div><h2>Retrieved guidance</h2><p>Passages are source-linked decision support; validate the original publication and its current version.</p></div></div>{appConfig.mocks && <div className="warning-callout" role="note"><AlertTriangle /><span>Mock passages are synthetic fixtures, not verbatim or authoritative publication text.</span></div>}{guidance.references.length ? <div className="reference-list">{guidance.references.map((reference) => <ReferenceCard key={reference.chunk_id} guideline={reference} onCitation={onCitation} />)}</div> : <div className="empty-state"><strong>No guidance references</strong><p>No source passages were returned for this report.</p></div>}</section><section><div className="section-heading"><div><h2>Evidence findings</h2><p>Claims are shown with their evidence type, support level, and source links.</p></div></div>{guidance.evidence.length ? <div className="table-wrap"><table className="data-table evidence-findings-table" aria-label="Evidence findings"><thead><tr><th>Claim</th><th>Claim type</th><th>Support</th><th>Transactions</th><th>Guidance chunks</th><th>Evidence explanation</th></tr></thead><tbody>{guidance.evidence.map((finding) => <tr key={finding.claim_id}><td><strong>{finding.claim}</strong><small className="table-subtext mono">{finding.claim_id}</small></td><td><StatusBadge status={finding.claim_type} label={claimLabels[finding.claim_type]} /></td><td><StatusBadge status={finding.support_status} /></td><td><div className="chip-list">{finding.supporting_transaction_ids.length ? finding.supporting_transaction_ids.map((id) => <CopyableId key={id} value={id} />) : <span className="subtle">None</span>}</div></td><td><div className="chip-list">{finding.supporting_chunk_ids.length ? finding.supporting_chunk_ids.map((chunkId) => { const guideline = referencesByChunk.get(chunkId); return guideline ? <Citation key={chunkId} guideline={guideline} onSelect={onCitation} /> : <span className="evidence-ref mono" key={chunkId}>{chunkId} · unavailable</span>; }) : <span className="subtle">None</span>}</div></td><td>{finding.evidence_explanation}</td></tr>)}</tbody></table></div> : <div className="empty-state"><strong>No evidence findings</strong><p>The report contains no evidence-correlated claims.</p></div>}</section><div className="three-column concern-callouts"><section className="concern-callout"><h3><ShieldAlert />Potential concerns</h3>{guidance.potential_concerns.length ? <ul>{guidance.potential_concerns.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="field-hint">None reported.</p>}</section><section className="concern-callout muted"><h3><CircleHelp />Unsupported assumptions</h3>{guidance.unsupported_assumptions.length ? <ul>{guidance.unsupported_assumptions.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="field-hint">None reported.</p>}</section></div>{disclaimer}</div></TabsContent>
      <TabsContent value="gaps"><div className="section-stack"><div className="table-wrap"><table className="data-table compact" aria-label="Information gaps"><thead><tr><th>Field</th><th>Status</th><th>Explanation</th><th>Question</th></tr></thead><tbody>{questions.information_gaps.map((gap) => <tr key={gap.field}><td>{humanize(gap.field)}</td><td><StatusBadge status={gap.status} label={gapLabels[gap.status]} /></td><td>{gap.explanation}</td><td>{gap.question ?? "—"}</td></tr>)}</tbody></table></div><section className="evidence-card question-list"><h3>Investigation questions</h3>{questions.investigation_questions.length ? <ol>{questions.investigation_questions.map((question) => <li key={question}>{question}</li>)}</ol> : <p className="field-hint">No additional questions were recorded.</p>}</section>{disclaimer}</div></TabsContent>
      <TabsContent value="narrative"><div className="section-stack"><section className="evidence-card"><h3>Draft narrative</h3>{narrative.statements.length ? <ol>{narrative.statements.map((statement) => <li key={statement}>{statement}</li>)}</ol> : <p className="field-hint">No narrative statements were generated.</p>}</section><section className="evidence-card"><h3>Recommended next steps</h3>{narrative.recommended_next_steps.length ? <ol>{narrative.recommended_next_steps.map((step) => <li key={step}>{step}</li>)}</ol> : <p className="field-hint">No next steps were generated.</p>}</section><section className="evidence-card"><h3>Limitations</h3>{narrative.limitations.length ? <ul>{narrative.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul> : <p className="field-hint">None reported.</p>}</section>{disclaimer}</div></TabsContent>
    </Tabs>
    <details className="trace-panel"><summary><span><FileCheck2 />How this was produced</span><small>{response.agent_execution_trace.length} trace steps</small></summary><div className="trace-list">{response.agent_execution_trace.map((trace, index) => <div className="trace-row" key={`${trace.agent_name}-${index}`}><span className={`trace-icon ${trace.execution_status === "completed" ? "ok" : trace.execution_status === "failed" ? "bad" : ""}`}>{trace.execution_status === "completed" ? <CheckCircle2 /> : trace.execution_status === "failed" ? <XCircle /> : <CircleHelp />}</span><strong>{trace.agent_name}</strong><StatusBadge status={trace.execution_status} /><span className="subtle">{trace.error_message ?? ""}</span></div>)}</div></details>
  </div>;
}

export function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [citation, setCitation] = useState<Guideline | null>(null);
  const reportQuery = useQuery({ queryKey: ["investigation-report", id], queryFn: () => api.getInvestigationReport(id), enabled: Boolean(id) });
  const summaryQuery = useQuery({ queryKey: ["investigation", id], queryFn: () => api.getInvestigation(id), enabled: Boolean(id) });
  if (reportQuery.isLoading || summaryQuery.isLoading) return <><PageHeader title="Investigation review" /><Panel title="Loading investigation"><LoadingRows count={6} /></Panel></>;
  if (reportQuery.isError || !reportQuery.data) return <><PageHeader backHref="/investigations" title="Investigation not found" /><ErrorPanel message={reportQuery.error?.message ?? "The investigation could not be loaded."} onRetry={() => reportQuery.refetch()} /></>;
  const response = reportQuery.data;
  const summary = summaryQuery.data;
  const exportReport = () => downloadJson(`${id}-investigation-report.json`, redactSensitiveIdentifiers(response));
  return <>
    <PageHeader backHref="/investigations" eyebrow="INVESTIGATION REVIEW" title={<span className="detail-title-row"><span>{id}</span><StatusBadge status={response.execution_status} label={response.label} /></span>} description={`Alert ${response.report.alert_summary.alert_id} · Draft generated ${summary ? formatDate(summary.created_at) : ""}`} action={<div className="detail-header-actions"><details className="export-menu"><summary className="button-secondary"><Download />Export</summary><div className="export-menu-content"><button type="button" onClick={() => window.print()}><Printer />Print / Save PDF</button><button type="button" onClick={exportReport}><Download />Download JSON</button></div></details><Link className="button-secondary" href={`/alerts/${response.report.alert_summary.alert_id}`}>Open source alert <ExternalLink /></Link></div>} />
    <VerificationStrip response={response} />
    <div className="detail-layout investigation-detail-layout"><div className="detail-main"><Panel title="Investigation report" description="Evidence-linked, AI-generated draft for investigator review."><ReportPanel response={response} onCitation={setCitation} /></Panel>
      {summary?.decision && <Panel title="Recorded investigator disposition" description={`Recorded ${formatDate(summary.decision.created_at)} by ${summary.decision.analyst_id}`}><div className="recorded-decision"><StatusBadge status={summary.decision.decision} /><strong>Rationale</strong><p>{summary.decision.rationale}</p></div></Panel>}
    </div><aside className="detail-side" aria-label="Investigation controls"><DecisionPanel response={response} existingDecision={summary?.decision ?? null} decisionStateUnavailable={summaryQuery.isError || !summary} onDecisionSaved={() => { queryClient.invalidateQueries({ queryKey: ["investigation", id] }); }} /><Panel title="Run validation"><div className="health-list"><div className="health-list-row"><span className="subtle">Run status</span><StatusBadge status={response.execution_status} /></div><div className="health-list-row"><span className="subtle">Verification</span><StatusBadge status={response.verification.passed ? "supported" : "warning"} label={response.verification.passed ? "Passed" : "Needs review"} /></div><div className="health-list-row"><span className="subtle">Warnings</span><strong>{response.verification.warnings.length}</strong></div><div className="health-list-row"><span className="subtle">Errors</span><strong>{response.verification.errors.length}</strong></div></div></Panel><Panel title="Audit trail" description="All case activity is recorded."><Link href={`/audit?investigation_id=${encodeURIComponent(id)}`} className="inline-link">View event history <ArrowRight /></Link></Panel></aside></div>
    <Dialog open={Boolean(citation)} onOpenChange={(open) => { if (!open) setCitation(null); }}><DialogContent className="citation-drawer"><DialogHeader><DialogTitle>Source citation</DialogTitle><DialogDescription>{citation ? formatCitation(citation) : "Review the original retrieved passage."}</DialogDescription></DialogHeader>{citation && <div className="citation-drawer-content"><div className="citation-score-row"><span>Relevance</span><strong>{(citation.relevance_score * 100).toFixed(1)}%</strong></div><div className="relevance-bar" role="img" aria-label={`Relevance ${(citation.relevance_score * 100).toFixed(1)} percent`}><span style={{ width: `${Math.max(0, Math.min(100, citation.relevance_score * 100))}%` }} /></div><div className="citation-meta-grid"><span>Typology</span><strong>{humanize(citation.typology)}</strong><span>Source</span><strong>{citation.source}</strong></div><section className="citation-verbatim"><h3>Retrieved text</h3><blockquote>{citation.text}</blockquote></section><p className="field-hint">Verify the cited passage in the original publication and applicable jurisdiction before relying on it.</p></div>}<DialogFooter className="confirm-modal-actions"><button type="button" className="button-secondary" onClick={() => setCitation(null)}>Close citation</button></DialogFooter></DialogContent></Dialog>
  </>;
}
