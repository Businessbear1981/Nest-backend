"""
Thin wrapper around Claude API — supports both direct Anthropic SDK
and OpenRouter (OpenAI-compatible) as backends.

Priority: ANTHROPIC_API_KEY (direct) > OPENROUTER_API_KEY (via OpenRouter)
"""
from __future__ import annotations

import os
from typing import Optional

from config import Config


class ClaudeUnavailable(RuntimeError):
    pass


_client = None
_backend = None  # "anthropic" or "openrouter"


def _get_client():
    global _client, _backend
    if _client is not None:
        return _client

    # Try direct Anthropic first
    if Config.ANTHROPIC_API_KEY:
        import anthropic
        _client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        _backend = "anthropic"
        return _client

    # Fall back to OpenRouter
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if openrouter_key:
        from openai import OpenAI
        _client = OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
        )
        _backend = "openrouter"
        return _client

    raise ClaudeUnavailable(
        "No API key set. Add ANTHROPIC_API_KEY or OPENROUTER_API_KEY to backend/.env"
    )


def complete(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> str:
    """
    Single-shot completion. Works with both Anthropic SDK and OpenRouter.
    """
    client = _get_client()

    if _backend == "anthropic":
        resp = client.messages.create(
            model=model or Config.ANTHROPIC_MODEL,
            max_tokens=max_tokens or Config.ANTHROPIC_MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return "\n".join(parts).strip()

    elif _backend == "openrouter":
        # OpenRouter uses OpenAI-compatible API
        resp = client.chat.completions.create(
            model="anthropic/claude-sonnet-4-20250514" if model and "sonnet" in model else "anthropic/claude-sonnet-4",
            max_tokens=max_tokens or Config.ANTHROPIC_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            extra_headers={
                "HTTP-Referer": "https://nestadvisors.com",
                "X-Title": "NEST Advisors Platform",
            },
        )
        return resp.choices[0].message.content.strip()

    raise ClaudeUnavailable("No backend configured")
