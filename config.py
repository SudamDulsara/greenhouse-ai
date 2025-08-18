import os
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

class Settings(BaseModel):
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    weather_provider: str = os.getenv("WEATHER_PROVIDER", "open-meteo")
    market_data_source: str = os.getenv("MARKET_DATA_SOURCE", "csv")
    db_url: str = os.getenv("DB_URL", "sqlite:///greenhouse.db")
    # models
    model_small: str = os.getenv("MODEL_SMALL", "gpt-4o-mini")
    # toggles
    log_tokens: bool = os.getenv("LOG_TOKENS", "false").lower() == "true"

settings = Settings()
