from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str

    class Config:
        env_file = ".env"  # This tells pydantic to load .env automatically
        env_file_encoding = 'utf-8'

settings = Settings()