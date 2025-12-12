"""Web Search Service for MCP Server.

Provides web search capabilities using multiple providers:
1. Tavily AI (primary - requires API key, optimized for AI agents)
2. SerpAPI/Google (secondary - requires API key, uses Google search)
3. DuckDuckGo (fallback - no API key needed, limited results)
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

import httpx

from core.factory import Domain, MCPToolBase

logger = logging.getLogger(__name__)


class WebSearchService(MCPToolBase):
    """Web search service with multiple provider support."""

    def __init__(self):
        super().__init__(Domain.GENERAL)
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.serpapi_key = os.getenv("SERPAPI_API_KEY")
        
        # Determine which provider to use
        if self.tavily_api_key:
            self.primary_provider = "tavily"
            logger.info("WebSearchService: Using Tavily as primary provider")
        elif self.serpapi_key:
            self.primary_provider = "serpapi"
            logger.info("WebSearchService: Using SerpAPI as primary provider")
        else:
            self.primary_provider = "duckduckgo"
            logger.warning("WebSearchService: No API keys found, using DuckDuckGo (limited functionality)")

    @property
    def tool_count(self) -> int:
        """Return the number of tools provided by this service."""
        return 2  # search_web and get_weather

    def register_tools(self, mcp) -> None:
        """Register web search tools with the MCP server."""

        @mcp.tool(tags={self.domain.value})
        async def search_web(query: str, max_results: int = 5) -> dict[str, Any]:
            """Search the web for information using the best available search provider.

            Args:
                query: The search query (e.g., "latest technology trends 2025")
                max_results: Maximum number of results to return (1-10, default: 5)

            Returns:
                Search results with titles, URLs, and snippets from Tavily, SerpAPI, or DuckDuckGo
            """
            logger.info(f"Web search requested: '{query}' (max_results={max_results}, provider={self.primary_provider})")
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
        """Search the web using the best available provider.

        Tries providers in order: Tavily -> SerpAPI -> DuckDuckGo

        Args:
            query: The search query
            max_results: Maximum number of results to return (default: 5, max: 10)

        Returns:
            Dictionary containing search results with titles, URLs, and snippets
        """
        max_results = min(max(1, max_results), 10)  # Clamp between 1 and 10
        
        errors = []
        
        # Try primary provider first
        if self.primary_provider == "tavily" and self.tavily_api_key:
            try:
                return await self._search_tavily(query, max_results)
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}, falling back...")
                errors.append(f"Tavily: {str(e)}")
        
        if self.primary_provider == "serpapi" and self.serpapi_key:
            try:
                return await self._search_serpapi(query, max_results)
            except Exception as e:
                logger.warning(f"SerpAPI search failed: {e}, falling back...")
                errors.append(f"SerpAPI: {str(e)}")
        
        # Try DuckDuckGo as fallback
        try:
            logger.info("Using DuckDuckGo fallback for web search")
            return await self._search_duckduckgo(query, max_results)
        except Exception as e:
            logger.error(f"All search providers failed. Errors: {errors + [f'DuckDuckGo: {str(e)}']}")
            return {
                "query": query,
                "timestamp": datetime.utcnow().isoformat(),
                "results_count": 0,
                "results": [],
                "error": f"All search providers failed: {'; '.join(errors + [f'DuckDuckGo: {str(e)}'])}",
                "provider": "none",
            }

    async def _search_tavily(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """Search using Tavily AI (optimized for AI agents).

        Args:
            query: The search query
            max_results: Maximum number of results

        Returns:
            Dictionary containing search results
        """
        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": self.tavily_api_key,
                "query": query,
                "max_results": min(max_results, 10),
                "search_depth": "basic",  # or "advanced" for more depth
                "include_answer": True,
                "include_raw_content": False,
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("results", []):
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
                "answer": data.get("answer", ""),  # AI-generated answer
                "message": f"Found {len(results)} results via Tavily AI",
                "provider": "tavily",
            }

        except httpx.HTTPError as e:
            logger.error(f"Tavily API error: {e}")
            raise

    async def _search_serpapi(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """Search using SerpAPI (Google search).

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
                "api_key": self.serpapi_key,
                "engine": "google",
                "num": min(max_results, 10),
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
                results.append({
                    "title": data.get("Heading", ""),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("Abstract", ""),
                    "source": "DuckDuckGo Instant Answer",
                })

            # Get related topics
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else topic.get("Text", "")[:100],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                        "source": "DuckDuckGo",
                    })
                elif isinstance(topic, dict) and "Topics" in topic:
                    # Handle nested topics
                    for subtopic in topic.get("Topics", [])[:max_results]:
                        if len(results) >= max_results:
                            break
                        results.append({
                            "title": subtopic.get("Text", "").split(" - ")[0] if " - " in subtopic.get("Text", "") else subtopic.get("Text", "")[:100],
                            "url": subtopic.get("FirstURL", ""),
                            "snippet": subtopic.get("Text", ""),
                            "source": "DuckDuckGo",
                        })

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
            raise
        except Exception as e:
            logger.error(f"Error during DuckDuckGo search: {e}")
            raise

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
                url_val = ""
                snippet = ""
                
                # Find the link with title
                if 'class="result-link"' in part:
                    # Extract URL
                    url_match = part.find('href="')
                    if url_match != -1:
                        url_start = url_match + 6
                        url_end = part.find('"', url_start)
                        if url_end != -1:
                            url_val = part[url_start:url_end]
                    
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
                
                if url_val and (title or snippet):
                    results.append({
                        "title": title or snippet[:100],
                        "url": url_val,
                        "snippet": snippet or title,
                        "source": "DuckDuckGo HTML"
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
            # Search for weather using the primary search provider
            search_query = f"current weather in {location}"
            search_results = await self._search_web(search_query, max_results=3)

            if search_results.get("results"):
                # Extract weather info from search results
                weather_info = {
                    "location": location,
                    "timestamp": datetime.utcnow().isoformat(),
                    "information": f"{search_results['results'][0]['title']}. {search_results['results'][0]['snippet']}",
                    "url": search_results['results'][0]["url"],
                    "source": f"Web Search ({search_results.get('provider', 'unknown')})",
                    "provider": search_results.get("provider"),
                }

                # Add AI-generated answer if available (from Tavily)
                if search_results.get("answer"):
                    weather_info["answer"] = search_results["answer"]

                # Add additional context from other results
                if len(search_results["results"]) > 1:
                    weather_info["additional_info"] = [
                        {"title": r["title"], "snippet": r["snippet"][:200], "url": r["url"]}
                        for r in search_results["results"][1:]
                    ]

                return weather_info
            else:
                return {
                    "location": location,
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": "No weather information found",
                    "provider": search_results.get("provider"),
                }

        except Exception as e:
            logger.error(f"Error getting weather info: {e}", exc_info=True)
            return {
                "location": location,
                "timestamp": datetime.utcnow().isoformat(),
                "error": f"Failed to get weather information: {str(e)}",
            }
