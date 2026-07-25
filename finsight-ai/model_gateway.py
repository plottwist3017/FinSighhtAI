import os
import time
import requests
from dotenv import dotenv_values

_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

_token_cache: dict = {"token": None, "expires_at": 0.0}


def _cfg() -> dict:
    return dotenv_values(_ENV_PATH)


def _get_iam_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    cfg = _cfg()
    api_key = cfg.get("API_KEY", "")

    response = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": api_key,
        },
        timeout=30,
    )
    response.raise_for_status()
    token_data = response.json()

    _token_cache["token"] = token_data["access_token"]
    _token_cache["expires_at"] = now + 50 * 60

    return _token_cache["token"]


def invoke_llm(prompt: str, max_new_tokens: int = 4096) -> str:
    cfg = _cfg()
    cloud_url = cfg.get("CLOUD_URL", "").rstrip("/")
    llm_name = cfg.get("LLM_NAME", "")
    project_id = cfg.get("PROJECT_ID", "")

    token = _get_iam_token()

    endpoint = f"{cloud_url}/ml/v1/text/generation?version=2023-05-29"

    payload = {
        "model_id": llm_name,
        "project_id": project_id,
        "input": prompt,
        "parameters": {
            "max_new_tokens": max_new_tokens,
            "temperature": 0.0,
            "repetition_penalty": 1.05,
            "stop_sequences": ["```"],
        },
    }

    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()

    return response.json()["results"][0]["generated_text"]
