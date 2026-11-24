// AMLens on Azure Container Apps. Deploy with infra/deploy.ps1 (see DEPLOY.md).
//
//  frontend (public, Entra ID sign-in) --proxy--> backend (internal) --> PostgreSQL (private access only)
//                                      \--proxy--> rag (internal) ----> Azure AI Search / Azure OpenAI
//
// Two passes: deployApps=false creates the platform (network, database, registry, Key Vault,
// identities, environment); after the images are pushed, deployApps=true adds the apps and jobs.

targetScope = 'resourceGroup'

@description('Region for everything in this resource group. Prefer the region of the Azure OpenAI / AI Search resources.')
param location string = resourceGroup().location

@description('Short lowercase prefix for resource names.')
@maxLength(10)
param prefix string = 'amlens'

@description('Object ID of the person or pipeline running the deployment (gets Key Vault Secrets Officer so deploy.ps1 can reuse generated secrets).')
param deployerObjectId string

@description('Principal type of deployerObjectId.')
@allowed(['User', 'ServicePrincipal'])
param deployerPrincipalType string = 'User'

// ---- Secrets (all stored in Key Vault, never in app settings) --------------------------------
@secure()
@description('PostgreSQL administrator password (deploy.ps1 generates it once and reuses it).')
param postgresAdminPassword string

@secure()
@description('Account tokenisation secret. Must equal the TOKEN_SECRET that produced the existing data.')
param tokenSecret string

@secure()
@description('Shared secret between the frontend proxy and the backend (deploy.ps1 generates it once).')
param proxyKey string

// ---- Existing AI resources --------------------------------------------------------------------
@description('Azure OpenAI endpoint, e.g. https://<resource>.openai.azure.com/')
param azureOpenAIEndpoint string
param azureOpenAIChatDeployment string = 'gpt-4.1-mini'
param azureOpenAIEmbeddingDeployment string = 'text-embedding-3-small'
@description('Azure AI Search endpoint, e.g. https://<service>.search.windows.net')
param azureSearchEndpoint string
param azureSearchIndexName string = 'amlens-guidance-v1'

@description('managedIdentity: apps call Azure OpenAI / AI Search with their identities (needs the two resource IDs below, and the Search service must allow RBAC). keys: use the two keys below.')
@allowed(['managedIdentity', 'keys'])
param aiAuth string = 'managedIdentity'
@description('Resource ID of the Azure OpenAI (AI Services) account, for role assignments (managedIdentity mode).')
param azureOpenAIResourceId string = ''
@description('Resource ID of the Azure AI Search service, for role assignments (managedIdentity mode).')
param azureSearchResourceId string = ''
@secure()
param azureOpenAIKey string = ''
@secure()
param azureSearchKey string = ''

// ---- Sign-in (Entra ID app registration for the frontend) --------------------------------------
@description('Client ID of the Entra ID app registration used for sign-in. Empty = no sign-in (only for a throwaway test deployment with no real data).')
param authClientId string = ''
@secure()
param authClientSecret string = ''

// ---- Apps --------------------------------------------------------------------------------------
param deployApps bool = false
@description('Image tag to run (git SHA from the pipeline).')
param imageTag string = 'latest'
@description('Create the one-off data seed job (image amlens-seed:<imageTag> must exist).')
param deploySeedJob bool = false

@description('Days of PostgreSQL point-in-time restore (7-35).')
@minValue(7)
@maxValue(35)
param postgresBackupRetentionDays int = 14
@allowed(['Enabled', 'Disabled'])
param postgresGeoRedundantBackup string = 'Disabled'

var suffix = uniqueString(resourceGroup().id)
var names = {
  logs: 'log-${prefix}-${suffix}'
  vnet: 'vnet-${prefix}'
  acr: 'acr${prefix}${suffix}'
  kv: 'kv-${prefix}-${take(suffix, 8)}'
  pg: '${prefix}-pg-${suffix}'
  env: 'cae-${prefix}'
  rag: '${prefix}-rag'
  backend: '${prefix}-backend'
  frontend: '${prefix}-frontend'
  migrate: '${prefix}-migrate'
  seed: '${prefix}-seed'
}
var useKeys = aiAuth == 'keys'
var roles = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  kvSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  kvSecretsOfficer: 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
}

