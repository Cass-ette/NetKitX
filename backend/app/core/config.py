from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "NetKitX"
    DEBUG: bool = False
    VERSION: str = "0.1.0"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://netkitx:netkitx@localhost:5432/netkitx"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # Plugin directory
    PLUGINS_DIR: str = "plugins"
    ENGINES_DIR: str = "engines/bin"

    # Marketplace
    VERIFIED_PUBLISHERS: list[str] = []

    # Agent
    AGENT_MAX_TURNS: int = 0  # 0 = unlimited
    AGENT_COMMAND_TIMEOUT: int = 30

    # Knowledge extraction
    AUTO_EXTRACT_KNOWLEDGE: bool = False

    # GitHub OAuth
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # User quotas
    DEFAULT_MAX_CONCURRENT_TASKS: int = 5
    DEFAULT_MAX_DAILY_TASKS: int = 100

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # WebAuthn / Passkey
    DOMAIN: str | None = None  # e.g. "wql.me" for production, None for localhost

    class Config:
        env_file = ".env"


settings = Settings()
