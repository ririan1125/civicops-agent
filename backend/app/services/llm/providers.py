import httpx
from dataclasses import dataclass

from app.core.config import get_settings


class LLMProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatCompletion:
    content: str
    provider: str
    model: str


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


def _mock_grounded_completion(user_prompt: str) -> str:
    evidence_marker = "Evidence:"
    evidence = user_prompt.split(evidence_marker, 1)[-1].strip() if evidence_marker in user_prompt else user_prompt
    compact = " ".join(evidence.split())
    if not compact:
        return "I cannot answer confidently from the indexed documents."
    return (
        "Based on the retrieved evidence, the answer is: "
        f"{compact[:900]}"
        + ("..." if len(compact) > 900 else "")
    )


def complete_chat(system_prompt: str, user_prompt: str) -> ChatCompletion:
    settings = get_settings()
    if settings.llm_provider.lower() == "deepseek" and settings.deepseek_api_key:
        content = optional_deepseek_completion(system_prompt, user_prompt)
        if content:
            return ChatCompletion(content=content, provider="deepseek", model=settings.deepseek_model)
    return ChatCompletion(content=_mock_grounded_completion(user_prompt), provider="mock", model="mock-grounded")


def llm_planning_enabled() -> bool:
    settings = get_settings()
    return settings.llm_provider.lower() == "deepseek" and bool(settings.deepseek_api_key)
