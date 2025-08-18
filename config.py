import os
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

class Settings(BaseModel):
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    weather_provider: str = os.getenv("WEATHER_PROVIDER", "open-meteo")
    market_data_source: str = os.getenv("MARKET_DATA_SOURCE", "csv")
    db_url: str = os.getenv("DB_URL", "sqlite:///greenhouse.db")
    model_small: str = os.getenv("MODEL_SMALL", "gpt-4o-mini")
    log_tokens: bool = os.getenv("LOG_TOKENS", "false").lower() == "true"

    auth0_domain: str = os.getenv("AUTH0_DOMAIN", "")
    auth0_client_id: str = os.getenv("AUTH0_CLIENT_ID", "")
    auth0_client_secret: str = os.getenv("AUTH0_CLIENT_SECRET", "")
    auth0_redirect_uri: str = os.getenv("AUTH0_REDIRECT_URI", "http://localhost:8501")
    auth0_audience: str = os.getenv("AUTH0_AUDIENCE", "")
    access_code: str = os.getenv("ACCESS_CODE", "")

settings = Settings()
