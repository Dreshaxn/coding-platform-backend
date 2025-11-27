from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str  # Secret key for JWT token signing
    ALGORITHM: str = "HS256"  # Algorithm for JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Token expiration time in minutes

    class Config:
        env_file = ".env"  # This tells pydantic to load .env automatically
        env_file_encoding = 'utf-8'

settings = Settings()