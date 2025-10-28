try:
    # Pydantic v2
    from pydantic_settings import BaseSettings  # type: ignore
    from pydantic import conint, confloat
except Exception:
    # Pydantic v1 fallback
    from pydantic import BaseSettings, conint, confloat  # type: ignore
from typing import List, Dict
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Server
    AGENT_HOST: str = "0.0.0.0"
    AGENT_PORT: int = 8000

    # External services
    METRICS_MOCK_HOST: str = "localhost"
    METRICS_MOCK_PORT: int = 9000
    DOCS_MOCK_HOST: str = "localhost"
    DOCS_MOCK_PORT: int = 9010
    QDRANT_URL: str = "http://localhost:6333"
    USE_QDRANT: bool = True
    USE_LANGCHAIN: bool = True
    USE_LANGGRAPH: bool = False  # optional switch

    # LLM / Agent parameters
    GGML_MODEL_PATH: str = ""
    AGENT_MAX_ITERATIONS: conint(ge=1, le=20) = 6
    AGENT_MAX_TOKENS: conint(ge=32, le=2048) = 128
    ROUTER_MAX_TOKENS: conint(ge=32, le=512) = 64

    # Thresholds
    DEFAULT_P95_THRESHOLD_MS: conint(ge=1) = 200
    KNOWLEDGE_SCORE_MIN: confloat(ge=0.0, le=1.0) = 0.4
    KNOWLEDGE_SCORE_MIN_AGENT: confloat(ge=0.0, le=1.0) = 0.1

    # Trace compactness
    TRACE_COMPACT_LAST_N: conint(ge=1, le=10) = 3

    # Timeouts / retries
    HTTP_TIMEOUT_SECONDS: confloat(gt=0.0) = 5.0
    HTTP_RETRIES: conint(ge=0, le=5) = 2
    HTTP_RETRY_BACKOFF_SECONDS: confloat(gt=0.0) = 0.3

    # Prompts
    PROMPTS_DIR: str = "prompts"
    ROUTER_PROMPT_VERSION: str = "router_v1.txt"
    REACT_PROMPT_VERSION: str = "react_agent_v1.txt"

    # Service catalog (simple for POC; move to DB in prod)
    SERVICE_CATALOG: List[str] = ["payments", "orders"]

    # Data paths
    DOCS_DIR: str = "seed_data/docs"

    class Config:
        env_file = ".env"

    @property
    def METRICS_BASE_URL(self) -> str:
        return f"http://{self.METRICS_MOCK_HOST}:{self.METRICS_MOCK_PORT}"

    @property
    def DOCS_BASE_URL(self) -> str:
        return f"http://{self.DOCS_MOCK_HOST}:{self.DOCS_MOCK_PORT}"

cfg = Settings()
