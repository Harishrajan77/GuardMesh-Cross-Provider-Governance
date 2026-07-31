from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    GUARDMESH_API_KEY: str | None = None

    POLICY_PATH: str = "configs/policy.yaml"
    DB_PATH: str = "guardmesh.db"
    DATABASE_URL: str = "sqlite:///./guardmesh.db"
    GUARDMESH_DB_URL: str | None = None

    def get_db_url(self) -> str:
        url = self.GUARDMESH_DB_URL or self.DATABASE_URL
        if url.startswith("sqlite:///./") or url.startswith("sqlite:///"):
            return url
        return url


settings = Settings()
