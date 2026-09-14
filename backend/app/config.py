from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./streammind.db"
    jwt_secret: str = "development-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    aws_region: str = "ap-south-1"
    s3_upload_bucket: str = "streammind-original-videos"
    s3_endpoint_url: str | None = None
    max_upload_bytes: int = 2 * 1024 * 1024 * 1024
    presigned_upload_expire_seconds: int = 900

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
