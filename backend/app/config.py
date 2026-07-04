from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    blackboard_login_url: str = "https://learn.humber.ca"
    blackboard_courses_url: str = "https://learn.humber.ca/ultra/course"
    session_path: Path = Path("./data/session.json")
    browser_profile_dir: Path = Path("./data/browser_profile")
    login_status_path: Path = Path("./data/login_status.json")
    database_path: Path = Path("./data/study_copilot.db")
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    sync_headless: bool = False
    browser_channel: str = ""

    @property
    def blackboard_origin(self) -> str:
        parsed = urlparse(self.blackboard_login_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def blackboard_url(self) -> str:
        return self.blackboard_login_url


settings = Settings()
