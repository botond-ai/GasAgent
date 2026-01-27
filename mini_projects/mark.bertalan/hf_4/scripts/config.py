"""
Configuration management module for application settings.

Provides centralized configuration loading from environment variables
with validation and default values.

Single Responsibility Principle: Exclusively handles configuration
loading, parsing, and validation without mixing business logic concerns.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class Config:
    """
    Immutable configuration container for application settings.

    Uses dataclass for automatic initialization, representation, and
    comparison methods. Configuration values are loaded from environment
    variables with sensible defaults for optional settings.

    Attributes:
        openai_api_key: Authentication key for OpenAI API access (required).
        embedding_model: Model identifier for OpenAI embeddings.
                        Default: 'text-embedding-3-small' (1536 dimensions).
        llm_model: Model identifier for OpenAI chat completions (RAG).
                   Default: 'gpt-4o-mini' for cost-effective generation.
        chroma_db_path: Filesystem path for ChromaDB persistent storage.
                       Default: './chroma_db' in current working directory.
        collection_name: ChromaDB collection identifier for vector storage.
                        Default: 'prompts' for prompt embedding storage.
    """
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    embedding_chunk_size: int = 500
    overlap: int = 0
    chroma_db_path: str = "./chroma_db"
    documents_root: Path = Path("./embedding_sources")
    collection_name: str = "prompts"

    # Jira integration settings (optional)
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_enabled: bool = False
    use_jira_mcp: bool = True  # Use MCP if available, fallback to REST API

    # Department to Jira project mapping
    # Format: "hr:HR,dev:DEV,support:SUP,management:MGT"
    jira_department_mapping: dict = None

    # Teams integration settings (optional)
    teams_enabled: bool = False
    # Department to Teams webhook URL mapping
    # Format: "hr:webhook_url_1,dev:webhook_url_2,..."
    teams_webhooks: dict = None

    @classmethod
    def from_env(cls) -> "Config":
        """
        Factory method to construct Config from environment variables.

        Automatically loads variables from a .env file (if present) using
        python-dotenv, then reads from the environment. Required variables
        must be present; optional variables fall back to class defaults.

        Environment Variables:
            OPENAI_API_KEY (required): OpenAI API authentication key
            EMBEDDING_MODEL (optional): Override default embedding model
            LLM_MODEL (optional): Override default LLM model for RAG
            CHROMA_DB_PATH (optional): Override default database path
            COLLECTION_NAME (optional): Override default collection name

        Returns:
            Config instance populated with environment values and defaults.

        Raises:
            ValueError: When OPENAI_API_KEY is missing from environment.
                       Includes helpful message directing users to .env setup.
        """
        # Load environment variables from .env file if present
        load_dotenv()

        # Validate required configuration
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required but not found. "
                "Please copy .env.example to .env and configure your API key."
            )

        # Construct config with environment values, falling back to defaults
        documents_root_str = os.getenv("DOCUMENTS_ROOT")
        documents_root = Path(documents_root_str) if documents_root_str else cls.documents_root

        # Parse integer config values
        embedding_chunk_size = int(os.getenv("EMBEDDING_CHUNK_SIZE", cls.embedding_chunk_size))
        overlap = int(os.getenv("OVERLAP", cls.overlap))

        # Parse Jira configuration
        jira_base_url = os.getenv("JIRA_BASE_URL", "")
        jira_email = os.getenv("JIRA_EMAIL", "")
        jira_api_token = os.getenv("JIRA_API_TOKEN", "")
        jira_enabled = jira_base_url and jira_email and jira_api_token
        use_jira_mcp = os.getenv("USE_JIRA_MCP", "true").lower() in ("true", "1", "yes")

        # Parse department mapping
        jira_department_mapping = {}
        mapping_str = os.getenv("JIRA_DEPARTMENT_MAPPING", "hr:HR,dev:DEV,support:SUP,management:MGT")
        if mapping_str:
            for pair in mapping_str.split(","):
                if ":" in pair:
                    dept, project = pair.split(":", 1)
                    jira_department_mapping[dept.strip().lower()] = project.strip()

        # Parse Teams webhook mapping
        teams_webhooks = {}
        teams_webhooks_str = os.getenv("TEAMS_WEBHOOKS", "")
        if teams_webhooks_str:
            for pair in teams_webhooks_str.split(","):
                if ":" in pair:
                    dept, webhook = pair.split(":", 1)
                    teams_webhooks[dept.strip().lower()] = webhook.strip()

        teams_enabled = bool(teams_webhooks)

        return cls(
            openai_api_key=openai_api_key,
            embedding_model=os.getenv("EMBEDDING_MODEL", cls.embedding_model),
            llm_model=os.getenv("LLM_MODEL", cls.llm_model),
            embedding_chunk_size=embedding_chunk_size,
            overlap=overlap,
            chroma_db_path=os.getenv("CHROMA_DB_PATH", cls.chroma_db_path),
            documents_root=documents_root,
            collection_name=os.getenv("COLLECTION_NAME", cls.collection_name),
            jira_base_url=jira_base_url,
            jira_email=jira_email,
            jira_api_token=jira_api_token,
            jira_enabled=jira_enabled,
            use_jira_mcp=use_jira_mcp,
            jira_department_mapping=jira_department_mapping,
            teams_enabled=teams_enabled,
            teams_webhooks=teams_webhooks,
        )
