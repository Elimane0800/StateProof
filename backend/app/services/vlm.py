"""VLM orchestration: Gemini primary, OpenAI fallback, JSON-only, with retries.

The classifier calls `complete_json(prompt, image_b64)`. Each configured
provider is tried in order; on transient failure or non-JSON output we retry
with the parse error fed back into the prompt. If no provider is configured the
caller (classifier) falls back to the deterministic heuristic path.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

from app.core.config import get_settings

log = logging.getLogger("synchronaise.vlm")


class ProviderUnavailable(RuntimeError):
    """No VLM provider is configured/reachable."""


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output.")
    return json.loads(text[start : end + 1])


def _call_gemini(prompt: str, image_b64: Optional[str]) -> str:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ProviderUnavailable("GEMINI_API_KEY not set")
    try:
        import google.generativeai as genai
    except ImportError as exc:  # pragma: no cover
        raise ProviderUnavailable("google-generativeai not installed") from exc

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        settings.gemini_model,
        generation_config={"response_mime_type": "application/json"},
    )
    parts: list[Any] = [prompt]
    if image_b64:
        parts.append({"mime_type": "image/png", "data": base64.b64decode(image_b64)})
    resp = model.generate_content(parts, request_options={"timeout": settings.request_timeout_s})
    return resp.text


def _call_openai(prompt: str, image_b64: Optional[str]) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ProviderUnavailable("OPENAI_API_KEY not set")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise ProviderUnavailable("openai not installed") from exc

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.request_timeout_s)
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    if image_b64:
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
        )
    resp = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": content}],
    )
    return resp.choices[0].message.content or ""


_PROVIDERS = (("gemini", _call_gemini), ("openai", _call_openai))


def available() -> bool:
    settings = get_settings()
    return bool(settings.gemini_api_key or settings.openai_api_key)


def complete_json(prompt: str, image_b64: Optional[str] = None) -> dict[str, Any]:
    settings = get_settings()
    last_error: Exception | None = None

    for name, fn in _PROVIDERS:
        # Each provider starts from the original prompt. Retry error-context is
        # accumulated per provider only, never carried across to the next one.
        attempt_prompt = prompt
        for attempt in range(settings.max_retries + 1):
            try:
                text = fn(attempt_prompt, image_b64)
                return _extract_json(text)
            except ProviderUnavailable as exc:
                last_error = exc
                break  # try next provider
            except Exception as exc:  # noqa: BLE001 - retry on parse/transport errors
                last_error = exc
                log.warning("VLM %s attempt %s failed: %s", name, attempt + 1, exc)
                attempt_prompt = (
                    f"{attempt_prompt}\n\nYour previous response failed with: {exc}. "
                    "Return ONLY valid JSON matching the requested shape."
                )

    raise ProviderUnavailable(f"All VLM providers failed. Last error: {last_error}")
