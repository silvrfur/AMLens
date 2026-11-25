// Lets the given identities call the Azure OpenAI account with Entra ID (no keys).
param openAIAccountName string
param openAIPrincipalIds array

var cognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource openAI 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAIAccountName
}

resource roles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for p in openAIPrincipalIds: {
  scope: openAI
  name: guid(openAI.id, p, cognitiveServicesOpenAIUser)
  properties: {
    principalId: p
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUser)
  }
}]
