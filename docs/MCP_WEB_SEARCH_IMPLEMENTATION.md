# MCP Web Search Implementation Guide

## Overview

This document describes the custom MCP web search implementation that provides web search capabilities to agents without requiring Bing API or Azure local authentication.

## Implementation Summary

**Date**: December 2025  
**Reason**: Bing Grounding requires local authentication (API keys) which is blocked by organizational subscription policies.  
**Solution**: Multi-provider web search service using Tavily AI (primary), SerpAPI (secondary), and DuckDuckGo (fallback) via the MCP (Model Context Protocol) server.

## Architecture

### Components

1. **WebSearchService** (`src/mcp_server/services/web_search_service.py` - 456 lines)
   - MCP service providing web search capabilities with intelligent fallback
   - Supports three search providers:
     - **Tavily AI** (primary): AI-optimized search with generated answers (requires API key)
     - **SerpAPI** (secondary): Real Google search results (requires API key)
     - **DuckDuckGo** (fallback): Free search, no authentication required
   - Implements two tools: `search_web` and `get_weather`
   - Auto-detects available providers based on environment variables

2. **MCP Server Integration** (`src/mcp_server/mcp_server.py`)
   - WebSearchService registered in the MCP tool factory
   - Available to all agents with `use_mcp: true`
   - Provides 2 tools across all 5 registered services

3. **Agent Configuration** (`data/agent_teams/store.json`)
   - WebSearchAgent (formerly BingSearchAgent) updated to use MCP tools
   - `use_mcp: true`, `use_bing: false`

4. **Configuration Guide** (`src/mcp_server/WEB_SEARCH_SETUP.md`)
   - Comprehensive setup instructions for API key configuration
   - Provider comparison and testing procedures

## Available Tools

### 1. search_web

Search the web for information using the best available search provider (Tavily, SerpAPI, or DuckDuckGo).

**Parameters:**
- `query` (str): Search query (e.g., "latest technology trends 2025")
- `max_results` (int, optional): Maximum number of results to return (default: 5, range: 1-10)

**Returns:**
```json
{
  "query": "latest AI trends 2025",
  "timestamp": "2025-12-17T04:08:45Z",
  "results_count": 5,
  "results": [
    {
      "title": "Top AI Trends for 2025",
      "url": "https://example.com/ai-trends",
      "snippet": "The latest developments in AI include...",
      "source": "example.com"
    }
  ],
  "provider": "tavily",
  "answer": "AI in 2025 is characterized by advancements in..."
}
```

**Provider-Specific Features:**
- **Tavily**: Includes `answer` field with AI-generated summary, relevance scores
- **SerpAPI**: Includes position metadata, real Google results
- **DuckDuckGo**: Basic results, may return empty array

**Example Usage:**
```python
# Agent will automatically call this tool when it needs web search
response = await search_web(
    query="latest AI trends 2025",
    max_results=5
)
```

### 2. get_weather

Get current weather information for a location using web search.

**Parameters:**
- `location` (str): City name or location (e.g., "Tokyo", "Seattle")

**Returns:**
```json
{
  "query": "weather Tokyo",
  "timestamp": "2025-12-17T04:10:22Z",
  "results_count": 3,
  "results": [
    {
      "title": "Tokyo Weather - AccuWeather",
      "url": "https://www.accuweather.com/...",
      "snippet": "Current weather in Tokyo: 15°C, partly cloudy...",
      "source": "accuweather.com"
    }
  ],
  "provider": "tavily"
}
```

**Example Usage:**
```python
# Get weather information for planning
response = await get_weather(
    location="Seattle"
)
```

## Multi-Provider Search Architecture

### Provider Selection Logic

The service automatically selects the best available provider:

```python
if TAVILY_API_KEY exists:
    use Tavily (primary)
elif SERPAPI_API_KEY exists:
    use SerpAPI (secondary)
else:
    use DuckDuckGo (fallback)
```

On errors, the service gracefully falls back to the next available provider.

### 1. Tavily AI (Primary - Recommended)

