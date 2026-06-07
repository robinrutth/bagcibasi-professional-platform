from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Bagcibasi Logistics AI Platform"
    database_url: str = "postgresql+psycopg://bagcibasi:bagcibasi_dev_password@localhost:5432/bagcibasi_logistics?client_encoding=utf8"
    cors_origins: str = "http://localhost:3000"
    openai_api_key: str = ""
    secret_key: str = ""
    app_secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    debug: bool = False
    seed_demo_data: bool = False
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = "noreply@yourdomain.com"
    mail_server: str = ""
    mail_port: int = 587
    mail_tls: bool = True
    mail_ssl: bool = False
    platform_name: str = "Bagcibasi Logistics AI"
    frontend_url: str = "http://localhost:3000"
    ors_api_key: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def jwt_secret_key(self) -> str:
        return self.secret_key


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.secret_key:
        raise ValueError("SECRET_KEY env variable must be set")
    return settings
