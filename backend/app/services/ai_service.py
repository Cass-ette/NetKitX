"""AI service: encryption helpers and streaming API calls."""

import base64
import hashlib
import logging
from collections.abc import AsyncIterator

import httpx
from cryptography.fernet import Fernet

from app.core.config import settings

logger = logging.getLogger(__name__)

SECURITY_SYSTEM_PROMPT = (
    "You are a senior cybersecurity analyst. The user will provide network scan results, "
    "vulnerability reports, or other security-related data. Analyze the data thoroughly:\n"
    "1. Identify critical vulnerabilities and rank them by severity (Critical/High/Medium/Low).\n"
    "2. Explain each finding's potential impact and attack vectors.\n"
    "3. Provide actionable remediation steps.\n"
    "4. Highlight any patterns that suggest broader security issues.\n"
    "Keep your analysis concise, professional, and actionable."
)


def _derive_fernet_key() -> bytes:
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_key(plaintext: str) -> str:
    f = Fernet(_derive_fernet_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_key(ciphertext: str) -> str:
    f = Fernet(_derive_fernet_key())
    return f.decrypt(ciphertext.encode()).decode()


def mask_key(plaintext: str) -> str:
    if len(plaintext) <= 8:
        return "****"
    return plaintext[:3] + "..." + plaintext[-4:]


async def stream_claude(
    api_key: str, model: str, messages: list[dict[str, str]]
) -> AsyncIterator[str]:
    system_msg = None
    chat_messages = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        else:
            chat_messages.append(m)

    body: dict = {
        "model": model,
        "max_tokens": 4096,
        "stream": True,
        "messages": chat_messages,
    }
    if system_msg:
        body["system"] = system_msg

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
        ) as resp:
            if resp.status_code != 200:
                error_body = await resp.aread()
                logger.error("Claude API error %s: %s", resp.status_code, error_body[:500])
                yield f"[API Error {resp.status_code}]"
                return
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                import json

                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        yield text


async def stream_deepseek(
    api_key: str, model: str, messages: list[dict[str, str]]
) -> AsyncIterator[str]:
    body = {
        "model": model,
        "stream": True,
        "messages": messages,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        ) as resp:
            if resp.status_code != 200:
                error_body = await resp.aread()
                logger.error("DeepSeek API error %s: %s", resp.status_code, error_body[:500])
                yield f"[API Error {resp.status_code}]"
                return
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                import json

                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = event.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        yield text
