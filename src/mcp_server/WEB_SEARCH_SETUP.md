# Web Search Service Configuration

The MCP server's Web Search Service supports multiple search providers for reliable web search and weather lookups.

## Search Providers

The service tries providers in this order:

1. **Tavily AI** (Primary - Recommended)
   - Optimized for AI agents
   - Provides AI-generated answers
   - Best accuracy and relevance
   - Free tier: 1,000 searches/month

2. **SerpAPI/Google** (Secondary)
   - Uses real Google search results
   - High quality results
   - Free tier: 100 searches/month

3. **DuckDuckGo** (Fallback)
   - No API key required
   - Limited functionality
   - May return no results

## Configuration

### Option 1: Tavily AI (Recommended)

1. Sign up at https://tavily.com/
2. Get your API key from the dashboard
3. Configure the MCP container app:

```bash
az containerapp update \
  --name ca-mcp-odmadevycpyl \
  --resource-group rg-odmadev \
  --set-env-vars "TAVILY_API_KEY=<your-tavily-api-key>"
```

### Option 2: SerpAPI (Google Search)

1. Sign up at https://serpapi.com/
2. Get your API key from the dashboard
3. Configure the MCP container app:

```bash
az containerapp update \
  --name ca-mcp-odmadevycpyl \
  --resource-group rg-odmadev \
  --set-env-vars "SERPAPI_API_KEY=<your-serpapi-api-key>"
```

### Option 3: Both APIs (Best Reliability)

Configure both APIs for maximum reliability - the service will use Tavily first and fall back to SerpAPI if needed:

```bash
az containerapp update \
  --name ca-mcp-odmadevycpyl \
  --resource-group rg-odmadev \
  --set-env-vars \
    "TAVILY_API_KEY=<your-tavily-api-key>" \
    "SERPAPI_API_KEY=<your-serpapi-api-key>"
```

## Verifying Configuration

After setting environment variables, check the MCP server logs to see which provider is being used:

```bash
az containerapp logs show \
  --name ca-mcp-odmadevycpyl \
  --resource-group rg-odmadev \
  --tail 50 --follow false \
  | grep -E "WebSearchService|provider"
```

You should see one of:
- `WebSearchService: Using Tavily as primary provider`
- `WebSearchService: Using SerpAPI as primary provider`
- `WebSearchService: No API keys found, using DuckDuckGo (limited functionality)`

## Testing

### Test Web Search

Ask the agent: "What are the latest AI trends in 2025?"

### Test Weather

Ask the agent: "What is the current weather in Tokyo?"

## Provider Comparison

| Provider | API Key Required | Results Quality | Free Tier | AI-Optimized |
|----------|-----------------|-----------------|-----------|--------------|
| Tavily | Yes | Excellent | 1,000/month | Yes |
| SerpAPI | Yes | Excellent | 100/month | No |
| DuckDuckGo | No | Limited | Unlimited | No |

## Troubleshooting

### No search results returned

1. Check if API key is configured:
   ```bash
   az containerapp show \
     --name ca-mcp-odmadevycpyl \
     --resource-group rg-odmadev \
     --query "properties.template.containers[0].env" \
     -o json | grep -E "TAVILY|SERPAPI"
   ```

2. Check MCP server logs for errors:
   ```bash
   az containerapp logs show \
     --name ca-mcp-odmadevycpyl \
     --resource-group rg-odmadev \
     --tail 200 --follow false \
     | grep -E "ERROR|search|Tavily|SerpAPI"
   ```

3. Verify API key is valid by testing directly:
   - Tavily: https://docs.tavily.com/
   - SerpAPI: https://serpapi.com/search-api

### API rate limits exceeded

If you hit rate limits:
1. Add a secondary provider (e.g., add SerpAPI if using Tavily)
2. Upgrade your API plan
3. The service will automatically fall back to DuckDuckGo

## Cost Optimization

- **Development/Testing**: Use DuckDuckGo (free, limited results)
- **Light Production**: Tavily free tier (1,000 searches/month)
- **Heavy Production**: Configure both Tavily + SerpAPI for redundancy
- **Enterprise**: Upgrade to paid tiers of Tavily or SerpAPI

## Example Responses

### Tavily Response
```json
{
  "query": "current weather in Tokyo",
  "results_count": 3,
  "results": [...],
  "answer": "The current weather in Tokyo is partly cloudy with a temperature of 15°C...",
  "provider": "tavily"
}
```

### SerpAPI Response
```json
{
  "query": "current weather in Tokyo",
  "results_count": 3,
  "results": [...],
  "provider": "serpapi"
}
```

### DuckDuckGo Response
```json
{
  "query": "current weather in Tokyo",
  "results_count": 2,
  "results": [...],
  "provider": "duckduckgo"
}
```