**Why Tavily?**
- **AI-Optimized**: Specifically designed for AI agents
- **Rich Responses**: Includes AI-generated answers and summaries
- **High Quality**: Better relevance and accuracy than generic search
- **Generous Free Tier**: 1,000 searches/month

**Implementation:**
- Endpoint: `https://api.tavily.com/search`
- Method: POST with JSON payload
- Returns: Structured results with AI answers, relevance scores
- Best for: General queries, research, complex questions

### 2. SerpAPI/Google (Secondary)

**Why SerpAPI?**
- **Real Google Results**: Uses actual Google search
- **High Quality**: Google's search quality and coverage
- **Metadata Rich**: Includes position, source metadata
- **Free Tier**: 100 searches/month

**Implementation:**
- Endpoint: `https://serpapi.com/search`
- Method: GET with query parameters
- Returns: Organic search results from Google
- Best for: When Tavily unavailable, backup provider

### 3. DuckDuckGo (Fallback)

**Why DuckDuckGo?**
- **Free**: No API keys or authentication required
- **No Rate Limits**: Unlimited usage
- **Privacy-Focused**: No tracking
- **Always Available**: Works when paid providers fail

**Implementation:**
- Dual approach: Instant Answer API + HTML scraping
- Instant Answer: `https://api.duckduckgo.com/?q={query}&format=json`
- HTML scraping: `https://html.duckduckgo.com/html/` (when API returns empty)
- Returns: Basic results, may be limited
- Best for: Development, when API keys not configured

**Limitations:**
- Less comprehensive than Tavily/SerpAPI
- May return no results for some queries
- HTML scraping is fragile

### Provider Comparison

| Feature | Tavily | SerpAPI | DuckDuckGo |
|---------|--------|---------|------------|
| API Key Required | ✓ | ✓ | ✗ |
| Free Tier | 1,000/month | 100/month | Unlimited |
| AI-Optimized | ✓ | ✗ | ✗ |
| Answer Generation | ✓ | ✗ | ✗ |
| Result Quality | Excellent | Excellent | Limited |
| Reliability | High | High | Moderate |
| **Recommended For** | **Production** | **Backup** | **Development** |

### Advantages Over Bing

- **No Azure Dependencies**: Works without Azure resources
- **No Subscription Policies**: Bypasses local auth restrictions
- **Multiple Providers**: Built-in redundancy and failover
- **Better for AI**: Tavily specifically optimized for AI agents
- **Flexible**: Easy to add more providers

## Agent Configuration

### WebSearchAgent Configuration

Located in `data/agent_teams/store.json`:

```json
{
  "name": "WebSearchAgent",
  "deployment_name": "gpt-4.1-mini",
  "system_message": "Use search_web tool to search for information on the internet. Use get_weather tool to get weather information for a location. You can check weather forecast information from relevant websites. Pass the information you retrieve to DataAnalysisAgent for analysis and planning.",
  "description": "An agent with internet access via MCP tools to check latest information such as weather forecast, trends, and current events.",
  "use_rag": false,
  "use_mcp": true,
  "use_bing": false,
  "use_reasoning": false,
  "coding_tools": false
}
```

**Key Configuration:**
- `use_mcp`: `true` (Enable MCP tools including search_web and get_weather)
- `use_bing`: `false` (Bing disabled)
- **Available Tools**: `search_web`, `get_weather`
- **Search Providers**: Tavily (primary), SerpAPI (secondary), DuckDuckGo (fallback)

**Migration from Bing:**
- Old approach: Bing Grounding with API keys (blocked by policy)
- New approach: Multi-provider MCP tools (Tavily recommended, DuckDuckGo works without config)

## Deployment

### Prerequisites

- MCP server must be deployed with WebSearchService
- Backend deployed (no Bing dependencies)
- Agent configuration updated to use MCP tools
- **Optional**: API keys for Tavily and/or SerpAPI (recommended for production)

### Deployment Methods

#### Option 1: Automated Deployment (Recommended)

Use the deployment script:

```bash
# Deploy all services (frontend, backend, MCP)
cd /workspaces/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator
./deploy_with_acr.sh
```

The script will:
1. Build all container images in Azure Container Registry
2. Tag with timestamp and git commit
3. Update container apps with new images
4. Restart services

