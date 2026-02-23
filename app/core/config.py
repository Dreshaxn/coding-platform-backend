from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str  # Secret key for JWT token signing
    ALGORITHM: str = "HS256"  # Algorithm for JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Token expiration time in minutes

    REDIS_URL: str = "redis://localhost:6379/0"
    WS_HEARTBEAT_INTERVAL: int = 30
    CACHE_DEFAULT_TTL: int = 300

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()