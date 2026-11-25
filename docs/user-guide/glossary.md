---
audience: user
---

# Glossary

Plain-language definitions of the terms used in AMLens and in this guide, in alphabetical order.

| Term | Meaning |
| --- | --- |
| **Agent / AI assistant** | The automated software that drafts an investigation report in six steps. It cannot make decisions. See [AI investigation](features/ai-investigation.md). |
| **Alert** | A record created when an uploaded transaction (or group of transactions) matches a screening rule. An alert is a reason to look, not proof of wrongdoing. |
| **Alert ID** | The unique code of an alert, starting with `AL_` followed by the dataset ID and a number. Case-sensitive. |
| **AML (anti-money laundering)** | The laws, controls and processes that financial organisations use to detect and prevent the movement of criminal proceeds. |
| **Analyst ID** | A box on the decision form. On the live site, AMLens records your signed-in username instead of what is typed here. |
| **Anchor account** | The account an alert is about. For High Value and Repeated Pair it is the sender; for Rapid Movement it is the account money passed through. |
| **Append-only** | Records can be added but not edited or deleted. The audit trail works this way. |
| **Approve** | A decision accepting the verified AI report. Only possible when the run completed and verification passed. |
| **Audit trail** | The time-ordered history of events for an investigation: created, run requested, run finished or failed, decision recorded. See [Audit trail](features/audit-trail.md). |
| **Case** | Another word for an investigation. |
| **Chunk / passage** | A short section of a regulatory guidance document stored in the knowledge base. Each has an ID, source and section. |
| **Citation** | A reference in a report to a guidance passage. Select it to read the passage. |
| **Claim type** | How a statement in the report is classified: observed fact, supported interpretation, potential concern, or unsupported assumption. |
| **Counterparty** | The other party in a transaction: the receiver if the anchor account sent money, or the sender if it received money. |
| **CSV (comma-separated values)** | A plain-text spreadsheet file format where columns are separated by commas. The only upload format AMLens accepts. |
| **Dataset ID** | A 20-character code calculated from the exact contents of an uploaded file. The same file always gets the same ID, which is how AMLens refuses duplicate uploads. |
| **Decision / disposition** | The final human outcome for an investigation: Approve, Reject or Escalate. Recorded once and cannot be changed. |
| **Degraded** | A service health status meaning a service is running on a stand-in rather than the real service. |
| **Deposit / withdrawal** | In the report's transaction analysis: money coming into the anchor account (deposit) or going out of it (withdrawal). |
| **Escalate** | A decision requesting further review, context or referral. |
| **Execution status** | The status of the AI run: pending, running, completed, incomplete or failed. |
| **False positive** | An alert that, on review, does not indicate suspicious activity. Recorded with **Reject / close as false positive**. |
| **Fan-in / fan-out** | A pattern where many accounts send money to one account (fan-in), or one account sends money to many (fan-out). A typology in the knowledge base. |
| **High Value** | A screening rule: a single US Dollar payment of $1,000,000 or more. |
| **Incomplete** | An AI run that produced a report that did not pass verification. Approve is disabled. |
| **Information gap** | Information the report needs but AMLens does not have, such as KYC or source of funds, with a question for you to answer. |
| **Investigation** | The case created when you start an AI investigation on an alert. Holds the report, verification, decision and audit events. Its ID is a long code. |
| **KYC (know your customer)** | The process of verifying a customer's identity and understanding their expected activity. AMLens holds no KYC data. |
| **Knowledge base** | The searchable library of verified regulatory guidance passages. See [Knowledge base](features/knowledge-base.md). |
| **Layering** | A money-laundering stage in which funds are moved through accounts to hide their origin. Rapid movement can be a sign of it. |
| **Mock data** | Demonstration data used for testing. The top bar shows **DEV · Mock data** in this mode; the live site shows **LIVE API**. |
| **Observed fact** | A claim calculated directly from transactions, linked to transaction IDs. |
| **Payment format / payment rail** | How a payment was made, for example Wire, ACH, Cash or Cheque. |
| **RAG (retrieval-augmented generation)** | The technique of searching a document library and giving the relevant passages to the AI. In AMLens this is the guidance search used for citations. Shown as *RAG service* or *AML knowledge retrieval* in service health. |
| **Rapid Movement Candidate** | A screening rule: money arrives in and leaves the same account, in the same currency, within 60 minutes. |
| **Rate limiting** | A limit on how many requests can be made in a period. Sign-in is rate limited to slow down password guessing. |
| **Rationale** | Your written explanation for a decision. Required, 10–5,000 characters, stored permanently. |
| **Red flag** | A pattern that may indicate risk and needs human review. Not proof of wrongdoing. |
| **Reject** | A decision closing the alert, typically as a false positive. |
| **Relevance score** | A percentage showing how closely a guidance passage matches a search in meaning. The knowledge base shows passages of 40% or more; reports cite passages of 45% or more. |
| **Repeated Pair** | A screening rule: five or more payments from the same sender to the same receiver, in the same currency, within 48 hours. |
| **Rule** | A fixed condition that creates an alert when a transaction matches it. AMLens uses three: High Value, Repeated Pair, Rapid Movement Candidate. |
| **SAR / STR** | Suspicious Activity Report / Suspicious Transaction Report: a regulatory filing made to authorities. AMLens does not create or submit these. |
| **Source of funds** | Where the money in a transaction came from, for example salary or a property sale. Listed as an information gap in reports. |
| **Structuring** | Splitting transactions into smaller amounts to stay below reporting thresholds. A typology in the knowledge base. |
| **Token / tokenisation** | Replacing a real account reference with a code such as `ACC_9d2e…`. The same account always gets the same token. AMLens tokenises accounts at upload. |
| **Transaction ID** | The code AMLens gives each uploaded transaction, starting with `TX_`, the dataset ID and the row number. |
| **Typology** | A recognised category of money-laundering pattern, for example Structuring, Rapid movement, Fan-in / fan-out, Unusual activity. Each alert is mapped to one for guidance search. |
| **Unusual activity** | Transactions that are large, complex or unusually patterned compared with what is expected, without an apparent economic purpose. The typology used for High Value and Repeated Pair alerts. |
| **Unsupported assumption** | Something the report explicitly says cannot be established from the data, such as intent. |
| **Verification** | The automatic check of every AI draft against independently recalculated evidence. Passed means the report is faithful to the evidence; it does not judge the customer. See [Understanding results](understanding-results.md). |
