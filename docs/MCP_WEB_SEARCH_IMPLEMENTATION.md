# MCP Web Search Implementation Guide

## Overview

This document describes the custom MCP web search implementation that provides web search capabilities to agents without requiring Bing API or Azure local authentication.

## Implementation Summary

**Date**: January 2025  
**Reason**: Bing Grounding requires local authentication (API keys) which is blocked by organizational subscription policies.  
**Solution**: Custom web search service using DuckDuckGo via the MCP (Model Context Protocol) server.

## Architecture

### Components

1. **WebSearchService** (`src/mcp_server/services/web_search_service.py`)
   - MCP service providing web search capabilities
   - Uses DuckDuckGo as the search provider (free, no authentication required)
   - Implements two tools: `web_search` and `get_web_page_content`

2. **MCP Server Integration** (`src/mcp_server/mcp_server.py`)
   - WebSearchService registered in the MCP tool factory
   - Available to all agents with `use_mcp: true`

3. **Agent Configuration** (`data/agent_teams/store.json`)
   - BingSearchAgent updated to use MCP instead of Bing
   - `use_mcp: true`, `use_bing: false`

## Available Tools

### 1. web_search

Search the web for information using DuckDuckGo.

**Parameters:**
- `query` (str): Search query
- `max_results` (int, optional): Maximum number of results to return (default: 5, range: 1-10)

**Returns:**
```json
{
  "status": "success",
  "timestamp": "2025-01-XX XX:XX:XX",
  "details": {
    "query": "weather in Seattle",
    "results": [
      {
        "title": "Weather in Seattle - AccuWeather",
        "url": "https://www.accuweather.com/...",
        "snippet": "Current weather conditions...",
        "source": "duckduckgo"
      }
    ],
    "result_count": 5
  },
  "summary": "Found 5 results for 'weather in Seattle'"
}
```

**Example Usage:**
```python
# Agent will automatically call this tool when it needs web search
response = await web_search(
    query="latest AI trends 2025",
    max_results=5
)
```

### 2. get_web_page_content

Fetch and extract text content from a web page.

**Parameters:**
- `url` (str): URL to fetch
- `max_length` (int, optional): Maximum content length (default: 5000)

**Returns:**
```json
{
  "status": "success",
  "timestamp": "2025-01-XX XX:XX:XX",
  "details": {
    "url": "https://example.com/article",
    "title": "Article Title",
    "content": "Extracted text content...",
    "content_length": 3500,
    "full_length": 3500,
    "truncated": false
  },
  "summary": "Retrieved content from https://example.com/article (3500 chars)"
}
```

**Example Usage:**
```python
# Follow up on search results by getting full page content
response = await get_web_page_content(
    url="https://example.com/article",
    max_length=5000
)
```

## Search Provider: DuckDuckGo

### Why DuckDuckGo?

- **Free**: No API keys or authentication required
- **No Rate Limits**: On Instant Answer API
- **Privacy-Focused**: No tracking or data collection
- **Reliable**: Well-established search engine

### Implementation Details

The service uses two DuckDuckGo endpoints:

1. **Instant Answer API** (Primary)
   - Endpoint: `https://api.duckduckgo.com/?q={query}&format=json`
   - Returns structured JSON with direct answers and related topics
   - Best for factual queries, definitions, quick facts

2. **HTML Search** (Fallback)
   - Endpoint: `https://html.duckduckgo.com/html/`
   - Scrapes search results when Instant Answer doesn't return results
   - Uses regex parsing (basic, works for most cases)

### Limitations Compared to Bing

- **Less Comprehensive**: Smaller index than Bing
- **No Citations**: Unlike Bing Grounding, no source metadata
- **Basic Parsing**: HTML scraping is fragile to page changes
- **No Advanced Features**: No image search, news filtering, etc.

### Advantages Over Bing

- **No Authentication**: Works without API keys
- **No Subscription Dependencies**: No Azure resource requirements
- **No Policy Conflicts**: Doesn't require local auth enablement
- **Extensible**: Can add more providers easily

## Agent Configuration

### BingSearchAgent Configuration

Located in `data/agent_teams/store.json`:

```json
{
  "name": "BingSearchAgent",
  "deployment_name": "gpt-4.1-mini",
  "system_message": "You have access to internet via MCP web search tools to check for latest information related with the question from user. Use web_search tool to search for information and get_web_page_content tool to retrieve detailed content from specific URLs. You can check weather forecast information from relevant websites. Pass the information you retrieve to DataAnalysisAgent for analysis and planning, you do not reason and do not perform analysis on the data. Pass the data you retrieve to VisualizationAgent to create data visualization such as graph. You do not create graphs.",
  "description": "An agent that has access to internet via MCP web search tools to check for latest information such as weather forecast, ask this agent if you have questions such us best day to do promotion, latest trend, etc.",
  "use_rag": false,
  "use_mcp": true,
  "use_bing": false,
  "use_reasoning": false,
  "coding_tools": false
}
```

**Key Changes:**
- `use_mcp`: `false` → `true` (Enable MCP tools)
- `use_bing`: `true` → `false` (Disable Bing)
- `system_message`: Updated to mention MCP web search tools
- `description`: Updated to mention MCP web search tools

## Deployment

### Prerequisites

