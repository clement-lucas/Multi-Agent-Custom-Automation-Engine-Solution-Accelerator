# Bing Grounding Setup - Remaining Steps

All code has been uncommented and environment variables are configured. Follow these steps to complete the setup:

## Step 1: Create Bing Search Grounding Resource

Run these commands in your terminal (replace placeholders with your values):

```bash
# Set your variables
RESOURCE_GROUP="<your-resource-group-name>"
ACCOUNT_NAME="<unique-bing-resource-name>"  # e.g., "binggrnd-macae"
LOCATION="global"   # Must be 'global'
SKU="G1"
KIND="Bing.Grounding"

# Get subscription ID
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/microsoft.bing/accounts/$ACCOUNT_NAME"

# Register Bing provider (one-time setup, may take a few minutes)
az provider register --namespace Microsoft.Bing

# Check registration status
az provider show --namespace Microsoft.Bing --query "registrationState"

# Wait for "Registered" status before proceeding

# Create the Bing Search Grounding resource
az rest --method put \
  --url "https://management.azure.com$RESOURCE_ID?api-version=2020-06-10" \
  --body "{
    \"location\": \"$LOCATION\",
    \"kind\": \"$KIND\",
    \"sku\": { \"name\": \"$SKU\" },
    \"properties\": {}
  }"

# Verify creation
az resource show --ids "$RESOURCE_ID" --api-version 2020-06-10 -o table
```

## Step 2: Connect Bing to Azure AI Foundry

1. Open [Azure AI Studio](https://ai.azure.com)
2. Navigate to your AI Foundry project
3. Go to **Management center** → **Connected resources**
4. Click **+ New connection**
5. Select **Grounding with Bing Search**
6. Choose the Bing resource you created
7. **Important**: Name the connection **`binggrnd`** (this matches the environment variable configuration)
8. Click **Create**

## Step 3: Verify Local Authentication is Enabled (CRITICAL)

⚠️ **Critical**: Bing Search Grounding only supports API key authentication.

**This is the most common cause of the 401 Unauthorized error!**

### Check Local Authentication Status:

```bash
# Get your AI Foundry resource name from the deployment
AI_FOUNDRY_RESOURCE=$(az resource list --resource-type "Microsoft.CognitiveServices/accounts" \
  --query "[?kind=='AIServices'].name" -o tsv | head -1)

# Check if local auth is enabled
az cognitiveservices account show \
  --name $AI_FOUNDRY_RESOURCE \
  --resource-group $RESOURCE_GROUP \
  --query "properties.disableLocalAuth" -o tsv
```

**Expected output: `false`** (meaning local auth is ENABLED)

If the output is `true`, you need to enable it:

```bash
# Enable local authentication
az cognitiveservices account update \
  --name $AI_FOUNDRY_RESOURCE \
  --resource-group $RESOURCE_GROUP \
  --set properties.disableLocalAuth=false
```

### Alternative: Check in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your AI Services resource (the one used by your AI Foundry project)
3. Go to **Settings** → **Keys and Endpoint** (or **Resource Management**)
4. Look for **Local Authentication** setting
5. Ensure it is **Enabled**
6. If not, enable it and save

⚠️ **Without local authentication enabled, you will get this error:**
```
Error: bing_search_user_error; [bing_search] Failed to call Get Bing Grounding Search Results API with status 401: 
{ "statusCode": 401, "message": "Unauthorized. Access token is missing, invalid, audience is incorrect (https://bing.azure.com), or have expired." }
```

## Step 4: Enable Bing in Agent Configuration

Update your agent team JSON files (in `data/agent_teams/`) to enable Bing for specific agents:

```json
{
  "name": "ResearchAgent",
  "description": "Performs research tasks",
  "system_message": "You are a research agent...",
  "use_bing": true,  // ← Set to true
  "use_rag": false,
  "use_mcp": false,
  "coding_tools": false
}
```

**Note**: Reasoning models (o3, o4-mini) cannot use Bing. Only set `use_bing: true` for regular models.

## Step 5: Redeploy Application

Run the deployment script to apply all changes:

```bash
./deploy_with_acr.sh
```

## Step 6: Verify Bing is Working

After deployment:

1. Check container app logs for successful Bing tool creation:
   ```
   INFO:v3.magentic_agents.foundry_agent:Bing tool created with connection <connection-id>
   INFO:v3.magentic_agents.foundry_agent:Added Bing search tools: 1 tools
   ```

2. Test with a query that requires real-time web search:
   - "What are today's top news headlines?"
   - "What is the current weather in Seattle?"

## Troubleshooting

### Error: "Unauthorized. Access token is missing, invalid, audience is incorrect (https://bing.azure.com), or have expired"

**This is the most common error!**

**Root Cause**: Local Authentication is disabled on your AI Foundry AI Services resource.

**Solution**:
1. Check if local auth is disabled:
   ```bash
   az cognitiveservices account show \
     --name <your-ai-foundry-resource-name> \
     --resource-group <your-resource-group> \
     --query "properties.disableLocalAuth" -o tsv
   ```
   
2. If it returns `true`, enable it:
   ```bash
   az cognitiveservices account update \
     --name <your-ai-foundry-resource-name> \
     --resource-group <your-resource-group> \
     --set properties.disableLocalAuth=false
   ```

3. Redeploy or restart your container app after enabling

### Error: "Connection can't be found in this workspace"
- Verify the connection name in AI Foundry is exactly **`binggrnd`**
- Check that the connection was created successfully in the portal

### Error: "Provider 'Microsoft.Bing' is not registered"
- Run: `az provider register --namespace Microsoft.Bing`
- Wait for registration to complete (check with `az provider show --namespace Microsoft.Bing`)

### Error: "Bing tool not enabled"
- Verify `use_bing: true` in agent JSON configuration
- Check environment variables are set (should happen automatically via Bicep)

### Error: "Cannot use Bing with reasoning models"
- Don't set `use_bing: true` for agents using o3 or o4-mini models
- Use regular GPT models (gpt-4, gpt-4.1, etc.) for Bing-enabled agents

## What Was Changed

### Code Files Modified:
1. `src/backend/common/config/app_config.py` - Uncommented Bing configuration
2. `src/backend/v3/magentic_agents/models/agent_models.py` - Uncommented BingConfig class
3. `src/backend/v3/magentic_agents/foundry_agent.py` - Uncommented Bing tool methods
4. `src/backend/v3/magentic_agents/magentic_agent_factory.py` - Uncommented Bing initialization

### Infrastructure Files Modified:
1. `infra/main.bicep` - Added BING_CONNECTION_NAME and AZURE_BING_CONNECTION_NAME
2. `infra/main_custom.bicep` - Added same Bing environment variables

All code is now ready - you just need to create the Azure resource and connection!
