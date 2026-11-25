---
title: AMLens Documentation
hide:
  - navigation
  - toc
---

<div class="amlens-hero" markdown>

# AMLens documentation

AMLens helps anti-money-laundering (AML) analysts review suspicious transactions. It flags
unusual payments, drafts an evidence-linked investigation report with AI, and records the
analyst's final decision in a complete audit trail. **The AI drafts; a person decides.**

</div>

## Choose your guide

<div class="amlens-audiences" markdown>

<a class="amlens-audience-card user" href="user-guide/">
  <span class="amlens-card-title">I'm an application user</span>
  <span class="amlens-card-body">You review alerts, read investigation reports and record decisions.
  No technical knowledge needed: step-by-step guides, screenshots and plain-language explanations.</span>
  <span class="amlens-card-cta">Open the user guide →</span>
</a>

<a class="amlens-audience-card developer" href="developer-guide/">
  <span class="amlens-card-title">I'm a developer</span>
  <span class="amlens-card-body">You build, run, test, deploy or operate AMLens. Architecture,
  modules, API and database reference, the AI agent pipeline, and the production runbook.</span>
  <span class="amlens-card-cta">Open the developer guide →</span>
</a>

</div>

## Popular pages

<div class="grid cards" markdown>

-   :material-rocket-launch-outline: **Your first case, end to end**

    ---

    Upload a file, open an alert, run the AI investigation and record a decision.

    [:octicons-arrow-right-24: Start the walkthrough](user-guide/workflows/first-case-end-to-end.md)

-   :material-help-circle-outline: **Understanding results**

    ---

    What every status, score and report section means, and what to do next.

    [:octicons-arrow-right-24: Read the guide](user-guide/understanding-results.md)

-   :material-sitemap-outline: **System architecture**

    ---

    How the frontend, backend, AI agents and guidance search fit together.

    [:octicons-arrow-right-24: See the architecture](developer-guide/architecture/system-architecture.md)

-   :material-laptop: **Run AMLens locally**

    ---

    Install the services and run the full stack on your machine.

    [:octicons-arrow-right-24: Local development](developer-guide/getting-started/local-development.md)

-   :material-api: **API reference**

    ---

    Every backend, agent and guidance-search endpoint, with examples.

    [:octicons-arrow-right-24: Browse the API](developer-guide/api-reference/overview.md)

-   :material-kubernetes: **Production environment**

    ---

    The live Azure Kubernetes Service deployment and how to operate it.

    [:octicons-arrow-right-24: Deployment](developer-guide/deployment/index.md)

</div>

## What AMLens does, in one picture

```mermaid
flowchart LR
    A[Transaction file<br/>CSV] -->|Upload| B[Detection rules]
    B -->|Suspicious patterns| C[Alerts]
    C -->|Analyst starts| D[AI investigation]
    D -->|Draft report<br/>with evidence and guidance| E[Analyst review]
    E -->|Approve, reject or escalate| F[Decision]
    F --> G[Audit trail]
```

!!! info "Scope"
    AMLens is decision support for analysts. It does **not** make decisions on its own,
    file regulatory reports (SAR/STR), or monitor payments in real time.
