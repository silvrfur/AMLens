import { AuditPage } from "@/components/pages/audit";
export default async function AuditRoute({ searchParams }: { searchParams: Promise<{ investigation_id?: string }> }) { const params = await searchParams; return <AuditPage initialId={params.investigation_id ?? ""} />; }
