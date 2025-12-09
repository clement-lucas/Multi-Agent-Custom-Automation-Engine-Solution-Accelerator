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

## Step 3: Verify Local Authentication is Enabled

⚠️ **Critical**: Bing Search Grounding only supports API key authentication.

1. In Azure AI Studio, go to your AI Foundry project settings
2. Check that **Local Authentication** is **Enabled**
3. If disabled, you won't be able to use Bing grounding

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

### Error: "Connection can't be found in this workspace"
- Verify the connection name in AI Foundry is exactly **`binggrnd`**
- Check that Local Authentication is enabled in AI Foundry

### Error: "Provider 'Microsoft.Bing' is not registered"
- Run: `az provider register --namespace Microsoft.Bing`
- Wait for registration to complete (check with `az provider show`)

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