// ================================ Monitoring ================================
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: names.logs
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ================================ Network ===================================
resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: names.vnet
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.40.0.0/16'] }
    subnets: [
      {
        name: 'snet-apps'
        properties: {
          addressPrefix: '10.40.0.0/23'
          delegations: [{ name: 'apps', properties: { serviceName: 'Microsoft.App/environments' } }]
        }
      }
      {
        name: 'snet-postgres'
        properties: {
          addressPrefix: '10.40.2.0/24'
          delegations: [{ name: 'pg', properties: { serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers' } }]
        }
      }
    ]
  }
}

resource pgDns 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: '${prefix}.private.postgres.database.azure.com'
  location: 'global'
}

resource pgDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: pgDns
  name: 'link-${names.vnet}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

// ================================ Database ==================================
// Private access only: reachable from the VNet (the apps and jobs), not from the internet.
resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: names.pg
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: 'amlensadmin'
    administratorLoginPassword: postgresAdminPassword
    storage: { storageSizeGB: 32, autoGrow: 'Enabled' }
    backup: {
      backupRetentionDays: postgresBackupRetentionDays
      geoRedundantBackup: postgresGeoRedundantBackup
    }
    network: {
      delegatedSubnetResourceId: '${vnet.id}/subnets/snet-postgres'
      privateDnsZoneArmResourceId: pgDns.id
      publicNetworkAccess: 'Disabled'
    }
    highAvailability: { mode: 'Disabled' }
  }
  dependsOn: [pgDnsLink]
}

resource pgDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: pg
  name: 'amlens'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

// libpq URL: accepted by the backend (normalised to psycopg), the agents and psql.
var databaseUrl = 'postgresql://amlensadmin:${uriComponent(postgresAdminPassword)}@${pg.properties.fullyQualifiedDomainName}:5432/amlens?sslmode=require'

// ================================ Registry ==================================
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: names.acr
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }   // pulls use managed identities
}

// ================================ Key Vault =================================
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: names.kv
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true          // no access policies; identities get roles
    enableSoftDelete: true
    softDeleteRetentionInDays: 30
    enablePurgeProtection: true
  }
}

var secretValues = union({
  'database-url': databaseUrl
  'pg-admin-password': postgresAdminPassword
  'token-secret': tokenSecret
  'proxy-key': proxyKey
}, useKeys ? {
  'azure-openai-key': azureOpenAIKey
  'azure-search-key': azureSearchKey
} : {}, empty(authClientId) ? {} : {
  'auth-client-secret': authClientSecret
})

// Loop over the names (known at deployment start); values may depend on the server FQDN.
var secretNames = concat(['database-url', 'pg-admin-password', 'token-secret', 'proxy-key'],
  useKeys ? ['azure-openai-key', 'azure-search-key'] : [],
  empty(authClientId) ? [] : ['auth-client-secret'])

resource secrets 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = [for name in secretNames: {
  parent: kv
  name: name
  properties: { value: secretValues[name] }
}]

resource deployerKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, deployerObjectId, roles.kvSecretsOfficer)
  properties: {
    principalId: deployerObjectId
    principalType: deployerPrincipalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.kvSecretsOfficer)
  }
}

// ================================ Identities ================================
// One user-assigned identity per app (and one for the jobs), so role assignments exist
// before the apps start and each app gets only what it needs.
var identityNames = ['rag', 'backend', 'frontend', 'jobs']

resource ids 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = [for n in identityNames: {
  name: 'id-${prefix}-${n}'
  location: location
}]

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (n, i) in identityNames: {
  scope: acr
  name: guid(acr.id, n, roles.acrPull)
  properties: {
    principalId: ids[i].properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
  }
}]

resource kvRead 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (n, i) in identityNames: {
  scope: kv
  name: guid(kv.id, n, roles.kvSecretsUser)
  properties: {
    principalId: ids[i].properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.kvSecretsUser)
  }
}]

// Keyless Azure OpenAI / AI Search (the AI resources may live in another resource group).
// Resource IDs look like /subscriptions/<sub>/resourceGroups/<rg>/providers/<type>/<name>.
var openAIParts = useKeys ? ['', '', subscription().subscriptionId, '', resourceGroup().name, '', '', '', 'unused'] : split(azureOpenAIResourceId, '/')
var searchParts = useKeys ? ['', '', subscription().subscriptionId, '', resourceGroup().name, '', '', '', 'unused'] : split(azureSearchResourceId, '/')

