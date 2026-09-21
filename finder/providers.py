"""Encrypted bring-your-own AI and web-search provider configuration."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from urllib.parse import urlparse

import requests
from cryptography.fernet import Fernet, InvalidToken

from . import store
from .auth import now

AI_PRESETS = {
    "poe": ("https://api.poe.com/v1/chat/completions", "Claude-Sonnet-4.6"),
    "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4.1-mini"),
    "anthropic": ("https://api.anthropic.com/v1/messages", "claude-3-5-haiku-latest"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta", "gemini-2.0-flash"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "openai/gpt-4.1-mini"),
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    "mistral": ("https://api.mistral.ai/v1/chat/completions", "mistral-small-latest"),
    "ollama": ("http://127.0.0.1:11434/v1/chat/completions", "llama3.1"),
    "lmstudio": ("http://127.0.0.1:1234/v1/chat/completions", "local-model"),
    "custom": ("", ""),
}
SEARCH_PROVIDERS = {"duckduckgo", "tavily", "brave", "serper"}
SEARCH_PROVIDER_ORDER = ["duckduckgo", "tavily", "brave", "serper"]
AI_LABELS = {
    "poe": "Poe (easy setup)", "openai": "OpenAI",
    "anthropic": "Anthropic Claude", "gemini": "Google Gemini",
    "openrouter": "OpenRouter", "groq": "Groq", "mistral": "Mistral",
    "ollama": "Ollama (local)", "lmstudio": "LM Studio (local)",
    "custom": "Other compatible API",
}


def _fernet() -> Fernet:
    secret = os.environ.get("API_ENCRYPTION_KEY") or os.environ.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY must be configured before provider keys can be stored.")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt((value or "").encode("utf-8")).decode("ascii") if value else ""


def decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored provider key cannot be decrypted with the current server key.") from exc


def _validate_base_url(provider: str, value: str) -> str:
    base = (value or AI_PRESETS.get(provider, ("", ""))[0]).strip().rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme == "https" and parsed.netloc:
        return base
    if (provider in {"ollama", "lmstudio"} and
            os.environ.get("ALLOW_LOCAL_AI", "").lower() == "true" and
            parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}):
        return base
    raise ValueError("AI endpoints must use HTTPS. Local endpoints require ALLOW_LOCAL_AI=true.")


def save_config(user_id: str, data: dict) -> dict:
    provider = (data.get("ai_provider") or "").lower()
    search = (data.get("search_provider") or "duckduckgo").lower()
    if provider not in AI_PRESETS:
        raise ValueError("Unsupported AI provider.")
    if search not in SEARCH_PROVIDERS:
        raise ValueError("Unsupported search provider.")
    base_url = _validate_base_url(provider, data.get("ai_base_url") or "")
    model = (data.get("ai_model") or AI_PRESETS[provider][1]).strip()[:160]
    if not model:
        raise ValueError("Enter an AI model name.")
    conn = store.connect()
    try:
        old = conn.execute("SELECT * FROM provider_configs WHERE user_id=?", (user_id,)).fetchone()
        ai_key = data.get("ai_key") or (decrypt(old["ai_key_enc"]) if old else "")
        search_key = data.get("search_key") or (decrypt(old["search_key_enc"]) if old else "")
        if provider not in {"ollama", "lmstudio"} and not ai_key:
            raise ValueError("Enter the API key supplied by your AI provider.")
        if search != "duckduckgo" and not search_key:
            raise ValueError(
                f"{search.title()} Search requires a separate search API key. "
                "Choose DuckDuckGo for web research without a search key."
            )
        stamp = now()
        if old:
            config_id, created = old["id"], old["created_at"]
            conn.execute(
                """UPDATE provider_configs SET ai_provider=?,ai_model=?,ai_base_url=?,
                   ai_key_enc=?,search_provider=?,search_key_enc=?,updated_at=?
                   WHERE id=? AND user_id=?""",
                (provider, model, base_url, encrypt(ai_key), search, encrypt(search_key),
                 stamp, config_id, user_id),
            )
        else:
            config_id, created = uuid.uuid4().hex, stamp
            conn.execute(
                """INSERT INTO provider_configs
                   (id,user_id,ai_provider,ai_model,ai_base_url,ai_key_enc,
                    search_provider,search_key_enc,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (config_id, user_id, provider, model, base_url, encrypt(ai_key), search,
                 encrypt(search_key), created, stamp),
            )
        conn.commit()
    finally:
        conn.close()
    return {"ai_provider": provider, "ai_model": model, "ai_base_url": base_url,
            "search_provider": search, "has_ai_key": bool(ai_key),
            "has_search_key": bool(search_key), "updated_at": stamp}


def get_config(user_id: str, include_keys: bool = False) -> dict | None:
    conn = store.connect()
    try:
        row = conn.execute("SELECT * FROM provider_configs WHERE user_id=?", (user_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    value = dict(row)
    value["has_ai_key"] = bool(value.pop("ai_key_enc", ""))
    value["has_search_key"] = bool(value.pop("search_key_enc", ""))
    if include_keys:
        conn = store.connect()
        try:
            raw = conn.execute("SELECT ai_key_enc,search_key_enc FROM provider_configs WHERE user_id=?",
                               (user_id,)).fetchone()
        finally:
            conn.close()
        value["ai_key"] = decrypt(raw["ai_key_enc"])
        value["search_key"] = decrypt(raw["search_key_enc"])
    return value


def chat(user_id: str, system: str, prompt: str, max_tokens: int = 5000) -> str:
    cfg = get_config(user_id, include_keys=True)
    if not cfg:
        raise ValueError("Configure an AI provider in Settings before generating documents.")
    provider, key = cfg["ai_provider"], cfg.get("ai_key", "")
    url, model = cfg["ai_base_url"], cfg["ai_model"]
    timeout = 110
    if provider == "anthropic":
        response = requests.post(url, timeout=timeout,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": max_tokens, "system": system,
                  "messages": [{"role": "user", "content": prompt}]})
        response.raise_for_status()
        return "\n".join(block.get("text", "") for block in response.json().get("content", []))
    if provider == "gemini":
        endpoint = f"{url}/models/{model}:generateContent?key={key}"
        response = requests.post(endpoint, timeout=timeout, json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.25},
        })
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if provider in {"openrouter", "poe"}:
        headers["HTTP-Referer"] = "https://opportunity-finder-uz4x.onrender.com"
        headers["X-Title"] = "Opportunity Finder"
    response = requests.post(url, timeout=timeout, headers=headers, json={
        "model": model, "temperature": 0.25, "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
    })
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def public_catalog() -> dict:
    return {
        "ai": [{"key": k, "label": AI_LABELS[k], "default_url": v[0],
                "default_model": v[1]} for k, v in AI_PRESETS.items()],
        "search": SEARCH_PROVIDER_ORDER,
    }
