"""
ARIA — Base LLM Provider
Kimi K2 via NVIDIA API using ChatOpenAI (LangChain-native).
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
from typing import Any, Dict, Iterator, List, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

load_dotenv()

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL   = "meta/llama-3.3-70b-instruct"
# Multimodal (VLM) model used by modules that reason on images
# (Agent_A — state description, Agent_B — entry/exit comparison).
DEFAULT_VISION_MODEL = "meta/llama-3.2-90b-vision-instruct"
DEFAULT_TEMP    = 0.6
DEFAULT_TOKENS  = 4096


def get_nvidia_llm(
    model_name:  str   = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMP,
    max_tokens:  int   = DEFAULT_TOKENS,
) -> ChatOpenAI:
    """Factory — returns a ChatOpenAI pointed at the NVIDIA endpoint."""
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise ValueError("NVIDIA_API_KEY missing from environment variables.")
    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        base_url=NVIDIA_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
    )


class ChatNVIDIA:
    """
    Adapter autour de ChatOpenAI compatible avec create_react_agent.
    Expose invoke, ainvoke, stream, bind_tools.
    """

    def __init__(
        self,
        model_name:  str   = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMP,
        max_tokens:  int   = DEFAULT_TOKENS,
    ):
        self.llm = get_nvidia_llm(model_name, temperature, max_tokens)

    def invoke(self, messages: List[BaseMessage], **kwargs: Any):
        return self.llm.invoke(messages, **kwargs)

    async def ainvoke(self, messages: List[BaseMessage], **kwargs: Any):
        return await self.llm.ainvoke(messages, **kwargs)

    def stream(self, messages: List[BaseMessage], **kwargs: Any):
        return self.llm.stream(messages, **kwargs)

    def bind_tools(self, tools: List[Any], **kwargs: Any):
        return self.llm.bind_tools(tools, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self.llm, name)


class BaseLLMProvider:
    """
    High-level wrapper used by ARIA nodes.
    Handles system prompt injection, context, and JSON parsing.
    """

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        model_name:    str   = DEFAULT_MODEL,
        temperature:   float = DEFAULT_TEMP,
        max_tokens:    int   = DEFAULT_TOKENS,
    ):
        self.system_prompt = system_prompt
        self._llm = get_nvidia_llm(model_name, temperature, max_tokens)

    def _build_messages(
        self,
        user_message: str,
        context:     Optional[str]       = None,
        input_data:  Optional[Dict]      = None,
        image_paths: Optional[List[str]] = None,
    ) -> List[BaseMessage]:
        messages: List[BaseMessage] = []
        if self.system_prompt:
            messages.append(SystemMessage(content=self.system_prompt))
        prompt = user_message
        if context:
            prompt = f"# CONTEXT\n{context}\n\n{prompt}"
        if input_data:
            prompt += "\n\n# DATA (JSON):\n" + json.dumps(input_data, indent=2, ensure_ascii=False)
        if image_paths:
            content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
            for path in image_paths:
                content.append({"type": "image_url", "image_url": {"url": self._image_to_data_url(path)}})
            messages.append(HumanMessage(content=content))
        else:
            messages.append(HumanMessage(content=prompt))
        return messages

    @staticmethod
    def _image_to_data_url(image_path: str) -> str:
        """Encode a local image as a base64 data URL for a multimodal VLM."""
        mime_type, _ = mimetypes.guess_type(image_path)
        mime_type = mime_type or "image/jpeg"
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{b64}"

    @staticmethod
    def _clean_json(raw: str) -> str:
        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        return raw.strip()

    def invoke(self, user_message: str, context: Optional[str] = None,
               input_data: Optional[Dict] = None, reset_chat: bool = False,
               image_paths: Optional[List[str]] = None) -> str:
        resp = self._llm.invoke(self._build_messages(user_message, context, input_data, image_paths))
        content = getattr(resp, "content", None)
        # resp.content may be a list of blocks (e.g. [{"type": "text", "text": "..."}])
        # when the NVIDIA API returns a structured message — normalize to a clean str.
        if content is None:
            return str(resp)
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text", ""))
                else:
                    parts.append(str(block))
            return "".join(parts)
        if isinstance(content, str):
            return content
        # Fallback ultime
        return str(content)

    def invoke_for_json(self, user_message: str, context: Optional[str] = None,
                        input_data: Optional[Dict] = None,
                        image_paths: Optional[List[str]] = None) -> Optional[Dict]:
        raw = self.invoke(user_message, context, input_data, image_paths=image_paths)
        try:
            return json.loads(self._clean_json(raw))
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}\nRaw response:\n{raw[:300]}")
            return None

    async def ainvoke(self, user_message: str, context: Optional[str] = None,
                      input_data: Optional[Dict] = None,
                      image_paths: Optional[List[str]] = None) -> str:
        resp = await self._llm.ainvoke(self._build_messages(user_message, context, input_data, image_paths))
        content = getattr(resp, "content", None)
        if content is None:
            return str(resp)
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text", ""))
                else:
                    parts.append(str(block))
            return "".join(parts)
        if isinstance(content, str):
            return content
        return str(content)

    def stream(self, user_message: str, context: Optional[str] = None,
               input_data: Optional[Dict] = None) -> Iterator[str]:
        for chunk in self._llm.stream(self._build_messages(user_message, context, input_data)):
            content = getattr(chunk, "content", "")
            if content:
                yield content


if __name__ == "__main__":
    import asyncio
    import sys

    # Windows consoles default to cp1252, which cannot encode the accented text
    # and emoji used below; force UTF-8 so the self-test never crashes on Windows.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    print("=== ARIA LLM Provider — Quick test ===\n")

    llm = BaseLLMProvider(
        system_prompt="You are a concise assistant. Reply in one sentence maximum.",
        temperature=0.6,
        max_tokens=128,
    )

    # Test 1 — simple invoke
    print("[1] invoke():")
    print(llm.invoke("Say hello in English."))

    # Test 2 — invoke_for_json
    print("\n[2] invoke_for_json():")
    llm_json = BaseLLMProvider(
        system_prompt="Reply ONLY with valid JSON, no backticks or extra text.",
        temperature=0.2,
        max_tokens=128,
    )
    print(llm_json.invoke_for_json('Return {"name": "ARIA", "version": 1}'))

    print("\nTests complete.")