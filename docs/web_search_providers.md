# Web Search Providers for MCP Server

The WebSearchService supports multiple search providers with automatic fallback:

## Supported Providers (in priority order)

### 1. Tavily AI (Recommended) ⭐
- **Best for**: AI agents and LLM applications
- **Pros**: 
  - Designed specifically for AI/LLM use cases
  - Returns AI-generated answers + sources
  - High quality, relevant results
  - Generous free tier (1,000 searches/month)
- **Cons**: Requires API key
- **Get API Key**: https://tavily.com/
- **Cost**: Free tier available, then $0.001 per search

#### Setup:
```bash
# Add to Azure Container App environment variables
az containerapp update \
  --name ca-mcp-odmadevycpyl \
  --resource-group rg-odmadev \
  --set-env-vars "TAVILY_API_KEY=your-key-here"
```

### 2. SerpAPI (Google Results)
- **Best for**: Getting Google search results
- **Pros**:
  - Real Google search results
  - High quality, fresh data
  - Good for local/location-based searches
- **Cons**: Requires API key, limited free tier
- **Get API Key**: https://serpapi.com/
- **Cost**: 100 free searches/month, then paid plans

#### Setup:
```bash
# Add to Azure Container App environment variables
az containerapp update \
  --name ca-mcp-odmadevycpyl \
  --resource-group rg-odmadev \
  --set-env-vars "SERPAPI_KEY=your-key-here"
```

### 3. DuckDuckGo (Fallback)
- **Best for**: Fallback when no API keys are configured
- **Pros**: 
  - No API key required
  - Free, unlimited
  - Privacy-focused
- **Cons**: 
  - Very unreliable (often returns no results)
  - Limited to instant answers (not comprehensive search)
  - No control over freshness
- **No setup required** - automatically used as fallback

## Recommended Configuration

For production use, configure **Tavily AI** for best results:

```bash
# 1. Sign up at https://tavily.com/
# 2. Get your API key from the dashboard
# 3. Add to your container app

az containerapp update \
  --name ca-mcp-odmadevycpyl \
  --resource-group rg-odmadev \
  --set-env-vars "TAVILY_API_KEY=tvly-YOUR-API-KEY-HERE"
```

## Testing

After configuring, test the search functionality:

1. Ask the agent: "What is the current weather in Tokyo?"
2. Check MCP logs to see which provider was used:
   ```bash
   az containerapp logs show \
     --name ca-mcp-odmadevycpyl \
     --resource-group rg-odmadev \
     --tail 50 | grep -i "using.*for search"
   ```

Expected output:
- With Tavily: `Using Tavily AI for search`
- With SerpAPI: `Using SerpAPI for search`
- No API keys: `Using DuckDuckGo for search (no API keys configured)`

## Cost Comparison

| Provider | Free Tier | Cost After Free Tier |
|----------|-----------|---------------------|
| Tavily AI | 1,000 searches/month | $0.001 per search |
| SerpAPI | 100 searches/month | Starting at $50/month |
| DuckDuckGo | Unlimited | Free |

## Troubleshooting

### No results returned
1. Check which provider is being used in logs
2. If using DuckDuckGo (no API keys), consider adding Tavily API key
3. Verify API key is correctly set in container app environment variables

### API key not working
```bash
# Verify environment variable is set
az containerapp show \
  --name ca-mcp-odmadevycpyl \
  --resource-group rg-odmadev \
  --query "properties.template.containers[0].env" \
  -o table
```

### Rate limits exceeded
- Tavily: Upgrade plan or wait for monthly reset
- SerpAPI: Upgrade plan or add backup provider
- The service automatically falls back to next provider on error
