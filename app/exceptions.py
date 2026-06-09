class EnrichmentError(Exception):
    """Base exception for enrichment failures."""


class AgentProviderError(EnrichmentError):
    """Raised when the LLM provider cannot complete an enrichment request."""


class AgentResponseError(EnrichmentError):
    """Raised when the LLM provider returns invalid structured data."""
