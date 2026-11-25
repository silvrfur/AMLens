import { AlertsPage } from "@/components/pages/alerts";

type AlertQueueProps = { searchParams: { search?: string | string[] } };

export default function AlertQueuePage({ searchParams }: AlertQueueProps) {
  const value = searchParams.search;
  return <AlertsPage initialSearch={Array.isArray(value) ? value[0] ?? "" : value ?? ""} />;
}
