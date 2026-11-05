from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_name: str = 'CurbOps AI'
    cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'
    source_refresh_min_seconds: int = 240
    request_timeout_seconds: int = 13
    road_matrix_optimization: bool = True  # v1.3: road-time local-search + counterfactual
    routing_provider: str = 'osrm_demo'  # osrm_demo (no key, noncommercial) | ors (API key) | illustrative
    ors_api_key: str = ''
    ors_base_url: str = 'https://api.heigit.org'
    osrm_base_url: str = 'https://router.project-osrm.org'
    agent_provider: str = 'demo'  # demo, google, groq, auto
    google_api_key: str = ''
    gemini_model: str = 'gemini-3.5-flash-lite'
    gemini_advanced_model: str = 'gemini-3.8-flash'
    groq_api_key: str = ''
    groq_model: str = 'openai/gpt-oss-20b'
    live_max_incidents: int = 60

@lru_cache
def get_settings() -> Settings:
    return Settings()
