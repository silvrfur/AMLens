"use client";

import Link from "next/link";
import type { MouseEvent, ReactNode } from "react";
import { ArrowLeft, ArrowRight, Check, Copy, FileSearch, Info, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export function PageHeader({ eyebrow, title, description, action, backHref }: { eyebrow?: string; title: ReactNode; description?: string; action?: ReactNode; backHref?: string }) {
  return <div className="page-heading">{backHref && <Link className="back-link" href={backHref}><ArrowLeft />Back</Link>}<div className="page-heading-row"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{action && <div className="page-heading-action">{action}</div>}</div></div>;
}

export function Panel({ title, description, action, children, className }: { title: string; description?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <Card className={cn("panel-card", className)}><CardHeader className="panel-header"><div><CardTitle>{title}</CardTitle>{description && <CardDescription>{description}</CardDescription>}</div>{action && <div className="panel-action">{action}</div>}</CardHeader><CardContent className="panel-content">{children}</CardContent></Card>;
}

const statusColors: Record<string, string> = {
  OPEN: "status-open", "UNDER REVIEW": "status-review", DECIDED: "status-done", COMPLETED: "status-done", APPROVE: "status-done", healthy: "status-done", supported: "status-done", available_verified: "status-done",
  RUNNING: "status-running", PENDING_AGENT: "status-running", limited: "status-running", not_provided: "status-muted", not_applicable: "status-outline", INCOMPLETE: "status-warning", incomplete: "status-warning", warning: "status-warning", confirmed_missing: "status-failed", FAILED: "status-failed", failed: "status-failed", REJECT: "status-failed", ESCALATE: "status-warning", offline: "status-failed", degraded: "status-warning", unsupported: "status-failed",
};
export function StatusBadge({ status, label, className }: { status: string; label?: string; className?: string }) {
  return <Badge variant="outline" className={cn("status-badge", statusColors[status] ?? "status-muted", className)}>{label ?? status.replaceAll("_", " ")}</Badge>;
}

export function CopyableId({ value, className }: { value: string; className?: string }) {
  async function copy(event: MouseEvent<HTMLButtonElement>) { event.stopPropagation(); try { await navigator.clipboard.writeText(value); toast.success("Copied to clipboard"); } catch { toast.error("Could not copy ID"); } }
  return <span className={cn("copyable-id", className)}><span>{value}</span><button type="button" className="copy-button" onClick={copy} aria-label={`Copy ${value}`} title="Copy to clipboard"><Copy /></button></span>;
}

export function MetricCard({ label, value, detail, icon, accent }: { label: string; value: string; detail: ReactNode; icon: ReactNode; accent?: string }) {
  return <Card className="metric-card"><CardContent className="metric-content"><div className="metric-top"><span className="metric-label">{label}</span><span className={cn("metric-icon", accent)}>{icon}</span></div><div className="metric-value tabular-nums">{value}</div><div className="metric-detail">{detail}</div></CardContent></Card>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><span className="empty-icon"><FileSearch /></span><strong>{title}</strong><p>{description}</p>{action}</div>;
}

export function LoadingRows({ count = 5 }: { count?: number }) {
  return <div className="skeleton-stack" aria-label="Loading"><span className="sr-only">Loading data</span>{Array.from({ length: count }, (_, index) => <div className="skeleton-row" key={index}><i /><i /><i /><i /></div>)}</div>;
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="error-panel" role="alert"><ShieldAlert /><div><strong>Unable to load this information</strong><p>{message}</p></div>{onRetry && <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button>}</div>;
}

export function DisclaimerCallout({ children }: { children: ReactNode }) {
  return <div className="disclaimer-callout"><Info /><p>{children}</p></div>;
}

export function InlineLink({ href, children }: { href: string; children: ReactNode }) { return <Link href={href} className="inline-link">{children}<ArrowRight /></Link>; }
