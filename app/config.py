from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
)


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
    pg_exec_mode: str = "auto"
    pg_container_name: str = "whereisit-postgres"
    pg_service_name: str = "db"
    pg_tools_image_template: str = "postgres:{major}-alpine"
    pg_tools_image_fallback_template: str = "postgres:{major}"
    pg_tested_max_major: int = 17
    voice_search_enabled: bool = True
    voice_search_mock_final: bool = False
    voice_search_mock_stream: bool = False
    voice_terms_index_delay_seconds: int = 300
    voice_terms_index_poll_seconds: int = 30
    voice_terms_index_batch_size: int = 50
    voice_stream_sample_rate: int = 16000
    voice_stream_channels: int = 1
    voice_stream_max_seconds: int = 15
    voice_stream_partial_interval_ms: int = 150
    voice_offline_timeout_ms: int = 3000
    voice_session_ttl_seconds: int = 300
    voice_hotwords_enabled: bool = True
    voice_asr_engine: str = "faster_whisper"
    voice_stream_engine: str = "sherpa_onnx"
    voice_offline_engine: str = "funasr"
    voice_stream_model_size: str = "tiny"
    voice_offline_model_size: str = "small"
    voice_model_device: str = "cpu"
    voice_model_compute_type: str = "int8"
    voice_model_num_threads: int = 2
    voice_model_download_root: str = "/data/voice-models"
    voice_cleaning_lexicon_dir: str = "/data/voice-cleaning-lexicon"
    voice_sherpa_provider: str = "cpu"
    voice_sherpa_hf_repo: str = "csukuangfj/sherpa-onnx-streaming-paraformer-bilingual-zh-en"
    voice_sherpa_model_url: str = (
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
        "sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2"
    )
    voice_sherpa_model_dir: str = ""
    voice_sherpa_tokens_file: str = "tokens.txt"
    voice_sherpa_encoder_file: str = "encoder.int8.onnx"
    voice_sherpa_decoder_file: str = "decoder.int8.onnx"
    voice_funasr_model: str = "paraformer-zh"
    voice_funasr_vad_model: str = "fsmn-vad"
    voice_funasr_punc_model: str = ""
    voice_funasr_hub: str = "ms"
    voice_mock_final_text: str = "__VOICE_DEBUG_PLACEHOLDER__"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: EnvSettingsSource,
        dotenv_settings: DotEnvSettingsSource,
        file_secret_settings: SecretsSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Keep explicit source order to guarantee runtime env vars (-e / --env-file)
        # override .env defaults in every deployment style.
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.database_url:
            self.database_url = f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}@db:5432/{self.postgres_db}"


settings = Settings()
