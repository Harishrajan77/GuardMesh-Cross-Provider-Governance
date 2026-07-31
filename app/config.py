"""
All configuration lives here and comes from environment variables
(or a local .env file). Nothing else in the app reads os.environ
directly  --  that keeps configuration in exactly one place.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Provider API keys. Leave any of these blank to run that provider
    # in MOCK mode  --  no internet or key required. Useful for demos.
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Optional shared-secret header to protect the API. Leave blank to
    # disable auth entirely (handy for local testing).
    GUARDMESH_API_KEY: str | None = None

    POLICY_PATH: str = "configs/policy.yaml"
    DB_PATH: str = "guardmesh.db"
    DATABASE_URL: str = "sqlite:///./guardmesh.db"
    GUARDMESH_DB_URL: str | None = None

    def get_db_url(self) -> str:
        # Fallback path logic
        url = self.GUARDMESH_DB_URL or self.DATABASE_URL
        if url.startswith("sqlite:///./") or url.startswith("sqlite:///"):
            return url
        return url


settings = Settings()
