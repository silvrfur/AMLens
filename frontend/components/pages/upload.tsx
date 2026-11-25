"use client";

import { useRef, useState } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, FileSpreadsheet, FileUp, LoaderCircle, ShieldCheck } from "lucide-react";
import { PageHeader, Panel, StatusBadge, CopyableId } from "@/components/shared";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { api } from "@/lib/api/client";
import type { UploadResult } from "@/lib/api/types";

const uploadSchema = z.object({ file: z.instanceof(File, { message: "Select a transaction file to continue." }).refine((file) => /\.csv$/i.test(file.name), "Use a .csv file only.").refine((file) => file.size <= 25 * 1024 * 1024, "File must be smaller than 25 MB.") });
type UploadValues = z.infer<typeof uploadSchema>;

export function UploadPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [receipt, setReceipt] = useState<UploadResult | null>(null);
  const { handleSubmit, setValue, formState: { errors } } = useForm<UploadValues>({ resolver: zodResolver(uploadSchema) });
  const mutation = useMutation({ mutationFn: (file: File) => api.uploadTransactions(file), onSuccess: (data) => setReceipt(data) });
  function chooseFile(file?: File) { if (!file) return; setSelected(file); setReceipt(null); setValue("file", file, { shouldValidate: true }); }
  const onSubmit = handleSubmit(({ file }) => mutation.mutate(file));
  return <>
    <PageHeader eyebrow="DATA INGESTION" title="Upload transactions" description="Import a CSV transaction file for rule evaluation and alert generation." />
    <div className="two-column">
      <Panel title="Transaction file" description="Accepted format: CSV · Maximum file size: 25 MB">
        {!receipt ? <form onSubmit={onSubmit} className="form-stack">
          <FieldGroup className="form-stack">
            <Field data-invalid={Boolean(errors.file)}>
              <FieldLabel htmlFor="transaction-file">Transaction file</FieldLabel>
              <FieldDescription id="transaction-file-help">Use tokenized identifiers only. CSV files up to 25 MB are accepted.</FieldDescription>
              <input id="transaction-file" ref={fileRef} type="file" accept=".csv,text/csv" className="sr-only" aria-describedby="transaction-file-help" aria-invalid={Boolean(errors.file)} onChange={(event) => chooseFile(event.target.files?.[0])} />
              <button type="button" aria-describedby="transaction-file-help" aria-label="Choose transaction file" className={`upload-dropzone ${dragging ? "is-dragging" : ""}`} onClick={() => fileRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files[0]); }}><FileUp /><strong>{selected ? selected.name : "Drop a file here or browse"}</strong><span>{selected ? `${(selected.size / 1024).toFixed(1)} KB · Click to choose another file` : "Upload a CSV spreadsheet"}</span></button>
              {errors.file && <FieldError>{errors.file.message}</FieldError>}
              {mutation.isError && <FieldError>{mutation.error.message}</FieldError>}
            </Field>
          </FieldGroup>
          {selected && <div className="inline-row"><FileSpreadsheet style={{ width: 16, height: 16, color: "var(--accent-teal)" }} /><span className="mono">{selected.name}</span><span className="subtle">{(selected.size / 1024).toFixed(1)} KB</span></div>}
          <button className="button-primary" type="submit" disabled={mutation.isPending || !selected}>{mutation.isPending ? <><LoaderCircle className="progress-spinner" />Processing file…</> : <><FileUp />Upload and analyze</>}</button>
        </form> : <div className="section-stack"><div className="upload-receipt"><div className="upload-receipt-header"><span>Upload completed</span><StatusBadge status="COMPLETED" label="Processed" /></div><div className="upload-receipt-grid"><div><strong>{receipt.accepted_count.toLocaleString()}</strong><span>Accepted rows</span></div><div><strong>{receipt.rejected_count.toLocaleString()}</strong><span>Rejected rows</span></div><div><strong>{receipt.alerts_created.toLocaleString()}</strong><span>Alerts generated</span></div></div><div className="upload-count-bar" role="img" aria-label={`${receipt.accepted_count} accepted rows and ${receipt.rejected_count} rejected rows`}><span style={{ width: `${receipt.accepted_count + receipt.rejected_count ? Math.round(receipt.accepted_count / (receipt.accepted_count + receipt.rejected_count) * 100) : 0}%` }} /><span style={{ width: `${receipt.accepted_count + receipt.rejected_count ? Math.round(receipt.rejected_count / (receipt.accepted_count + receipt.rejected_count) * 100) : 0}%` }} /></div><div style={{ padding: "8px 14px 13px" }}><span className="field-label">Dataset ID</span><CopyableId value={receipt.dataset_id} /></div></div>
          {receipt.rejected_count > 0 && <div><div className="warning-callout" role="status"><AlertCircle /><span>Rejected rows are flagged, not silently dropped. Review each reason before continuing.</span></div><div className="section-heading"><h2>Rejected rows</h2><span className="subtle">{receipt.rejected_count} total</span></div><div className="table-wrap"><table className="data-table compact" aria-label="Rejected rows"><thead><tr><th>Row</th><th>Reason</th></tr></thead><tbody>{receipt.rejection_reasons.map((reason) => <tr key={reason.row_number}><td className="mono">{reason.row_number}</td><td>{reason.reason}</td></tr>)}</tbody></table></div>{receipt.rejection_reasons_truncated && <p className="field-hint">Only the first 3 rejection reasons are shown.</p>}</div>}
          <div className="inline-row"><button className="button-secondary" onClick={() => { setReceipt(null); setSelected(null); }}>Upload another file</button><a className="button-primary" href="/alerts">View {receipt.alerts_created} new alerts <ArrowRight /></a></div>
        </div>}
        <div className="dropzone-help"><div className="help-item"><ShieldCheck /><div><strong>Tokenized identifiers</strong><p>Account IDs are tokenized at ingestion, so nothing downstream sees raw identifiers. Do not upload direct customer identifiers.</p></div></div><div className="help-item"><AlertCircle /><div><strong>Validation summary</strong><p>Rows with malformed timestamps, invalid amounts, or unsupported currencies are rejected and summarized.</p></div></div></div>
      </Panel>
      <Panel title="Required fields" description="Columns used for monitoring and review">
        <div className="table-wrap"><table className="data-table compact" aria-label="Required transaction fields"><thead><tr><th>Field</th><th>Format</th></tr></thead><tbody>{[["transaction_id","Unique reference"],["timestamp","ISO 8601 datetime"],["sender_token","Tokenized ID"],["receiver_token","Tokenized ID"],["amount_paid","Decimal string"],["payment_currency","ISO 4217"],["amount_received","Decimal string"],["receiving_currency","ISO 4217"],["payment_format","ACH, SWIFT, etc."],["account_id","Optional token"]].map(([field, format]) => <tr key={field}><td className="mono">{field}</td><td>{format}</td></tr>)}</tbody></table></div>
        <p className="field-hint" style={{ marginTop: 12 }}>Amounts must remain decimal strings to preserve exactness. Account identifiers must be masked or tokenized before upload.</p>
      </Panel>
    </div>
  </>;
}