module aiRoles 'modules/ai-roles.bicep' = if (!useKeys) {
  name: 'ai-roles'
  scope: resourceGroup(openAIParts[2], openAIParts[4])
  params: {
    openAIAccountName: last(openAIParts)
    openAIPrincipalIds: [ids[0].properties.principalId, ids[1].properties.principalId]
  }
}

module searchRoles 'modules/search-roles.bicep' = if (!useKeys) {
  name: 'search-roles'
  scope: resourceGroup(searchParts[2], searchParts[4])
  params: {
    searchServiceName: last(searchParts)
    principalId: ids[0].properties.principalId
  }
}

// ================================ Environment ===============================
resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: names.env
  location: location
  properties: {
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
    vnetConfiguration: {
      infrastructureSubnetId: '${vnet.id}/subnets/snet-apps'
      internal: false                     // the frontend needs a public endpoint
    }
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// ================================ Apps ======================================
var kvUri = kv.properties.vaultUri
func kvSecret(vaultUri string, name string, identityId string) object => {
  name: name
  keyVaultUrl: '${vaultUri}secrets/${name}'
  identity: identityId
}
func probes(port int) array => [
  { type: 'Liveness', httpGet: { path: '/health', port: port }, periodSeconds: 30, failureThreshold: 3 }
  { type: 'Readiness', httpGet: { path: '/health', port: port }, periodSeconds: 10, failureThreshold: 3 }
]

var openAIBase = endsWith(azureOpenAIEndpoint, '/') ? azureOpenAIEndpoint : '${azureOpenAIEndpoint}/'

resource rag 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: names.rag
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${ids[0].id}': {} } }
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      // Internal only. allowInsecure: plain HTTP inside the environment (no redirect to HTTPS).
      ingress: { external: false, targetPort: 8001, transport: 'http', allowInsecure: true }
      registries: [{ server: acr.properties.loginServer, identity: ids[0].id }]
      secrets: useKeys ? [
        kvSecret(kvUri, 'azure-openai-key', ids[0].id)
        kvSecret(kvUri, 'azure-search-key', ids[0].id)
      ] : []
    }
    template: {
      containers: [{
        name: 'rag'
        image: '${acr.properties.loginServer}/amlens-rag:${imageTag}'
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: concat([
          { name: 'RAG_BACKEND', value: 'azure' }
          { name: 'AZURE_SEARCH_ENDPOINT', value: azureSearchEndpoint }
          { name: 'AZURE_SEARCH_INDEX_NAME', value: azureSearchIndexName }
          { name: 'AZURE_OPENAI_BASE_URL', value: '${openAIBase}openai/v1/' }
          { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: azureOpenAIEmbeddingDeployment }
          { name: 'AZURE_CLIENT_ID', value: ids[0].properties.clientId }
        ], useKeys ? [
          { name: 'AZURE_OPENAI_API_KEY', secretRef: 'azure-openai-key' }
          { name: 'AZURE_SEARCH_ADMIN_KEY', secretRef: 'azure-search-key' }
        ] : [])
        probes: probes(8001)
      }]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
  dependsOn: [acrPull, kvRead, secrets, aiRoles, searchRoles]
}

resource backend 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: names.backend
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${ids[1].id}': {} } }
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: false, targetPort: 8000, transport: 'http', allowInsecure: true }
      registries: [{ server: acr.properties.loginServer, identity: ids[1].id }]
      secrets: concat([
        kvSecret(kvUri, 'database-url', ids[1].id)
        kvSecret(kvUri, 'token-secret', ids[1].id)
        kvSecret(kvUri, 'proxy-key', ids[1].id)
      ], useKeys ? [kvSecret(kvUri, 'azure-openai-key', ids[1].id)] : [])
    }
    template: {
      containers: [{
        name: 'backend'
        image: '${acr.properties.loginServer}/amlens-backend:${imageTag}'
        resources: { cpu: json('1.0'), memory: '2Gi' }
        env: concat([
          { name: 'DATABASE_URL', secretRef: 'database-url' }
          { name: 'AML_AGENT_DATABASE_URL', secretRef: 'database-url' }
          { name: 'TOKEN_SECRET', secretRef: 'token-secret' }
          { name: 'AML_PROXY_KEY', secretRef: 'proxy-key' }
          { name: 'AML_SOURCE_TIMEZONE', value: 'UTC' }
          { name: 'USE_MOCK_LLM', value: 'false' }
          { name: 'LLM_PROVIDER', value: 'azure_openai' }
          { name: 'AZURE_OPENAI_ENDPOINT', value: openAIBase }
          { name: 'AZURE_OPENAI_DEPLOYMENT', value: azureOpenAIChatDeployment }
          { name: 'AZURE_CLIENT_ID', value: ids[1].properties.clientId }
          { name: 'USE_MOCK_RAG', value: 'false' }
          { name: 'RAG_SERVICE_URL', value: 'http://${names.rag}' }
          { name: 'RUN_MIGRATIONS', value: 'false' }   // the migrate job runs them
        ], useKeys ? [{ name: 'AZURE_OPENAI_API_KEY', secretRef: 'azure-openai-key' }] : [])
        probes: probes(8000)
      }]
      // Agent runs and their leases live in PostgreSQL, so several replicas are safe.
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
  dependsOn: [acrPull, kvRead, secrets, aiRoles, pgDb, rag]   // RAG first, then backend
}

