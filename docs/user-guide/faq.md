---
audience: user
---

# Frequently asked questions

## General

**What is AMLens for?**
: Reviewing transaction alerts for anti-money-laundering purposes. It flags transactions using simple rules, drafts an AI investigation report, and records your decision with a full audit trail. See [Introduction](introduction.md).

**Does the AI make decisions?**
: No. The AI only drafts a report. Only a signed-in person can record Approve, Reject or Escalate, and must confirm it in a dialog first.

**Does AMLens file SARs or STRs?**
: No. AMLens does not create or submit any regulatory filing. Use your organisation's filing process.

**Does AMLens monitor transactions in real time?**
: No. Alerts are created only when someone uploads a transaction file.

**Who can see my work?**
: Every signed-in user can see all alerts, investigations, decisions and audit events. There are no separate roles or private cases.

## Accounts and sign-in

**How do I get an account?**
: Ask your administrator. Accounts (username and password) are created by an administrator. See [Account and sign-in](account-and-login.md).

**I forgot my password. What do I do?**
: Contact your administrator. There is no self-service reset.

**How do I sign out?**
: There is no sign-out button in the app. Go to `/oauth2/sign_out` on the AMLens address, then close your browser tabs.

**Why does the top-right corner show a name that is not mine?**
: It is a fixed demo placeholder built into the page. Your **signed-in username** is what AMLens records on your decisions.

**Why was I locked out after a few attempts?**
: Sign-in is rate limited to protect accounts. Wait one minute and try again.

## Data and uploads

**What file format do I need?**
: A `.csv` file, 20 MB or less, up to 100,000 rows, with these headings: Timestamp, From Bank, Account, To Bank, Account.1, Amount Received, Receiving Currency, Amount Paid, Payment Currency, Payment Format, Is Laundering. See [Upload transaction data](features/upload-data.md).

**The Upload page lists different field names. Which are right?**
: The headings above. The **Required fields** panel on the page does not match what the upload accepts.

**What happens if I upload the same file twice?**
: The second upload is refused with **Dataset already imported**, and no new transactions or alerts are created. AMLens recognises the file by a fingerprint of its exact contents (the dataset ID).

**What if I change the file slightly and upload it again?**
: It is treated as a new file, and any matching transactions create new, duplicate alerts. Avoid this. Upload only new or corrected rows.

**Are real account numbers stored or shown?**
: Account references are replaced by tokens (for example `ACC_9d2e…`) at upload and are never displayed. Do not put names, emails or other direct identifiers in your file.

**What is the Is Laundering column for?**
: It is part of the accepted file layout and must be `0` or `1`, but AMLens does not use it to create alerts and does not display it.

## Alerts

**Why did this transaction create an alert?**
: Open the alert and read the **Evidence** panel. The three rules are High Value ($1,000,000 or more in US Dollar), Repeated Pair (5 or more payments between the same pair within 48 hours) and Rapid Movement Candidate (in and out of the same account within 60 minutes). See [Introduction](introduction.md).

**Does an alert mean money laundering happened?**
: No. As the app says, *"A rule match is a screening signal and is not proof of suspicious activity."*

**Why can't my search find an alert?**
: Search and filters in the queue only cover the page currently loaded. Set **Rows** to 200, or paste the alert ID into the top-bar search.

**Can I assign an alert to a colleague?**
: No. AMLens has no assignment feature. Agree on ownership within your team, and check for **UNDER REVIEW** before starting.

## AI investigations

**How long does an AI investigation take?**
: It varies with the AI service and has not been measured for this guide. Keep the page open until it finishes.

**What does "incomplete" mean?**
: The AI produced a report, but it did not pass verification even after one automatic redraft. You can still review it and Reject or Escalate, but not Approve.

**What does "failed" mean?**
: No report was produced, usually because a connected service was unavailable. Run it again from the investigation page. See [Retrying a failed investigation](workflows/retry-failed-investigation.md).

**Why does a passing report still say "Review required"?**
: Almost every report carries the warning that intent cannot be established from transaction patterns. Warnings do not stop verification passing. Check the **Verification passed** badge.

**Why are KYC and source of funds always "Not provided"?**
: AMLens does not hold customer information. Obtain it from your own systems and mention it in your rationale.

**Why did the report cite no guidance?**
: No guidance passage was relevant enough (45% or more) for that typology. You can search the [Knowledge base](features/knowledge-base.md) yourself.

## Decisions

**Why can't I approve?**
: Approval needs a **completed** run with **verification passed**. Otherwise choose Reject or Escalate.

**Can I change or delete a decision?**
: No. Only one decision can be recorded per investigation, and it cannot be edited. Follow your organisation's correction procedure if needed.

**Whose name is recorded on the decision?**
: Your signed-in username, regardless of what is in the Analyst ID box.

## Knowledge base

**Why does my search return "No matching passages"?**
: Each typology has only 1–3 verified passages, and only those scoring 40% or more are returned. Write a full sentence in regulatory language and pick the right typology. See [Knowledge base](features/knowledge-base.md) for queries that work.

**Can I open the source documents listed on the page?**
: No. That list is static, illustrative information and the items cannot be opened.

## Exports

**What can I export?**
: Alerts (current page, CSV), investigations (CSV), audit events per investigation (CSV), and each report (JSON or print to PDF). See [Preparing evidence for an audit](workflows/audit-evidence.md).

## Related pages

- [Troubleshooting](troubleshooting.md)
- [Glossary](glossary.md)
- [Understanding results](understanding-results.md)
