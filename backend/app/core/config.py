from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # PostgreSQL Database URL
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/dci_db"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/dci_db"

    # Evidence Storage
    EVIDENCE_STORAGE_PATH: str = "./data/evidence"
    FIXTURES_PATH: str = "./data/fixtures"

    # Playwright Facebook Settings
    FACEBOOK_STORAGE_STATE: str | None = None
    PLAYWRIGHT_HEADLESS: bool = True

    # Crawler Limits & Timeouts
    CRAWL_DEFAULT_PAGE_TIMEOUT: int = 30000
    CRAWL_DEFAULT_TIMEOUT: int = 120000
    QUICK_POST_LIMIT: int = 10
    DEEP_POST_LIMIT: int = 75
    QUICK_MAX_SCROLL_CYCLES: int = 4
    DEEP_MAX_SCROLL_CYCLES: int = 25
    BLOCK_MEDIA_ON_QUICK_CRAWL: bool = True

    # Scoring & Threshold Decisions
    QUICK_LOW_THRESHOLD: float = 25.0
    QUICK_DEEP_THRESHOLD: float = 65.0
    DEEP_CRAWL_THRESHOLD: float = 65.0
    REVIEW_THRESHOLD: float = 75.0

    # Gemini & AI Provider Settings
    GEMINI_API_KEY: str | None = None
    GEMINI_FAST_MODEL: str = "gemini-2.5-flash"
    GEMINI_ANALYSIS_MODEL: str = "gemini-2.5-pro"
    GEMINI_ENABLED: bool = True
    GEMINI_TIMEOUT_SECONDS: float = 30.0
    GEMINI_MAX_RETRIES: int = 2
    GEMINI_CONCURRENCY: int = 3
    GEMINI_MAX_POSTS_PER_REQUEST: int = 20
    AI_PROMPT_VERSION: str = "1.0.0"
    AI_SCHEMA_VERSION: str = "1.0.0"
    AI_FALLBACK_TO_MOCK: bool = True

    # Worker Settings
    CRAWLER_CONCURRENCY: int = 2
    WORKER_POLL_INTERVAL: float = 2.0
    WORKER_MAX_RETRY_ATTEMPTS: int = 3

    # System Versions for Auditing & Provenance
    COLLECTOR_VERSION: str = "2.0.0"
    EXTRACTOR_VERSION: str = "1.0.0"
    SCORING_VERSION: str = "1.0.0"

    @property
    def evidence_path(self) -> Path:
        path = Path(self.EVIDENCE_STORAGE_PATH)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def fixtures_path(self) -> Path:
        path = Path(self.FIXTURES_PATH)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
