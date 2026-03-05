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

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"


settings = Settings()
