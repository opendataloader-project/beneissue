"""Configuration and LangSmith setup."""

import os


def setup_langsmith() -> None:
    """Configure LangSmith tracing."""
    # Set environment variables for LangChain tracing
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "beneissue")

    # Verify API key is set
    if not os.environ.get("LANGCHAIN_API_KEY"):
        raise ValueError("LANGCHAIN_API_KEY environment variable is required")
