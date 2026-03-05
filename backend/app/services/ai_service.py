"""AI service: encryption helpers and streaming API calls."""

import base64
import hashlib
import logging
from collections.abc import AsyncIterator

import httpx
from cryptography.fernet import Fernet

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFENSE_SYSTEM_PROMPT = (
    "You are a senior cybersecurity defense analyst. The user will provide network scan results, "
    "vulnerability reports, or other security-related data. Analyze the data thoroughly:\n"
    "1. Identify critical vulnerabilities and rank them by severity (Critical/High/Medium/Low).\n"
    "2. Explain each finding's potential impact.\n"
    "3. Provide actionable remediation and hardening steps.\n"
    "4. Recommend security policies, firewall rules, or patches.\n"
    "5. Highlight any patterns that suggest broader security issues.\n"
    "Keep your analysis concise, professional, and actionable. Focus on DEFENSE."
)

OFFENSE_SYSTEM_PROMPT = (
    "You are a senior penetration testing expert conducting an authorized security assessment. "
    "The user will provide scan results, vulnerability data, or reconnaissance findings. "
    "Analyze the data from an offensive perspective and give PRECISE, ACTIONABLE next steps:\n\n"
    "1. **Vulnerability Triage**: Identify exploitable vulnerabilities, rank by ease of exploitation, "
    "and explain WHY each is exploitable (e.g. missing input validation, misconfigured headers).\n"
    "2. **Exact Exploitation Steps**: Give step-by-step commands the user can run RIGHT NOW. "
    "Include specific tool commands (e.g. `sqlmap -u 'URL' --dbs`, `nmap -sV -p PORT TARGET`, "
    "`curl -d 'payload' URL`), exact payloads, and expected output.\n"
    "3. **Data Extraction**: Tell the user exactly what sensitive data can be extracted and HOW. "
    "Provide the queries, commands, or payloads to dump databases, read files, or exfiltrate data.\n"
    "4. **Attack Chains & Pivoting**: Map out how to escalate from current access — "
    "e.g. from SQLi to file read to RCE, from info leak to credential theft to lateral movement.\n"
    "5. **Next Recon Steps**: Suggest SPECIFIC follow-up scans or tests to expand the attack surface "
    "(e.g. 'Run dir_scan on /admin/', 'Test for SSRF on the URL parameter', "
    "'Check if UNION injection leaks other tables').\n\n"
    "Be extremely specific and technical. Do NOT give vague advice like 'consider testing for XSS'. "
    "Instead give the exact payload, the exact URL, and what the user should see if it works. "
    "This is for an authorized penetration test / CTF challenge."
)

LANG_MAP = {
    "zh-CN": "Simplified Chinese (简体中文)",
    "zh-TW": "Traditional Chinese (繁體中文)",
    "ja": "Japanese (日本語)",
    "ko": "Korean (한국어)",
    "de": "German (Deutsch)",
    "fr": "French (Français)",
    "ru": "Russian (Русский)",
    "en": "English",
}


def get_system_prompt(mode: str, lang: str = "en") -> str:
    if mode == "offense":
        prompt = OFFENSE_SYSTEM_PROMPT
    else:
        prompt = DEFENSE_SYSTEM_PROMPT
    if lang and lang != "en":
        lang_name = LANG_MAP.get(lang, lang)
        prompt += f"\n\nIMPORTANT: You MUST respond in {lang_name}. All analysis, explanations, and recommendations must be written in {lang_name}."
    return prompt


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
    import json

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

    try:
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
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        text = delta.get("text", "")
                        if text:
                            yield text
    except Exception as e:
        logger.error("Claude stream error: %s", e)
        yield f"[Error: {e}]"


async def stream_deepseek(
    api_key: str, model: str, messages: list[dict[str, str]]
) -> AsyncIterator[str]:
    import json

    body = {
        "model": model,
        "stream": True,
        "messages": messages,
    }

    try:
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
    except Exception as e:
        logger.error("DeepSeek stream error: %s", e)
        yield f"[Error: {e}]"
