"""
RAG search capabilities for ReasoningAgentTemplate using AzureAISearchCollection.
Based on Semantic Kernel text search patterns.
"""

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function
from v3.magentic_agents.models.agent_models import SearchConfig


class ReasoningSearch:
    """Handles Azure AI Search integration for reasoning agents."""

    def __init__(self, search_config: SearchConfig | None = None):
        self.search_config = search_config
        self.search_client: SearchClient | None = None

    async def initialize(self, kernel: Kernel) -> bool:
        """Initialize the search collection with embeddings and add it to the kernel."""
        if (
            not self.search_config
            or not self.search_config.endpoint
            or not self.search_config.index_name
        ):
            print("Search configuration not available")
            return False

        try:

            self.search_client = SearchClient(
                endpoint=self.search_config.endpoint,
                credential=AzureKeyCredential(self.search_config.api_key),
                index_name=self.search_config.index_name,
            )

            # Add this class as a plugin so the agent can call search_documents
            kernel.add_plugin(self, plugin_name="knowledge_search")

            print(
                f"Added Azure AI Search plugin for index: {self.search_config.index_name}"
            )
            return True

        except Exception as ex:
            print(f"Could not initialize Azure AI Search: {ex}")
            return False

    @kernel_function(
        name="search_documents",
        description="Search the knowledge base for relevant documents and information. Use this when you need to find specific information from internal documents or data.",
    )
    async def search_documents(self, query: str, limit: str = "3") -> str:
        """Search function that the agent can invoke to find relevant documents."""
        if not self.search_client:
            return "Search service is not available."

        try:
            limit_int = int(limit)
            search_results = []

            results = self.search_client.search(
                search_text=query,
                query_type="simple",
                select=["content", "title", "metadata_storage_path", "metadata_storage_name", "chunk_id"],
                top=limit_int,
            )

            for result in results:
                content = result.get('content', '')
                title = result.get('title', 'Unknown')
                storage_path = result.get('metadata_storage_path', '')
                storage_name = result.get('metadata_storage_name', '')
                chunk_id = result.get('chunk_id', '')
                
                # Format result with citation information
                result_text = f"Content: {content}"
                if storage_path and storage_name:
                    citation = f"\nSource: [{storage_name}]({storage_path})"
                    if chunk_id:
                        citation += f" (Chunk ID: {chunk_id})"
                    result_text += citation
                elif title:
                    result_text += f"\nSource: {title}"
                    if chunk_id:
                        result_text += f" (Chunk ID: {chunk_id})"
                
                search_results.append(result_text)

            if not search_results:
                return f"No relevant documents found for query: '{query}'"

            return "\n\n---\n\n".join(search_results)

        except Exception as ex:
            return f"Search failed: {str(ex)}"

    def is_available(self) -> bool:
        """Check if search functionality is available."""
        return self.search_client is not None


# Simple factory function
async def create_reasoning_search(
    kernel: Kernel, search_config: SearchConfig | None
) -> ReasoningSearch:
    """Create and initialize a ReasoningSearch instance."""
    search = ReasoningSearch(search_config)
    await search.initialize(kernel)
    return search
