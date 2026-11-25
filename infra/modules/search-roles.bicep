// Lets the RAG identity query the AI Search index with Entra ID (no admin key).
// The Search service must allow RBAC: Settings > Keys > "Both" or "Role-based access control".
param searchServiceName string
param principalId string

var searchIndexDataReader = '1407120a-92aa-4202-b7e9-c0e197c71c8f'

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

resource role 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, principalId, searchIndexDataReader)
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataReader)
  }
}
