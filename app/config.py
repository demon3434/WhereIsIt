from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WhereIsIt"
    app_env: str = "production"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7
    auth_cookie_name: str = "whereisit_token"
    auth_cookie_secure: bool = False
    postgres_user: str = "whereisit"
    postgres_password: str = "whereisit"
    postgres_db: str = "whereisit"
    database_url: str = ""
    upload_dir: str = "/data/uploads"
    max_upload_mb: int = 10
    max_images_per_item: int = 9
    default_admin_username: str = "admin"
    default_admin_password: str = "admin123456"
    default_admin_nickname: str = "Admin"
    sync_default_admin_password: bool = True
    cors_origins: str = "*"
    service_discovery_enabled: bool = True
    service_discovery_type: str = "_whereisit._tcp.local."
    service_discovery_name: str = "WhereIsIt"
    service_advertise_host: str = ""
    service_advertise_port: int = 0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.database_url:
            self.database_url = f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}@db:5432/{self.postgres_db}"


settings = Settings()
