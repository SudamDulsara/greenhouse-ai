import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = None

def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
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
    """
    Calls Chat Completions with JSON response format and returns dict.
    """
    client = get_client()
    resp = client.chat.completions.create(
        model=model,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = resp.choices[0].message.content
    import json
    return json.loads(content)
