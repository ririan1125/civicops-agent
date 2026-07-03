import httpx

from app.core.config import get_settings


class LLMProviderError(RuntimeError):
    pass


def optional_deepseek_completion(system_prompt: str, user_prompt: str) -> str | None:
    settings = get_settings()
    if settings.llm_provider.lower() != "deepseek" or not settings.deepseek_api_key:
        return None

    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key}"}
    with httpx.Client(timeout=45) as client:
        response = client.post(f"{settings.deepseek_base_url.rstrip('/')}/v1/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]