#### Option 2: Manual MCP Server Deployment

```bash
# Navigate to MCP server directory
cd src/mcp_server

# Build in Azure Container Registry
az acr build \
  --registry <your-registry> \
  --image macae-mcp:latest \
  --file Dockerfile .

# Update container app
az containerapp update \
  --name ca-mcp-<suffix> \
  --resource-group <resource-group> \
  --image <your-registry>.azurecr.io/macae-mcp:latest
```

### Configuration

#### Step 1: Verify Deployment

```bash
# Check MCP server startup
az containerapp logs show \
  --name ca-mcp-<suffix> \
  --resource-group <resource-group> \
  --tail 50 | grep -E "Total services|WebSearchService"

# Expected output:
# INFO:__main__:📊 Total services: 5
# INFO:__main__:🔧 Total tools: 17
# INFO:__main__:   📁 general: 2 tools (WebSearchService)
# WARNING:...WebSearchService: No API keys found, using DuckDuckGo (limited functionality)
```

#### Step 2: Configure API Keys (Recommended)

**For Tavily (Recommended):**

```bash
# Sign up at https://tavily.com/ and get API key
az containerapp update \
  --name ca-mcp-<suffix> \
  --resource-group <resource-group> \
  --set-env-vars "TAVILY_API_KEY=tvly-YOUR_KEY_HERE"
```

**For SerpAPI (Optional Backup):**

```bash
# Sign up at https://serpapi.com/ and get API key
az containerapp update \
  --name ca-mcp-<suffix> \
  --resource-group <resource-group> \
  --set-env-vars "SERPAPI_API_KEY=YOUR_SERPAPI_KEY"
```

**For Both (Maximum Reliability):**

```bash
az containerapp update \
  --name ca-mcp-<suffix> \
  --resource-group <resource-group> \
  --set-env-vars \
    "TAVILY_API_KEY=tvly-YOUR_KEY" \
    "SERPAPI_API_KEY=YOUR_SERPAPI_KEY"
```

#### Step 3: Verify Provider Selection

```bash
# Wait for restart
sleep 30

# Check which provider is active
az containerapp logs show \
  --name ca-mcp-<suffix> \
  --resource-group <resource-group> \
  --tail 20 | grep WebSearchService

# Expected with Tavily:
# INFO:...WebSearchService: Using Tavily as primary provider

# Expected with SerpAPI:
# INFO:...WebSearchService: Using SerpAPI as primary provider

# Expected without keys:
# WARNING:...WebSearchService: No API keys found, using DuckDuckGo (limited functionality)
```

## Testing

### Test Provider Selection

```bash
# Check which provider is active
az containerapp logs show \
  --name ca-mcp-<suffix> \
  --resource-group <resource-group> \
  --tail 50 | grep -E "WebSearchService|provider"
```

### Test WebSearchAgent End-to-End

After deployment, test the agent with various queries:

**Test 1: General Search (Tavily excels here)**
```
"What are the latest AI trends in 2025?"
```
**Expected Behavior:**
- Agent calls `search_web` tool
- With Tavily: Gets AI-generated answer + 5 quality results
- With SerpAPI: Gets Google organic results
- With DuckDuckGo: Gets basic results (may be limited)
- Agent provides comprehensive response to user

**Test 2: Weather Query**
```
"What is the current weather in Tokyo?"
```
**Expected Behavior:**
- Agent calls `get_weather` tool
- Service searches for "weather Tokyo"
- Returns weather information from search results
- Agent extracts temperature and conditions

**Test 3: Complex Research**
```
"Find the latest trends in retail for 2025"
```
**Expected Behavior:**
- Agent calls `search_web` with query about retail trends
- With Tavily: Receives AI answer summarizing trends
- Agent synthesizes information from multiple results

**Test 4: Promotion Planning (Multi-Agent)**
```
"What's the best day this week to run a promotion based on weather?"
```
**Expected Behavior:**
- WebSearchAgent calls `get_weather` or `search_web`
- Retrieves weather forecast data
- Passes to DataAnalysisAgent for planning
- Returns recommendation

### Monitor Tool Calls