- MCP server must be deployed with WebSearchService
- Backend must be deployed with Bing code reverted
- Agent configuration updated (already done)

### Deployment Steps

#### 1. Build and Deploy MCP Server

```bash
# Navigate to MCP server directory
cd src/mcp_server

# Build Docker image
docker build -t <your-registry>/macaemcp:latest .

# Push to container registry
docker push <your-registry>/macaemcp:latest

# Update container app (replace with your values)
az containerapp update \
  --name <mcp-container-app-name> \
  --resource-group <resource-group> \
  --image <your-registry>/macaemcp:latest
```

#### 2. Build and Deploy Backend

```bash
# Navigate to backend directory
cd src/backend

# Build Docker image
docker build -t <your-registry>/macaebackend:latest .

# Push to container registry
docker push <your-registry>/macaebackend:latest

# Update container app (replace with your values)
az containerapp update \
  --name <backend-container-app-name> \
  --resource-group <resource-group> \
  --image <your-registry>/macaebackend:latest
```

#### 3. Verify Deployment

```bash
# Check MCP server logs for WebSearchService registration
az containerapp logs show \
  --name <mcp-container-app-name> \
  --resource-group <resource-group> \
  --follow

# Look for: "Registered service: WebSearchService"
```

## Testing

### Test MCP Server Locally

```bash
# Start MCP server
cd src/mcp_server
python mcp_server.py

# In another terminal, test web_search tool
curl -X POST http://localhost:8000/tools/web_search \
  -H "Content-Type: application/json" \
  -d '{"query": "weather in Seattle", "max_results": 3}'

# Test get_web_page_content tool
curl -X POST http://localhost:8000/tools/get_web_page_content \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_length": 1000}'
```

### Test BingSearchAgent End-to-End

After deployment, test the agent with web search queries:

**Test Query 1: Weather Forecast**
```
"What's the weather forecast for Seattle this week?"
```
Expected: Agent uses web_search, retrieves weather info, delegates to DataAnalysisAgent

**Test Query 2: Latest Trends**
```
"Find the latest trends in retail for 2025"
```
Expected: Agent uses web_search, may call get_web_page_content for details

**Test Query 3: Promotion Planning**
```
"What's the best day this week to run a promotion based on weather and trends?"
```
Expected: Agent uses web_search for weather, delegates to DataAnalysisAgent for planning

## Code Changes Summary

### Files Modified

1. **src/mcp_server/services/web_search_service.py** (NEW - 279 lines)
   - Created WebSearchService with DuckDuckGo integration
   - Implemented web_search and get_web_page_content tools

2. **src/mcp_server/mcp_server.py** (MODIFIED)
   - Added WebSearchService import
   - Registered WebSearchService in factory

3. **data/agent_teams/store.json** (MODIFIED)
   - Updated BingSearchAgent configuration
   - Changed use_mcp to true, use_bing to false
   - Updated system_message and description

### Files Previously Reverted (Bing Cleanup)

These files had Bing code commented out:
- `src/backend/common/config/app_config.py`
- `src/backend/v3/magentic_agents/models/agent_models.py`
- `src/backend/v3/magentic_agents/foundry_agent.py`
- `src/backend/v3/magentic_agents/magentic_agent_factory.py`
- `infra/main.bicep`
- `infra/main_custom.bicep`

Deleted:
- `BING_SETUP_STEPS.md`

## Future Enhancements

### Potential Improvements

1. **Better HTML Parsing**
   - Add BeautifulSoup for robust HTML parsing
   - Improve content extraction quality

2. **Multiple Search Providers**
   - Add Brave Search API
   - Add Searx instances
   - Implement provider fallback

3. **Caching**
   - Cache search results to reduce API calls
   - TTL-based cache expiration

4. **Enhanced Features**
   - Image search capability
   - News filtering
   - Date range filtering
   - Language selection

5. **Rate Limiting**
   - Implement per-user rate limits
   - Prevent abuse

## Troubleshooting

### Common Issues

**Issue: No search results returned**
- Check: DuckDuckGo API may not have instant answer for query
- Solution: Service automatically falls back to HTML scraping
- Verify: Check MCP server logs for error messages

**Issue: get_web_page_content returns empty content**
- Check: Target website may block scraping
- Check: Website may require JavaScript (not supported)
- Solution: Try different URL or use web_search instead

**Issue: Agent not using MCP tools**
- Check: Agent configuration has `use_mcp: true`
- Check: MCP server is deployed and accessible
- Check: MCP_ENDPOINT environment variable set correctly
- Verify: Backend logs show MCP connection success

**Issue: Search results irrelevant**
- Limitation: DuckDuckGo may have lower relevance than Bing
- Solution: Refine search query, be more specific
- Alternative: Consider switching to different search provider

## Support

For issues or questions:
1. Check MCP server logs: `az containerapp logs show --name <mcp-app>`
2. Check backend logs: `az containerapp logs show --name <backend-app>`
3. Review this documentation
4. Contact development team

## References

- DuckDuckGo Instant Answer API: https://duckduckgo.com/api
- FastMCP Documentation: https://github.com/jlowin/fastmcp
- MCP Protocol: https://modelcontextprotocol.io/

---

**Last Updated**: January 2025  
**Version**: 1.0
