# Deploying the AML database to Azure

Target: **Azure Database for PostgreSQL - Flexible Server** (managed PostgreSQL 16).
The main AML data moves here; in a deployment the agents also store their runs here
(schema `agent_runtime`, via `AML_AGENT_DATABASE_URL`). For the whole stack see `../DEPLOY.md`.

> Creating these resources **costs money** (Burstable B1ms is roughly US$13-15/month,
> or free for 12 months on an Azure free account: 750 h of B1ms + 32 GB storage).
> Delete the resource group when you are done experimenting.

## 0. Before you start

- Azure CLI installed and signed in: `az login`, then `az account show` shows the right subscription.
- Pick a region close to your users and to where the backend will run (examples use `centralindia`).
- Pick a **globally unique** server name (lowercase letters, digits, hyphens), e.g. `amlens-pg-<yourinitials>`.

```powershell
$RG       = "rg-amlens"
$LOCATION = "centralindia"
$SERVER   = "amlens-pg-<unique>"
$ADMIN    = "amlensadmin"
$ADMIN_PW = "<strong password: 8+ chars, upper, lower, digit, symbol>"
$MY_IP    = (Invoke-RestMethod https://api.ipify.org)
```

## 1. Create the server and database

```powershell
az group create --name $RG --location $LOCATION

az postgres flexible-server create `
  --resource-group $RG --name $SERVER --location $LOCATION `
  --version 16 --tier Burstable --sku-name Standard_B1ms --storage-size 32 `
  --admin-user $ADMIN --admin-password $ADMIN_PW `
  --public-access $MY_IP          # only your current IP may connect

az postgres flexible-server db create --resource-group $RG --server-name $SERVER --database-name amlens
```

Azure enforces TLS by default, so every connection URL needs `sslmode=require`.

## 2. Create the tables and copy existing data (from your machine)

```powershell
cd backend
$env:DATABASE_URL = "postgresql+psycopg://${ADMIN}:${ADMIN_PW}@${SERVER}.postgres.database.azure.com:5432/amlens?sslmode=require"
alembic upgrade head
python scripts/migrate_sqlite_to_postgres.py     # optional: copy local aml.db
python scripts/check_alerts.py
```

If the password contains `@ : / ? #`, URL-encode it (e.g. `python -c "import urllib.parse;print(urllib.parse.quote('p@ss', safe=''))"`).

Optional SELECT-only login for the agents:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" "host=$SERVER.postgres.database.azure.com dbname=amlens user=$ADMIN sslmode=require" `
  -v reader_password="'<reader password>'" -f scripts/create_readonly_role.sql
```

## 3. Keep secrets out of code: Key Vault

```powershell
$KV = "kv-amlens-<unique>"
az keyvault create --name $KV --resource-group $RG --location $LOCATION
az keyvault secret set --vault-name $KV --name database-url --value $env:DATABASE_URL
az keyvault secret set --vault-name $KV --name token-secret --value (python -c "import secrets;print(secrets.token_hex(32))")
```

Use the **same** `TOKEN_SECRET` as the one that produced your existing data, or old and new account tokens won't match.

## 4. Run the backend in Azure

See `../DEPLOY.md`: the backend image is built from the repository root
(`az acr build -f backend/Dockerfile .`) because it contains the `agents` package, and it
runs on Azure Container Apps with internal ingress behind the frontend.

## 5. Production hardening (later)

- Microsoft Entra ID authentication with the app's managed identity (no DB password at all).
- Private access (VNet) instead of public IP firewall rules.
- Point-in-time restore is on by default (7 days); raise retention / enable geo-redundant backup as needed.
- Scale up (General Purpose tier) before loading the full 5M-row dataset.

## Clean up

```powershell
az group delete --name $RG --yes      # deletes the server, database and Key Vault
```