```bash
# Watch backend for MCP tool usage
az containerapp logs show \
  --name ca-<backend-suffix> \
  --resource-group <resource-group> \
  --follow | grep -E "search_web|get_weather|MacaeMcpServer"

# Watch MCP server for provider activity
az containerapp logs show \
  --name ca-mcp-<suffix> \
  --resource-group <resource-group> \
  --follow | grep -E "search|weather|Tavily|SerpAPI|DuckDuckGo"
```

## Code Changes Summary

### Files Modified

1. **src/mcp_server/services/web_search_service.py** (COMPLETELY REWRITTEN - 456 lines)
   - Multi-provider architecture with Tavily, SerpAPI, DuckDuckGo
   - Provider auto-detection based on environment variables
   - Intelligent fallback: Tavily → SerpAPI → DuckDuckGo
   - Implemented tools: `search_web` and `get_weather`
   - Consistent response format across all providers
   - Comprehensive error handling and logging

2. **src/mcp_server/WEB_SEARCH_SETUP.md** (NEW - 173 lines)
   - Complete API key configuration guide
   - Provider comparison table
   - Testing procedures and examples
   - Troubleshooting guide
   - Cost optimization recommendations

3. **src/mcp_server/mcp_server.py** (MODIFIED)
   - Added WebSearchService import
   - Registered WebSearchService in factory
   - Now provides 17 total tools across 5 services

4. **data/agent_teams/store.json** (MODIFIED)
   - Updated agent configuration (now WebSearchAgent)
   - Changed `use_mcp` to `true`, `use_bing` to `false`
   - Updated system_message to reference `search_web` and `get_weather`
   - Updated description to mention MCP tools

5. **deploy_with_acr.sh** (USED FOR DEPLOYMENT)
   - Automated deployment script for all services
   - Builds frontend, backend, and MCP images
   - Tags with timestamp and git commit
   - Updates container apps automatically

### Current Deployment

**Latest Images:**
- Backend: `acrmacae7359.azurecr.io/macae-backend:20251212-035419-79ed0aca`
- MCP: `acrmacae7359.azurecr.io/macae-mcp:20251212-040650-79ed0aca`
- Frontend: `acrmacae7359.azurecr.io/macae-frontend:20251212-035419-79ed0aca`

**Container Apps:**
- MCP: Revision ca-mcp-odmadevycpyl--0000013 (Running)
- Backend: Revision ca-odmadevycpyl--0000033 (Running)
- Status: ✅ All services operational

**Active Provider:** DuckDuckGo (fallback - no API keys configured)

### Files Previously Reverted (Bing Cleanup)

These files had Bing code removed:
- `src/backend/common/config/app_config.py`
- `src/backend/v3/magentic_agents/models/agent_models.py`
- `src/backend/v3/magentic_agents/foundry_agent.py`
- `src/backend/v3/magentic_agents/magentic_agent_factory.py`
- `infra/main.bicep`
- `infra/main_custom.bicep`

Deleted:
- `BING_SETUP_STEPS.md`

Archived:
- `src/mcp_server/services/web_search_service_old.py` (backup of corrupted version)

## Future Enhancements

### Completed ✅

1. **Multiple Search Providers** ✅
   - Tavily AI integration (AI-optimized)
   - SerpAPI integration (Google search)
   - Intelligent provider fallback
   - Auto-detection based on API keys

### Potential Improvements

1. **Additional Providers**
   - Brave Search API
   - Searx/SearxNG instances
   - Bing Web Search API (if policies change)
   - Custom provider plugins

2. **Caching Layer**
   - Redis cache for search results
   - TTL-based cache expiration
   - Reduce API costs and improve latency
   - Cache invalidation strategies

3. **Enhanced Features**
   - Image search capability (Tavily supports this)
   - News filtering and recency
   - Date range filtering
   - Language selection
   - Location-based results

4. **Rate Limiting & Monitoring**
   - Per-user/per-agent rate limits
   - API usage tracking and alerting
   - Cost monitoring dashboard
   - Automatic provider switching on quota exhaustion

5. **Quality Improvements**
   - Result deduplication across providers
   - Relevance scoring and ranking
   - Source credibility scoring
   - Fact-checking integration

