---
audience: developer
---

# Prerequisites

Install these tools before you follow [Installation](installation.md). Which ones you need
depends on what you work on: the frontend alone runs on mock data with only Node.js and pnpm.

## Required tools

| Tool | Version | Needed for | Source of truth |
|---|---|---|---|
| **Git** | any recent 2.x | Cloning, branches, `.gitattributes` line-ending rules | - |
| **Python** | **3.12** recommended (3.11+ documented as minimum) | Backend, agents, RAG, tests, documentation site | `python:3.12-slim` in `backend/Dockerfile` and `RAG/Dockerfile`; `python-version: "3.12"` in CI |
| **Node.js** | **20** recommended (18.17+ is Next.js 14's minimum) | Frontend | `node:20-alpine` in `frontend/Dockerfile`; `node-version: "20"` in CI |
| **pnpm** | **12.3.4** (pinned) | Frontend dependencies and scripts | `"packageManager": "pnpm@12.3.4"` in `frontend/package.json` |
| **Docker Desktop** (or Docker Engine with Compose v2) | any current | Development PostgreSQL 16; production-like run of the images | `backend/docker-compose.yml`, `docker-compose.yml` |
| **PostgreSQL** | **16** | Main AML data, test database, agent runtime schema in deployments | `image: postgres:16` in `backend/docker-compose.yml` and CI |

!!! tip "You do not need to install PostgreSQL"
    `backend/docker-compose.yml` runs PostgreSQL 16 in Docker on `127.0.0.1:5433` with the
    development login `amlens` / `amlens_dev` and two databases, `amlens` (app) and
    `amlens_test` (wiped by tests). A locally installed PostgreSQL 16 also works; see
    [Installation](installation.md#alternative-a-locally-installed-postgresql-16).

### What each role needs

| You work on | Git | Python | Node.js + pnpm | Docker |
|---|:---:|:---:|:---:|:---:|
| Frontend only (mock mode) | ✓ | | ✓ | |
| Backend or agents | ✓ | ✓ | | ✓ (database) |
| RAG service | ✓ | ✓ | | |
| Full stack, local | ✓ | ✓ | ✓ | ✓ |
| Production-like run (`docker-compose.yml`) | ✓ | | | ✓ |
| Documentation site | ✓ | ✓ | | |

## Optional tools

| Tool | Needed for |
|---|---|
| **Azure CLI** (`az`) | Only for deployment and for Entra ID authentication to Azure OpenAI / AI Search from your machine (`az login`) when you leave the API keys empty. See [Deployment](../deployment/index.md). |
| **kubectl** | Operating the AKS deployment. See [Operations runbook](../deployment/operations-runbook.md). |
| **Bash** (Git Bash on Windows) | The deployment scripts in `deploy/aks/` and `infra/seed/` are Bash scripts. Local development does not need Bash. |
| **An editor with Python and TypeScript support** | The repository has no shared editor configuration, linters or formatters; use your own. |

## Accounts and credentials

Local development works fully **offline**: the backend defaults to the mock LLM and mock
RAG, and the frontend defaults to built-in mock data. You need credentials only to exercise
the live AI services.

| Credential | Needed when | How to get it |
|---|---|---|
| `TOKEN_SECRET` (team value) | Always for the backend, as soon as you upload data | Ask the team. It is shared privately, never committed. See [Configuration](configuration.md#token_secret). |
| Azure OpenAI endpoint, chat deployment and key | `USE_MOCK_LLM=false` | Ask the team, or leave the key empty and use `az login` with the *Cognitive Services OpenAI User* role. |
| Azure AI Search endpoint, index and key; Azure OpenAI embedding deployment | Running the RAG service with `RAG_BACKEND=azure` | Ask the team. |
| GitHub access to `silvrfur/AMLens` | Cloning and opening pull requests | Repository owner. |

!!! danger "Never commit secrets"
    `.env`, `.env.*` and `.env.local` files are git-ignored. Only the `*.env.example`
    templates are committed. Never put real keys in an example file, a test, a commit
    message, or these docs.

## Operating system notes

AMLens is developed on Windows (PowerShell) and Linux, and CI runs on `ubuntu-latest`. The
commands in this guide are given for PowerShell and for Bash (Linux, macOS, Git Bash).

=== "Windows"

    - Use **PowerShell** for the local-development commands. If activating a virtual
      environment fails with "running scripts is disabled", run
      `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
    - Start **Docker Desktop** and wait for "Engine running" before `docker compose up`.
    - Use `127.0.0.1`, not `localhost`, in database URLs: on Windows `localhost` may try
      IPv6 first, which the Docker port mapping does not listen on, causing ~8-second stalls.
    - Keep Git's default `core.autocrlf=true` if you like; `.gitattributes` forces LF for
      shell scripts, Dockerfiles, Bicep and YAML. See
      [Common setup issues](local-development.md#common-setup-issues).

=== "Linux / macOS"

    - Use `python3 -m venv` and `source .venv/bin/activate`.
    - Docker Engine with the Compose v2 plugin (`docker compose`) is enough.
    - On Linux, the production-like compose run reaches the development database through
      `host.docker.internal`, which `docker-compose.yml` maps with `host-gateway`.

## Check your setup

=== "PowerShell"

    ```powershell
    git --version
    python --version          # 3.12.x recommended
    node --version            # v20.x recommended
    npx pnpm --version        # 12.3.4 (Corepack or npx resolves the pinned version)
    docker --version
    docker compose version
    ```

=== "Bash"

    ```bash
    git --version
    python3 --version         # 3.12.x recommended
    node --version            # v20.x recommended
    npx pnpm --version        # 12.3.4
    docker --version
    docker compose version
    ```

??? note "Validated on the documentation machine"
    On the Windows Server 2022 machine used to write this guide: Git 2.56, Python 3.14.8,
    Node.js 24.21, pnpm 12.3.4, Docker 29.8. The agent test suite passed on Python 3.14.8
    and the frontend type-check passed on Node.js 24, but the **supported** versions are the
    ones the images and CI use: Python 3.12 and Node.js 20.

## Next step

Continue with [Installation](installation.md).
