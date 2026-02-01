from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Alkalmazáskonfiguráció, amelyet környezeti változók vezérelnek."""

    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    data_dir: Path = Field(default=Path("data"), env="DATA_DIR")
    model_name: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")
    # Webes keresési integráció eltávolítva — a kereséssel kapcsolatos env változók már nincsenek használatban.

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "protected_namespaces": ("settings_",),
    }


settings = Settings()

# A legegyszerűbb későbbi logika érdekében időben hozzuk létre az alapadat-mappákat
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.data_dir.joinpath("conversations").mkdir(parents=True, exist_ok=True)
settings.data_dir.joinpath("users").mkdir(parents=True, exist_ok=True)