## Troubleshooting

### Common Issues

**Issue: No search results returned**

**Current Provider: DuckDuckGo (no API keys)**
- Root Cause: DuckDuckGo frequently returns empty results
- **Solution**: Configure Tavily or SerpAPI API key (see WEB_SEARCH_SETUP.md)
- Temporary: Service falls back to HTML scraping automatically
- Verify: Check MCP logs for provider warnings

**Current Provider: Tavily/SerpAPI**
- Check: API key validity and quota remaining
- Check: Network connectivity from container to API endpoint
- Verify: MCP logs for API error messages
- Solution: Service automatically falls back to next provider

**Issue: Agent not using MCP tools**
- Check: Agent configuration has `use_mcp: true` in agent_teams/store.json
- Check: MCP server is running (check container app status)
- Check: Backend can reach MCP endpoint (check env vars)
- Verify: Backend logs show "MCP client initialized" or similar
- Test: Check MCP logs for "Total tools: 17" on startup

**Issue: Search quality is poor**

**With DuckDuckGo:**
- Expected: DuckDuckGo has limited results
- **Solution**: Configure Tavily API key for better results
- Impact: Tavily provides AI-generated answers and better relevance

**With Tavily/SerpAPI:**
- Rare: These providers have high quality
- Check: Query phrasing and specificity
- Check: Results may be recent (providers prioritize freshness)

**Issue: API quota exhausted**

**Tavily (1,000/month free):**
- Monitor: Check https://tavily.com/dashboard
- Solution: Upgrade plan or configure SerpAPI as backup
- Fallback: Service automatically uses SerpAPI or DuckDuckGo

**SerpAPI (100/month free):**
- Monitor: Check https://serpapi.com/dashboard
- Solution: Upgrade plan or rely on Tavily primarily
- Fallback: Service uses DuckDuckGo when both exhausted

**Issue: Provider not detected**
- Check: Environment variable name exactly matches:
  - `TAVILY_API_KEY` (not TAVILY_KEY)
  - `SERPAPI_API_KEY` (not SERP_API_KEY)
- Verify: Container app environment variables configured
- Test: Restart container app after setting variables
- Debug: Check MCP logs for "Using X as primary provider"

**Issue: Weather tool not working**
- Behavior: `get_weather` uses web search internally
- Check: Same troubleshooting as search_web tool
- With Tavily: Should return weather info in AI answer
- With DuckDuckGo: May return limited weather data

## Support

For issues or questions:
1. **Check Setup Guide**: See `src/mcp_server/WEB_SEARCH_SETUP.md` for API key configuration
2. **Check MCP Logs**: `az containerapp logs show --name ca-mcp-<suffix> --resource-group <rg>`
3. **Check Backend Logs**: `az containerapp logs show --name ca-<suffix> --resource-group <rg>`
4. **Verify Provider**: Look for "Using X as primary provider" in MCP logs
5. **Test API Keys**: Ensure keys are valid and have remaining quota
6. Review this documentation
7. Contact development team

## References

### Search Providers
- **Tavily AI**: https://tavily.com/ (Sign up, get API key, 1k/month free)
- **SerpAPI**: https://serpapi.com/ (Sign up, get API key, 100/month free)
- **DuckDuckGo API**: https://duckduckgo.com/api (No key needed)

### Documentation
- **Configuration Guide**: `src/mcp_server/WEB_SEARCH_SETUP.md` (detailed setup)
- **FastMCP**: https://github.com/jlowin/fastmcp (MCP framework)
- **MCP Protocol**: https://modelcontextprotocol.io/ (specification)

### Azure Resources
- **Container Apps**: https://learn.microsoft.com/azure/container-apps/
- **Container Registry**: https://learn.microsoft.com/azure/container-registry/

---

**Last Updated**: December 2025  
**Version**: 2.0 (Multi-Provider)  
**Current Deployment**: 
- MCP Image: `acrmacae7359.azurecr.io/macae-mcp:20251212-040650-79ed0aca`
- Active Provider: DuckDuckGo (fallback)
- **Recommended**: Configure Tavily API key for production use
