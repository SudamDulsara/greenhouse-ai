import os, json, time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import OpenAI
from dotenv import load_dotenv
from config import settings

load_dotenv()
_client = None

def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment.")
        _client = OpenAI(api_key=api_key)
    return _client

@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
)
def chat_json(model: str, system: str, user: str) -> dict:
    data, _, _ = chat_json_with_usage(model, system, user)
    return data

def chat_json_with_usage(model: str, system: str, user: str):
    """
    Returns (data: dict, usage: dict|None, elapsed_s: float)
    """
    client = get_client()
    t0 = time.time()
    resp = client.chat.completions.create(
        model=model,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    elapsed = time.time() - t0
    content = resp.choices[0].message.content
    usage = None
    try:
        usage = resp.usage.model_dump() if hasattr(resp, "usage") and resp.usage else None
    except Exception:
        usage = None
    return json.loads(content), usage, elapsed
