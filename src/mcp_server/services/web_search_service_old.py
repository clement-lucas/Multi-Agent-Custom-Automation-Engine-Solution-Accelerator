"""Web Search Service for MCP Server.

Provides web search capabilities using multiple providers:
1. Tavily AI (recommended - designed for AI agents, requires API key)
2. SerpAPI (Google search results, requires API key)
3. DuckDuckGo (fallback - no API key required, but unreliable)

Set environment variables:
- TAVILY_API_KEY for Tavily search
- SERPAPI_KEY for SerpAPI search
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

import httpx

from core.factory import Domain, MCPToolBase

logger = logging.getLogger(__name__)

# API Keys from environment
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")


class WebSearchService(MCPToolBase):
    """Web search service using DuckDuckGo."""

    def __init__(self):
        super().__init__(Domain.GENERAL)

    @property
    def tool_count(self) -> int:
        """Return the number of tools provided by this service."""
        return 2  # search_web and get_weather

    def register_tools(self, mcp) -> None:
        """Register web search tools with the MCP server."""

        @mcp.tool(tags={self.domain.value})
        async def search_web(query: str, max_results: int = 5) -> dict[str, Any]:
            """Search the web for information.

            Args:
                query: The search query (e.g., "latest technology trends 2025")
                max_results: Maximum number of results to return (1-10, default: 5)

            Returns:
                Search results with titles, URLs, and snippets
            """
            logger.info(f"Web search requested: '{query}' (max_results={max_results})")
            return await self._search_web(query, max_results)

        @mcp.tool(tags={self.domain.value})
        async def get_weather(location: str) -> dict[str, Any]:
            """Get current weather information for a location.

            Args:
                location: City name or location (e.g., "Tokyo", "Seattle")

            Returns:
                Weather information for the specified location
            """
            logger.info(f"Weather info requested for: {location}")
            return await self._get_weather_info(location)

    async def _search_web(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """Search the web using available providers in priority order.

        Priority:
        1. Tavily AI (if API key available)
        2. SerpAPI (if API key available)
        3. DuckDuckGo (fallback, no API key needed)

        Args:
            query: The search query
            max_results: Maximum number of results to return (default: 5, max: 10)

        Returns:
            Dictionary containing search results with titles, URLs, and snippets
        """
        try:
            max_results = min(max(1, max_results), 10)  # Clamp between 1 and 10

            # Try Tavily first (best for AI agents)
            if TAVILY_API_KEY:
                logger.info(f"Using Tavily AI for search: '{query}'")
                return await self._search_tavily(query, max_results)
            
            # Try SerpAPI next (Google results)
            if SERPAPI_KEY:
                logger.info(f"Using SerpAPI for search: '{query}'")
                return await self._search_serpapi(query, max_results)
            
            # Fallback to DuckDuckGo
            logger.info(f"Using DuckDuckGo for search: '{query}' (no API keys configured)")
            return await self._search_duckduckgo(query, max_results)

        except Exception as e:
            logger.error(f"Error during web search: {e}", exc_info=True)
            return {
                "query": query,
                "timestamp": datetime.utcnow().isoformat(),
                "results_count": 0,
                "results": [],
                "error": f"Search failed: {str(e)}",
            }

    async def _search_tavily(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """Search using Tavily AI API.

        Args:
            query: The search query
            max_results: Maximum number of results

        Returns:
            Dictionary containing search results
        """
        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": True,
                "include_raw_content": False,
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("results", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "source": "Tavily AI",
                    "score": item.get("score", 0),
                })

            return {
                "query": query,
                "timestamp": datetime.utcnow().isoformat(),
                "results_count": len(results),
                "results": results,
                "answer": data.get("answer", ""),  # Tavily's AI-generated answer
                "message": f"Found {len(results)} results via Tavily AI",
                "provider": "tavily",
            }

        except httpx.HTTPError as e:
            logger.error(f"Tavily API error: {e}")
            raise

    async def _search_serpapi(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """Search using SerpAPI (Google results).

        Args:
            query: The search query
            max_results: Maximum number of results

        Returns:
            Dictionary containing search results
        """
        try:
            url = "https://serpapi.com/search"
            params = {
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": max_results,
                "engine": "google",
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("organic_results", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": "Google (SerpAPI)",
                    "position": item.get("position", 0),
                })

            return {
                "query": query,
                "timestamp": datetime.utcnow().isoformat(),
                "results_count": len(results),
                "results": results,
                "message": f"Found {len(results)} results via Google (SerpAPI)",
                "provider": "serpapi",
            }

        except httpx.HTTPError as e:
            logger.error(f"SerpAPI error: {e}")
            raise

    async def _search_duckduckgo(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """Search using DuckDuckGo (fallback, no API key needed).

        Args:
            query: The search query
            max_results: Maximum number of results to return (default: 5, max: 10)

        Returns:
            Dictionary containing search results with titles, URLs, and snippets
        """
        try:
    async def _search_duckduckgo(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """Search using DuckDuckGo (fallback, no API key needed).

        Args:
            query: The search query
            max_results: Maximum number of results to return (default: 5, max: 10)

        Returns:
            Dictionary containing search results with titles, URLs, and snippets
        """
        try:
            # DuckDuckGo Instant Answer API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []

            # Get instant answer if available
            if data.get("Abstract"):
                results.append(
                    {
                        "title": data.get("Heading", ""),
                        "url": data.get("AbstractURL", ""),
                        "snippet": data.get("Abstract", ""),
                        "source": "DuckDuckGo Instant Answer",
                    }
                )

            # Get related topics
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append(
                        {
                            "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else topic.get("Text", "")[:100],
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", ""),
                            "source": "DuckDuckGo",
                        }
                    )
                elif isinstance(topic, dict) and "Topics" in topic:
                    # Handle nested topics
                    for subtopic in topic.get("Topics", [])[:max_results]:
                        if len(results) >= max_results:
                            break
                        results.append(
                            {
                                "title": subtopic.get("Text", "").split(" - ")[0] if " - " in subtopic.get("Text", "") else subtopic.get("Text", "")[:100],
                                "url": subtopic.get("FirstURL", ""),
                                "snippet": subtopic.get("Text", ""),
                                "source": "DuckDuckGo",
                            }
                        )

                if len(results) >= max_results:
                    break

            # If no results from instant answer API, try HTML scraping approach
            if not results:
                logger.info(f"No instant answer results for '{query}', trying HTML scraping")
                results = await self._search_web_html(query, max_results)

            return {
                "query": query,
                "timestamp": datetime.utcnow().isoformat(),
                "results_count": len(results),
                "results": results[:max_results],
                "message": f"Found {len(results)} results for '{query}'" if results else f"No results found for '{query}'",
                "provider": "duckduckgo",
            }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during DuckDuckGo search: {e}")
            return {
                "query": query,
                "timestamp": datetime.utcnow().isoformat(),
                "results_count": 0,
                "results": [],
                "error": f"Search failed: {str(e)}",
                "provider": "duckduckgo",
            }
            return {
                "query": query,
                "timestamp": datetime.utcnow().isoformat(),
                "results_count": 0,
                "results": [],
                "error": f"Search failed: {str(e)}",
            }

    async def _search_web_html(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Fallback search using DuckDuckGo HTML (lite version).

        Args:
            query: The search query
            max_results: Maximum number of results

        Returns:
            List of search results
        """
        try:
            url = "https://lite.duckduckgo.com/lite/"
            params = {"q": query}

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.post(url, data=params, headers=headers)
                response.raise_for_status()
                html = response.text

            # Parse DuckDuckGo lite HTML results
            results = []
            
            # Split by result table rows
            parts = html.split('<tr>')
            
            for part in parts:
                if 'result-link' not in part:
                    continue
                    
                # Extract title and URL from the link
                title = ""
                url = ""
                snippet = ""
                
                # Find the link with title
                if 'class="result-link"' in part:
                    # Extract URL
                    url_match = part.find('href="')
                    if url_match != -1:
                        url_start = url_match + 6
                        url_end = part.find('"', url_start)
                        if url_end != -1:
                            url = part[url_start:url_end]
                    
                    # Extract title (text between > and <)
                    title_start = part.find('>', part.find('result-link')) + 1
                    title_end = part.find('</a>', title_start)
                    if title_start > 0 and title_end != -1:
                        title = part[title_start:title_end].strip()
                
                # Extract snippet
                if 'class="result-snippet"' in part:
                    snippet_start = part.find('>', part.find('result-snippet')) + 1
                    snippet_end = part.find('</td>', snippet_start)
                    if snippet_start > 0 and snippet_end != -1:
                        snippet = part[snippet_start:snippet_end].strip()
                        # Clean HTML tags
                        snippet = snippet.replace('<b>', '').replace('</b>', '')
                
                if url and (title or snippet):
                    results.append({
                        "title": title or snippet[:100],
                        "url": url,
                        "snippet": snippet or title,
                        "source": "DuckDuckGo"
                    })
                    
                    if len(results) >= max_results:
                        break

            logger.info(f"HTML scraping found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error in HTML search fallback: {e}", exc_info=True)
            return []

    async def _get_weather_info(self, location: str) -> dict[str, Any]:
        """Get current weather information for a location.

        Uses web search to find weather information.

        Args:
            location: City name or location query

        Returns:
            Dictionary containing weather information
        """
        try:
            # Use web search to find weather information
            search_query = f"current weather {location}"
            search_results = await self._search_web(search_query, max_results=3)
            
            if search_results.get("results"):
                results = search_results["results"]
                
                # Combine top results into weather info
                weather_info = {
                    "location": location,
                    "timestamp": datetime.utcnow().isoformat(),
                    "information": f"{results[0]['title']}. {results[0]['snippet']}",
                    "url": results[0]["url"],
                    "source": results[0].get("source", "Web Search"),
                    "provider": search_results.get("provider", "unknown"),
                }
                
                # Add Tavily's AI answer if available
                if search_results.get("answer"):
                    weather_info["answer"] = search_results["answer"]
                
                # Add additional context from other results
                if len(results) > 1:
                    weather_info["additional_info"] = [
                        {"title": r["title"], "snippet": r["snippet"][:200], "url": r["url"]}
                        for r in results[1:]
                    ]
                
                return weather_info
            else:
                return {
                    "location": location,
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": "No weather information found",
                    "message": search_results.get("message", "No results found"),
                }

        except Exception as e:
            logger.error(f"Error getting weather info: {e}", exc_info=True)
            return {
                "location": location,
                "timestamp": datetime.utcnow().isoformat(),
                "error": f"Failed to get weather information: {str(e)}",
            }
