---
audience: user
---

# AI investigation

## What it is

An **AI investigation** asks AMLens's AI assistant to prepare a draft investigation report for one alert. The assistant works in six steps, then a built-in checker ([verification](../glossary.md)) tests the draft against the evidence. The result is an **investigation** (a case) with a report for you to review.

!!! note "The AI drafts. You decide."
    The AI cannot record a decision. While it runs, the page says *"The agent is preparing a draft report. No decision will be made automatically."*

## Why you would use it

To save time gathering the facts: the assistant summarises the account's activity, finds relevant regulatory guidance, links every claim to its evidence, and lists the information still missing. You then spend your time judging, not collecting.

## Where to find it

On the [Alert review](alert-review.md) page, select **Investigate with AI**.

## Before you start

- The alert has no investigation yet (otherwise you will see **Open investigation** instead).
- The services are healthy. Check the dot at the bottom of the sidebar, or [Settings and service health](settings-and-health.md). If the *Investigation agent* or *AML knowledge retrieval* service is not healthy, the run is likely to fail.

## Start an AI investigation

1. Open the alert.
2. Select **Investigate with AI**.

    **You should see** the button change to **Running investigation…** and an **Investigation in progress** panel with six numbered steps.

3. Wait. Do not close the tab or select the button again. How long a run takes has not been verified; it depends on the AI service.
4. When the run finishes, AMLens opens the **Investigation Review** page with the draft report.

!!! info "The step indicator is approximate"
    The six-step panel moves forward as your browser hears back from AMLens, not in real time from each step. It may sit on one step for most of the run and then jump to the end. That is normal.

## What the six steps do

| Step shown on screen | What it does, in plain terms |
| --- | --- |
| 1. **Transaction Analysis** | Loads the anchor account's transactions from **48 hours before to 48 hours after** the triggering transaction (up to 200) and calculates totals, counts, counterparties and simple patterns, such as several payments within one hour, round amounts, or money in and out close together. |
| 2. **AML Knowledge Retrieval** | Searches the regulatory guidance library for passages about the alert's [typology](../glossary.md) (for example *Unusual activity* or *Rapid movement*). |
| 3. **Evidence Correlation** | Turns each pattern into an **observed fact** linked to its transactions, and, where relevant guidance was found, adds an interpretation and a concern linked to the cited passages. |
| 4. **Information Gap** | Lists what is not known: KYC, source of funds, transaction purpose, sender–beneficiary relationship, counterparty information, economic rationale and supporting documents, each with a question for you. |
| 5. **Report Drafting** | The AI writes the narrative and recommended next steps, using only approved statements. |
| 6. **Verifier** | Independently recalculates the facts and checks the draft. If it fails, the report is redrafted **once** and checked again. |

Which typology is used depends on the rule:

| Rule | Typology used for guidance search |
| --- | --- |
| High Value | Unusual activity |
| Repeated Pair | Unusual activity |
| Rapid Movement Candidate | Rapid movement |

## What happens to the alert and case

- The alert status changes from **OPEN** to **UNDER REVIEW** as soon as the investigation is created.
- The audit trail records **Case created**, then **Agent run requested**, then either **Agent run finished** or **Agent run failed**.

## Possible outcomes

| Run status | Meaning | Can you record a decision? |
| --- | --- | --- |
| **completed** | All steps finished and the report **passed verification**. | Yes: Approve, Reject or Escalate. |
| **incomplete** | All steps finished, but the report **did not pass verification**, even after one redraft. | Yes, but **Approve is disabled**. Reject or Escalate only. |
| **failed** | A step could not finish, usually because a connected service (AI model or guidance search) was unavailable. No report was produced. | No. Run it again first. |

See [Reading the investigation report](investigation-report.md) and [Understanding results](../understanding-results.md).

## Errors and edge cases

| Message on the alert page | Meaning | What to do |
| --- | --- | --- |
| **Agent service unavailable** — *Agent investigation failed; inspect persisted status* | The run failed. The investigation exists with status **failed**. | Select **Open investigation** and use **Run investigation again**. See [Retrying a failed investigation](../workflows/retry-failed-investigation.md). |
| **Investigation already running or linked elsewhere** | Someone (or another tab) is already running this investigation. | Wait a moment, refresh, then select **Open investigation**. |
| **Investigation could not be completed** | Any other problem. | Select **Retry run**. If it fails again, contact your administrator. |

!!! warning "Avoid creating a second investigation"
    If a run failed, the **Investigation draft** tab on the alert page may show *No investigation draft yet* with a **Start investigation** button. Selecting it starts a **new**, separate investigation for the same alert. Retry from the investigation page instead, so the alert keeps a single case history.

## Related pages

- [Reading the investigation report](investigation-report.md)
- [Recording a decision](recording-decisions.md)
- [Retrying a failed investigation](../workflows/retry-failed-investigation.md)
- [Knowledge base](knowledge-base.md)
