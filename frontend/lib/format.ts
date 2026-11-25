// Only already-pseudonymous tokens are shown: masked IDs (ACC-****1234), backend HMAC tokens (ACC_<hex>)
// and agent account tokens (acct_<hex>). Anything else could be a raw account number and is withheld.
export function formatAccountToken(value: string) { return /^[A-Z]{2,6}-\*{2,}[A-Z0-9]{4}$/i.test(value) || /^(ACC|acct)_[0-9a-f]{12,64}$/.test(value) ? value : "Tokenized reference unavailable"; }
/** The alert's headline amount: amount_paid (high value) or incoming_amount (rapid movement); null when the rule has none. */
export function alertAmount(evidence: Record<string, unknown>): string | null {
  const value = evidence.amount_paid ?? evidence.incoming_amount;
  return typeof value === "string" || typeof value === "number" ? String(value) : null;
}
export function formatMoneyString(value: string | number, currency = "USD") {
  const raw = String(value);
  const negative = raw.startsWith("-");
  const unsigned = negative ? raw.slice(1) : raw;
  const [whole = "0", fraction] = unsigned.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const symbol = currency === "USD" ? "$" : currency === "EUR" ? "€" : currency === "GBP" ? "£" : `${currency} `;
  return `${negative ? "-" : ""}${symbol}${grouped}${fraction !== undefined ? `.${fraction}` : ""}`;
}
export function compareDecimalStrings(left: string, right: string) {
  const parse = (value: string) => {
    const negative = value.startsWith("-");
    const [whole = "0", fraction = ""] = (negative ? value.slice(1) : value).split(".");
    return { negative, whole: (whole || "0").replace(/^0+(?=\d)/, ""), fraction };
  };
  const a = parse(left);
  const b = parse(right);
  if (a.negative !== b.negative) return a.negative ? -1 : 1;
  const wholeOrder = a.whole.length === b.whole.length ? (a.whole < b.whole ? -1 : a.whole > b.whole ? 1 : 0) : a.whole.length < b.whole.length ? -1 : 1;
  const precision = Math.max(a.fraction.length, b.fraction.length);
  const aFraction = a.fraction.padEnd(precision, "0");
  const bFraction = b.fraction.padEnd(precision, "0");
  const fractionOrder = aFraction < bFraction ? -1 : aFraction > bFraction ? 1 : 0;
  const result = wholeOrder || fractionOrder;
  return a.negative ? -result : result;
}
export function humanize(value: string) { return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase()); }
export function formatDate(value: string | null | undefined, options?: Intl.DateTimeFormatOptions) {
  const date = value ? new Date(value) : null;
  // Missing or unparseable timestamps render as a dash instead of throwing a RangeError.
  if (!date || Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", options ?? { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" }).format(date);
}
/** Backend alerts carry created_at at the top level; mock fixtures keep it in evidence. */
export function alertCreatedAt(alert: { created_at?: string | null; evidence: Record<string, unknown> }): string | null {
  return alert.created_at ?? (typeof alert.evidence.created_at === "string" ? alert.evidence.created_at : null);
}
export function formatCitation(citation: { source: string; section: string; page: number | null; chunk_id: string }) { return `${citation.source} — ${citation.section}${citation.page === null ? "" : ` — ${citation.page}`} (${citation.chunk_id})`; }
export function downloadJson(filename: string, value: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json;charset=utf-8" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click(); URL.revokeObjectURL(url);
}
export function downloadCsv(filename: string, rows: Array<Record<string, string | number | boolean | null | undefined>>) {
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const escape = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const content = [columns.map(escape).join(","), ...rows.map((row) => columns.map((key) => escape(row[key])).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click(); URL.revokeObjectURL(url);
}
export async function copyText(value: string) { await navigator.clipboard.writeText(value); }
