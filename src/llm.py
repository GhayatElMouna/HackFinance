"""Client LLM unifie — Gemini (defaut) avec repli OpenAI-compatible."""
from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)


def _provider() -> str:
    explicit = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if explicit in {"gemini", "google", "openai"}:
        return "gemini" if explicit == "google" else explicit
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    if os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"):
        return "openai"
    return "gemini"


def _gemini_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


def _openai_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()


def llm_configured() -> bool:
    if _provider() == "openai":
        return bool(_openai_key())
    return bool(_gemini_key())


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=8))
def chat(
    prompt: str,
    *,
    system: str = "Tu es un analyste budgetaire et de marche. Reponds en francais.",
    temperature: float = 0.1,
    timeout: int = 60,
) -> str | None:
    """Appelle Gemini (defaut) ou OpenAI. Retourne le texte ou None si non configure."""
    provider = _provider()
    if provider == "openai":
        return _chat_openai(prompt, system=system, temperature=temperature, timeout=timeout)
    return _chat_gemini(prompt, system=system, temperature=temperature, timeout=timeout)


def _chat_gemini(
    prompt: str,
    *,
    system: str,
    temperature: float,
    timeout: int,
) -> str | None:
    api_key = _gemini_key()
    if not api_key:
        return None
    model = os.getenv("LLM_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
    url = GEMINI_URL.format(model=model)
    payload: dict[str, Any] = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    response = requests.post(
        url,
        params={"key": api_key},
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini: reponse vide ({data.get('error') or data})")
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    text = "".join(part.get("text") or "" for part in parts).strip()
    return text or None


def _chat_openai(
    prompt: str,
    *,
    system: str,
    temperature: float,
    timeout: int,
) -> str | None:
    api_key = _openai_key()
    if not api_key:
        return None
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return (content or "").strip() or None
