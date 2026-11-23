"use client";

import { useState } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { BookOpen, FileText, Search, ShieldAlert } from "lucide-react";
import { PageHeader, Panel, StatusBadge, CopyableId, DisclaimerCallout } from "@/components/shared";
import { api, appConfig } from "@/lib/api/client";
import { formatCitation, formatDate } from "@/lib/format";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";

const schema = z.object({ query: z.string().trim().min(3, "Enter at least 3 characters to search.").max(500), typology: z.enum(["structuring", "rapid_movement", "fan_in_out", "unusual_activity"]), top_k: z.coerce.number().int().min(1).max(20) });
type SearchInput = z.input<typeof schema>;
type SearchValues = z.output<typeof schema>;
const sources = [{ name: "FATF Recommendations", type: "Global standard · example metadata", chunks: 46, updated: "2026-09-18T11:00:00.000Z" }, { name: "RBI KYC Master Direction", type: "Regulatory guidance · example metadata", chunks: 28, updated: "2026-10-02T11:00:00.000Z" }, { name: "FIU-IND Guidance", type: "Reporting guidance · example metadata", chunks: 19, updated: "2026-10-16T11:00:00.000Z" }, { name: "Additional AML Guidance", type: "Reference material · example metadata", chunks: 14, updated: "2026-11-03T11:00:00.000Z" }];

export function KnowledgePage() {
  const [submittedQuery, setSubmittedQuery] = useState<SearchValues | null>(null);
  const { register, handleSubmit, formState: { errors } } = useForm<SearchInput, unknown, SearchValues>({ resolver: zodResolver(schema), defaultValues: { query: "high value payment inconsistent with customer profile", typology: "unusual_activity", top_k: 5 } });
  const mutation = useMutation({ mutationFn: (values: SearchValues) => api.searchGuidelines(values) });
  const submit = handleSubmit((values) => { setSubmittedQuery(values); mutation.mutate(values); });
  return <>
    <PageHeader eyebrow="REFERENCE LIBRARY" title="Knowledge base" description="Search example AML guidance fixtures. Mock excerpts are synthetic and are not authoritative or verbatim publication text." />
    <div className="two-column knowledge-layout">
      <Panel title="Retrieve AML guidance" description="Search results are decision support and require source-context review.">
        <form onSubmit={submit}>
          <FieldGroup className="form-stack">
            <Field data-invalid={Boolean(errors.query)}>
              <FieldLabel htmlFor="guidance-query">Search query</FieldLabel>
              <Textarea id="guidance-query" className="control-textarea" placeholder="Describe a transaction pattern or policy question…" {...register("query")} aria-invalid={Boolean(errors.query)} aria-describedby="guidance-query-help" />
              <FieldDescription id="guidance-query-help">Use a typology or policy question; avoid direct customer identifiers.</FieldDescription>
              <FieldError errors={[errors.query]} />
            </Field>
            <div className="form-grid">
              <Field data-invalid={Boolean(errors.typology)}>
                <FieldLabel htmlFor="guidance-typology">Typology</FieldLabel>
                <select id="guidance-typology" className="control-select" {...register("typology")} aria-invalid={Boolean(errors.typology)}><option value="structuring">Structuring</option><option value="rapid_movement">Rapid movement</option><option value="fan_in_out">Fan-in / fan-out</option><option value="unusual_activity">Unusual activity</option></select>
                <FieldError errors={[errors.typology]} />
              </Field>
              <Field data-invalid={Boolean(errors.top_k)}>
                <FieldLabel htmlFor="guidance-limit">Maximum results</FieldLabel>
                <Input id="guidance-limit" className="control-input" type="number" min={1} max={20} step={1} {...register("top_k")} aria-invalid={Boolean(errors.top_k)} />
                <FieldError errors={[errors.top_k]} />
              </Field>
            </div>
            {mutation.isError && <p className="field-error" role="alert">{mutation.error.message}</p>}
            <button className="button-primary" type="submit" disabled={mutation.isPending}>{mutation.isPending ? "Searching…" : <><Search />Search guidance</>}</button>
          </FieldGroup>
        </form>
        <div className="disclaimer-callout" style={{ marginTop: 14 }}><ShieldAlert /><p><strong>Research tool only.</strong> Retrieval does not establish applicability, legal interpretation, or a case decision. Verify the source document and applicable jurisdiction.</p></div>
      </Panel>
      <Panel title="Example source metadata" description="Illustrative fixture metadata only. Verify official source documents and current versions before relying on them.">
        <div className="source-list">{sources.map((source) => <div className="source-row" key={source.name}><span className="source-icon"><BookOpen /></span><div><strong>{source.name}</strong><span>{source.type} · {source.chunks} indexed chunks</span><small>Indexed {formatDate(source.updated, { month: "short", day: "numeric", year: "numeric" })}</small></div><StatusBadge status="available_verified" label="Indexed" /></div>)}</div>
      </Panel>
    </div>
    <Panel title="Retrieved passages" description={appConfig.mocks ? "Synthetic mock excerpts only; these are not verbatim or authoritative source passages." : submittedQuery ? `Top results for “${submittedQuery.query}” · ${submittedQuery.typology.replaceAll("_", " ")}` : "Submit a query to retrieve relevant source passages."}>
      {!mutation.data ? <div className="empty-state"><span className="empty-icon"><FileText /></span><strong>No search results yet</strong><p>Guidance retrieval returns source references and relevance notes for analyst review.</p></div> : <div className="section-stack">{mutation.data.relevance_notes.map((note) => <p className="field-hint" key={note}>{note}</p>)}{mutation.data.source_references.length > 0 && <div className="source-reference-row"><span>Source references</span>{mutation.data.source_references.map((source, index) => <span className="evidence-ref" key={`${source}-${index}`}>{source}</span>)}</div>}{mutation.data.retrieved_guidelines.map((result) => { const score = Math.max(0, Math.min(100, result.relevance_score * 100)); return <article className="evidence-card" key={result.chunk_id}><div className="evidence-card-head"><h3>{result.source} · {result.section}</h3><span className="evidence-ref">{score.toFixed(0)}% match</span></div><div className="relevance-bar" role="img" aria-label={`Relevance ${score.toFixed(0)} percent`}><span style={{ width: `${score}%` }} /></div><p>{result.text}</p><div className="evidence-meta"><CopyableId value={result.chunk_id} /><span className="evidence-ref">{result.typology.replaceAll("_", " ")}</span><span className="citation-format">{formatCitation(result)}</span></div></article>; })}{mutation.data.source_references.length === 0 && <p className="field-hint">No matching passages were returned. Refine the query or typology.</p>}</div>}
    </Panel>
  </>;
}
