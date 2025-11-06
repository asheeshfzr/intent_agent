"""
Configuration Module
--------------------
Centralized configuration for the Agentic AI Orchestrator.

All literals, thresholds, ports, and feature flags are externalized here.
Environment variables override defaults (via .env).
"""

from pydantic_settings import BaseSettings
from pydantic import Field, AnyHttpUrl
from typing import List, Optional


class Settings(BaseSettings):
    # ----------------------------------------------------------------------
    # General application metadata
    app_name: str = "Agentic AI Orchestrator"
    app_version: str = "1.0.0"
    environment: str = Field("local", description="Runtime environment (local/dev/prod)")

    # ----------------------------------------------------------------------
    # Core networking / infrastructure
    agent_host: str = Field("0.0.0.0", description="Host address for the agent service")
    use_qdrant: bool = Field(True, description="Enable Qdrant vector store for embeddings and RAG")
    qdrant_url: str = Field("http://localhost:6333", description="Qdrant service endpoint URL")

    # ----------------------------------------------------------------------
    # Model configuration
    ggml_model_path: str = Field(
        "/Users/asheeshbhardwaj/workspace/models/llama-2-7b.Q4_0.gguf",
        description="Absolute path to local GGUF Llama model file."
    )
    use_langchain: bool = Field(True, description="Enable LangChain compatibility layer")
    use_langgraph: bool = Field(True, description="Enable LangGraph orchestration")
    model_max_tokens: int = Field(2048, description="Maximum tokens for local model generation")

    # ----------------------------------------------------------------------
    # Prompt management
    prompts_path: str = Field(
        "prompts/",
        description="Root directory for prompt templates"
    )
    prompt_version: str = Field(
        "v1",
        description="Prompt version folder name"
    )

    # ----------------------------------------------------------------------
    # Service mock ports
    metrics_mock_port: int = Field(9000, description="Local port for metrics mock service")
    docs_mock_port: int = Field(9010, description="Local port for docs mock service")
    agent_port: int = Field(8000, description="Port for main agent service")

    # ----------------------------------------------------------------------
    # Agent / router thresholds
    router_max_tokens: int = Field(128, description="Token limit for routing prompt responses")
    agent_max_iterations: int = Field(6, description="Maximum reasoning / action steps per workflow")
    vector_score_threshold_primary: float = Field(0.4, description="Primary vector similarity threshold")
    vector_score_threshold_fallback: float = Field(0.1, description="Fallback vector similarity threshold")
    default_p95_threshold_ms: int = Field(500, description="Default p95 latency threshold for metrics")
    compact_trace_length: int = Field(3, description="Compact trace size for summarization")

    # ----------------------------------------------------------------------
    # External / API configuration
    service_catalog: str = Field(
        "payments,orders,loans",
        description="Comma-separated list of known mock services"
    )
    allowed_domains: List[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1"],
        description="Allowlisted outbound domains"
    )

    # ----------------------------------------------------------------------
    # Data and RAG configuration
    seed_data_path: str = Field(
        "seed_data/docs/",
        description="Path to seed documents for vector embeddings"
    )
    embeddings_reindex_interval_hours: int = Field(
        24, description="Reindexing interval for RAG vector store"
    )

    # ----------------------------------------------------------------------
    # Observability & telemetry
    enable_otel: bool = Field(False, description="Enable OpenTelemetry tracing")
    otel_exporter_url: Optional[AnyHttpUrl] = Field(
        None, description="Optional OpenTelemetry collector endpoint"
    )
    enable_langfuse: bool = Field(False, description="Enable Langfuse event tracing")
    enable_structured_logging: bool = Field(True, description="Use structured JSON logs")
    log_level: str = Field("INFO", description="Logging verbosity")

    # ----------------------------------------------------------------------
    # Safety & guardrails
    enable_content_filter: bool = Field(True, description="Enable content policy checks for LLM outputs")
    sanitize_inputs: bool = Field(True, description="Pre-sanitize inputs to prevent injection attacks")

    # ----------------------------------------------------------------------
    # Internal tuning / feature flags
    feature_flags: List[str] = Field(
        default_factory=lambda: ["replan", "clarify", "reflect"],
        description="Enabled agentic behavior flags"
    )

    # ----------------------------------------------------------------------
    # Configuration source
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow unknown .env keys to prevent validation errors
        case_sensitive = False  # ✅ Allow UPPER_CASE env vars to populate lowercase fields

# --------------------------------------------------------------------------
# Global settings instance (for imports across app modules)
# --------------------------------------------------------------------------
settings = Settings()
cfg = settings  # alias for convenience

# Optional: pretty-print config at startup
if settings.environment == "local":
    print(f"[Config] Loaded settings for {settings.environment.upper()} environment.")
    print(f"[Config] Model path: {settings.ggml_model_path}")
    print(f"[Config] Router max tokens: {settings.router_max_tokens}")
    print(f"[Config] Prompts path: {settings.prompts_path}/{settings.prompt_version}")
