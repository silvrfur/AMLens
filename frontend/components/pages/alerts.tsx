"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getCoreRowModel, getSortedRowModel, useReactTable, flexRender, type ColumnDef, type PaginationState, type SortingState, type VisibilityState } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";
import { Columns3, Download, Filter, Search } from "lucide-react";
import { PageHeader, Panel, StatusBadge, LoadingRows, ErrorPanel, CopyableId } from "@/components/shared";
import { api } from "@/lib/api/client";
import type { Alert } from "@/lib/api/types";
import { compareDecimalStrings, downloadCsv, formatAccountToken, formatDate, formatMoneyString, humanize } from "@/lib/format";

export function AlertsPage({ initialSearch = "" }: { initialSearch?: string }) {
  const router = useRouter();
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 10 });
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [search, setSearch] = useState(initialSearch);
  const [statusFilter, setStatusFilter] = useState("all");
  const [ruleFilter, setRuleFilter] = useState("all");
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  useEffect(() => { setSearch(initialSearch); setPagination((current) => ({ ...current, pageIndex: 0 })); }, [initialSearch]);
  const query = useQuery({ queryKey: ["alerts", pagination.pageSize, pagination.pageIndex * pagination.pageSize], queryFn: () => api.getAlerts(pagination.pageSize, pagination.pageIndex * pagination.pageSize), placeholderData: (previous) => previous });
  const columns = useMemo<ColumnDef<Alert>[]>(() => [
    { accessorKey: "id", header: "Alert ID", cell: ({ row }) => <CopyableId className="table-id" value={row.original.id} /> },
    { accessorKey: "rule_id", header: "Rule", cell: ({ row }) => <StatusBadge status={row.original.rule_id} label={row.original.rule_id} /> },
    { accessorKey: "description", header: "Description", cell: ({ row }) => <span className="table-description">{row.original.description}</span> },
    { accessorKey: "transaction_id", header: "Transaction ID", cell: ({ row }) => <span className="mono">{row.original.transaction_id}</span> },
    { id: "account", accessorFn: (row) => String(row.evidence.anchor_account_token), header: "Account", cell: ({ row }) => <span className="mono">{formatAccountToken(String(row.original.evidence.anchor_account_token))}</span> },
    { id: "amount", enableSorting: false, header: "Amount", cell: ({ row }) => <span className="tabular-nums">{formatMoneyString(String(row.original.evidence.amount_paid), String(row.original.evidence.currency))}</span> },
    { accessorKey: "status", header: "Status", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
    { id: "created", accessorFn: (row) => String(row.evidence.created_at), header: "Created", cell: ({ row }) => formatDate(String(row.original.evidence.created_at), { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }) },
    { id: "action", header: "", enableSorting: false, cell: ({ row }) => <Link className="inline-link" href={`/alerts/${row.original.id}`} onClick={(event) => event.stopPropagation()}>Review</Link> },
  ], []);
  const source = query.data?.items ?? [];
  const decimalInputValid = (value: string) => value === "" || /^-?\d+(?:\.\d+)?$/.test(value);
  const filtered = source.filter((alert) => {
    const amount = String(alert.evidence.amount_paid);
    const created = String(alert.evidence.created_at).slice(0, 10);
    const text = `${alert.id} ${alert.rule_id} ${alert.description} ${alert.evidence.anchor_account_token} ${alert.transaction_id}`.toLowerCase();
    return (!search || text.includes(search.toLowerCase()))
      && (statusFilter === "all" || alert.status === statusFilter)
      && (ruleFilter === "all" || alert.rule_id === ruleFilter)
      && (!minAmount || !decimalInputValid(minAmount) || compareDecimalStrings(amount, minAmount) >= 0)
      && (!maxAmount || !decimalInputValid(maxAmount) || compareDecimalStrings(amount, maxAmount) <= 0)
      && (!fromDate || created >= fromDate)
      && (!toDate || created <= toDate);
  });
  const table = useReactTable({ data: filtered, columns, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), manualPagination: true, pageCount: Math.ceil((query.data?.total ?? 0) / pagination.pageSize), state: { pagination, sorting, columnVisibility }, onPaginationChange: setPagination, onSortingChange: setSorting, onColumnVisibilityChange: setColumnVisibility });
  const pageCount = Math.ceil((query.data?.total ?? 0) / pagination.pageSize);
  const total = query.data?.total ?? 0;
  const exportCurrentPage = () => downloadCsv("amlens-alerts-current-page.csv", filtered.map((alert) => ({ alert_id: alert.id, transaction_id: alert.transaction_id, rule_id: alert.rule_id, description: alert.description, account_token: formatAccountToken(String(alert.evidence.anchor_account_token)),  amount: alert.evidence.amount_paid as string, currency: alert.evidence.currency as string, status: alert.status, created_at: alert.evidence.created_at as string })));
  const setFilter = (callback: () => void) => { callback(); setPagination((current) => ({ ...current, pageIndex: 0 })); };
  return <>
    <PageHeader eyebrow="TRANSACTION MONITORING" title="Alert queue" description="Review and triage alerts generated by transaction monitoring rules." action={<button type="button" className="button-secondary" onClick={exportCurrentPage}><Download />Export current page</button>} />
    <Panel title="Flagged transactions" description={`${query.data?.total ?? "—"} alerts in the review queue`}>
      <div className="queue-filters">
        <label className="input-with-icon filter-search"><Search aria-hidden="true" /><input className="control-input" aria-label="Search current alert page" placeholder="Search current page…" value={search} onChange={(event) => setFilter(() => setSearch(event.target.value))} /></label>
        <select className="control-select" aria-label="Filter by status" value={statusFilter} onChange={(event) => setFilter(() => setStatusFilter(event.target.value))}><option value="all">All statuses</option><option value="OPEN">Open</option><option value="UNDER REVIEW">Under review</option><option value="DECIDED">Decided</option></select>
        <select className="control-select" aria-label="Filter by rule" value={ruleFilter} onChange={(event) => setFilter(() => setRuleFilter(event.target.value))}><option value="all">All rules</option><option value="HIGH_VALUE">High value</option><option value="REPEATED_PAIR">Repeated pair</option><option value="RAPID_MOVEMENT_CANDIDATE">Rapid movement candidate</option></select>
        <label className="filter-field"><span>Minimum amount</span><input className="control-input" inputMode="decimal" aria-label="Minimum amount" placeholder="0.00" value={minAmount} onChange={(event) => setFilter(() => setMinAmount(event.target.value))} /></label>
        <label className="filter-field"><span>Maximum amount</span><input className="control-input" inputMode="decimal" aria-label="Maximum amount" placeholder="No limit" value={maxAmount} onChange={(event) => setFilter(() => setMaxAmount(event.target.value))} /></label>
        <label className="filter-field"><span>From date</span><input className="control-input" type="date" aria-label="From date" value={fromDate} onChange={(event) => setFilter(() => setFromDate(event.target.value))} /></label>
        <label className="filter-field"><span>To date</span><input className="control-input" type="date" aria-label="To date" value={toDate} onChange={(event) => setFilter(() => setToDate(event.target.value))} /></label>
        <details className="column-menu"><summary className="button-secondary"><Columns3 />Columns</summary><div className="column-menu-content">{table.getAllLeafColumns().filter((column) => column.id !== "action").map((column) => <label key={column.id}><input type="checkbox" checked={column.getIsVisible()} onChange={column.getToggleVisibilityHandler()} />{typeof column.columnDef.header === "string" ? column.columnDef.header : humanize(column.id)}</label>)}</div></details>
        <span className="subtle filters-note"><Filter aria-hidden="true" />Filters and sorting apply to this server page. Amount comparisons preserve decimal strings.</span>
      </div>
      {query.isLoading ? <LoadingRows count={8} /> : query.isError ? <ErrorPanel message={query.error.message} onRetry={() => query.refetch()} /> : <>
        <div className="table-wrap"><table className="data-table alert-table" aria-label="Alert queue"><thead>{table.getHeaderGroups().map((group) => <tr key={group.id}>{group.headers.map((header) => <th key={header.id}>{header.isPlaceholder ? null : header.column.getCanSort() ? <button type="button" className="table-sort-button" onClick={header.column.getToggleSortingHandler()} aria-label={`Sort by ${header.column.id}`}>{flexRender(header.column.columnDef.header, header.getContext())}{header.column.getIsSorted() === "asc" ? " ↑" : header.column.getIsSorted() === "desc" ? " ↓" : ""}</button> : flexRender(header.column.columnDef.header, header.getContext())}</th>)}</tr>)}</thead><tbody>{table.getRowModel().rows.length ? table.getRowModel().rows.map((row) => <tr key={row.id} className="clickable-row" tabIndex={0} aria-label={`Open alert ${row.original.id}`} onClick={() => router.push(`/alerts/${row.original.id}`)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); router.push(`/alerts/${row.original.id}`); } }}>{row.getVisibleCells().map((cell) => <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>) : <tr><td colSpan={table.getVisibleLeafColumns().length} className="subtle">No alerts match the current filters.</td></tr>}</tbody></table></div>
        <div className="table-pagination"><span>Showing {total ? pagination.pageIndex * pagination.pageSize + 1 : 0}–{Math.min((pagination.pageIndex + 1) * pagination.pageSize, total)} of {total} alerts · {filtered.length} match current-page filters</span><div className="pagination-actions"><label className="page-size-select"><span>Rows</span><select className="control-select" aria-label="Rows per page" value={pagination.pageSize} onChange={(event) => setPagination({ pageIndex: 0, pageSize: Number(event.target.value) })}><option value={10}>10</option><option value={25}>25</option><option value={50}>50</option><option value={100}>100</option><option value={200}>200</option></select></label><button type="button" className="button-secondary" disabled={!table.getCanPreviousPage() || query.isFetching} onClick={() => table.previousPage()}>Previous</button><span className="subtle page-index">Page {pagination.pageIndex + 1} of {pageCount || 1}</span><button type="button" className="button-secondary" disabled={!table.getCanNextPage() || query.isFetching} onClick={() => table.nextPage()}>Next</button></div></div>
      </>}
    </Panel>
  </>;
}