resource frontend 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: names.frontend
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${ids[2].id}': {} } }
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 3000, transport: 'http', allowInsecure: false }
      registries: [{ server: acr.properties.loginServer, identity: ids[2].id }]
      secrets: concat([kvSecret(kvUri, 'proxy-key', ids[2].id)],
        empty(authClientId) ? [] : [{
          name: 'microsoft-provider-authentication-secret'
          keyVaultUrl: '${kvUri}secrets/auth-client-secret'
          identity: ids[2].id
        }])
    }
    template: {
      containers: [{
        name: 'frontend'
        image: '${acr.properties.loginServer}/amlens-frontend:${imageTag}'
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: [
          { name: 'AMLENS_BACKEND_URL', value: 'http://${names.backend}' }
          { name: 'AMLENS_RAG_URL', value: 'http://${names.rag}' }
          { name: 'AMLENS_PROXY_KEY', secretRef: 'proxy-key' }
        ]
      }]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
  dependsOn: [acrPull, kvRead, secrets, backend]   // frontend last
}

// Entra ID sign-in in front of the whole frontend (and therefore the proxy).
resource frontendAuth 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (deployApps && !empty(authClientId)) {
  parent: frontend
  name: 'current'
  properties: {
    platform: { enabled: true }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
      // Status only (no data), so the pipeline and uptime checks can read it.
      excludedPaths: ['/api/backend/health']
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: authClientId
          clientSecretSettingName: 'microsoft-provider-authentication-secret'
          openIdIssuer: '${environment().authentication.loginEndpoint}${subscription().tenantId}/v2.0'
        }
        validation: { allowedAudiences: ['api://${authClientId}'] }
      }
    }
  }
}

// ================================ Jobs ======================================
// Jobs run inside the VNet, so they can reach the private database.
var jobBase = {
  environmentId: env.id
  workloadProfileName: 'Consumption'
  configuration: {
    triggerType: 'Manual'
    replicaTimeout: 900
    replicaRetryLimit: 0
    manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
    registries: [{ server: acr.properties.loginServer, identity: ids[3].id }]
    secrets: [kvSecret(kvUri, 'database-url', ids[3].id)]
  }
}

resource migrateJob 'Microsoft.App/jobs@2024-03-01' = if (deployApps) {
  name: names.migrate
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${ids[3].id}': {} } }
  properties: union(jobBase, {
    template: {
      containers: [{
        name: 'migrate'
        image: '${acr.properties.loginServer}/amlens-backend:${imageTag}'
        command: ['alembic', 'upgrade', 'head']
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: [{ name: 'DATABASE_URL', secretRef: 'database-url' }]
      }]
    }
  })
  dependsOn: [acrPull, kvRead, secrets, pgDb]
}

resource seedJob 'Microsoft.App/jobs@2024-03-01' = if (deployApps && deploySeedJob) {
  name: names.seed
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${ids[3].id}': {} } }
  properties: union(jobBase, {
    template: {
      containers: [{
        name: 'seed'
        image: '${acr.properties.loginServer}/amlens-seed:${imageTag}'
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: [{ name: 'DATABASE_URL', secretRef: 'database-url' }]
      }]
    }
  })
  dependsOn: [acrPull, kvRead, secrets, pgDb]
}

output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
output keyVaultName string = kv.name
output environmentName string = env.name
output postgresServer string = pg.properties.fullyQualifiedDomainName
output frontendUrl string = deployApps ? 'https://${frontend!.properties.configuration.ingress.fqdn}' : ''
output migrateJobName string = names.migrate
output seedJobName string = names.seed
output appNames object = { rag: names.rag, backend: names.backend, frontend: names.frontend }
