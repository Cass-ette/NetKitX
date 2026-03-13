"""Embedding service: generate embeddings, vector search, RAG context formatting."""

import logging
from typing import Any

import httpx
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import async_session
from app.models.knowledge import KnowledgeEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

OPENAI_EMBEDDING_URL = "https://api.openai.com/v1/embeddings"
ZHIPUAI_EMBEDDING_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"


async def generate_embedding(text_input: str) -> list[float] | None:
    """Call embedding API (OpenAI or ZhipuAI). Returns None on failure."""
    provider = settings.RAG_EMBEDDING_PROVIDER
    api_key = settings.RAG_EMBEDDING_API_KEY
    model = settings.RAG_EMBEDDING_MODEL

    if not provider or not api_key:
        logger.debug("RAG embedding not configured, skipping")
        return None

    if settings.RAG_EMBEDDING_URL:
        url = settings.RAG_EMBEDDING_URL
    elif provider == "openai":
        url = OPENAI_EMBEDDING_URL
    elif provider == "zhipuai":
        url = ZHIPUAI_EMBEDDING_URL
    else:
        logger.warning("Unknown embedding provider: %s", provider)
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"input": text_input[:8000], "model": model},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
    except Exception:
        logger.exception("Failed to generate embedding")
        return None


# ---------------------------------------------------------------------------
# Text construction for embedding
# ---------------------------------------------------------------------------


def build_embedding_text(entry: KnowledgeEntry | dict[str, Any]) -> str:
    """Build a text representation of a knowledge entry for embedding.

    Accepts either a KnowledgeEntry ORM instance or a plain dict.
    """
    if isinstance(entry, dict):
        scenario = entry.get("scenario", "")
        summary = entry.get("summary", "")
        key_findings = entry.get("key_findings", "")
        target_type = entry.get("target_type", "")
        vuln_type = entry.get("vulnerability_type", "")
        tags = entry.get("tags") or []
        tools = entry.get("tools_used") or []
    else:
        scenario = entry.scenario or ""
        summary = entry.summary or ""
        key_findings = entry.key_findings or ""
        target_type = entry.target_type or ""
        vuln_type = entry.vulnerability_type or ""
        tags = entry.tags or []
        tools = entry.tools_used or []

    parts: list[str] = []
    if scenario:
        parts.append(f"Scenario: {scenario}")
    if summary:
        parts.append(f"Summary: {summary}")
    if key_findings:
        parts.append(f"Key findings: {key_findings}")
    if target_type:
        parts.append(f"Target type: {target_type}")
    if vuln_type:
        parts.append(f"Vulnerability: {vuln_type}")
    if tags and isinstance(tags, list):
        parts.append(f"Tags: {', '.join(str(t) for t in tags)}")
    if tools and isinstance(tools, list):
        parts.append(f"Tools: {', '.join(str(t) for t in tools)}")

    return "\n".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Embed a knowledge entry
# ---------------------------------------------------------------------------


async def embed_knowledge_entry(entry_id: int) -> bool:
    """Generate and store embedding for a knowledge entry. Returns True on success."""
    if not settings.RAG_ENABLED:
        return False

    async with async_session() as db:
        entry = (
            await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id))
        ).scalar_one_or_none()
        if not entry:
            logger.warning("Knowledge entry %d not found for embedding", entry_id)
            return False

        embed_text = build_embedding_text(entry)
        if not embed_text:
            logger.debug("Empty embedding text for entry %d, skipping", entry_id)
            return False

        embedding = await generate_embedding(embed_text)
        if embedding is None:
            return False

        # Use raw SQL to update the vector column
        await db.execute(
            text("UPDATE knowledge_entries SET embedding = :vec WHERE id = :id"),
            {"vec": str(embedding), "id": entry_id},
        )
        await db.commit()
        logger.info("Embedded knowledge entry %d", entry_id)
        return True


# ---------------------------------------------------------------------------
# Vector search
# ---------------------------------------------------------------------------


async def search_similar_knowledge(
    query: str,
    user_id: int,
    limit: int | None = None,
    threshold: float | None = None,
) -> list[tuple[KnowledgeEntry, float]]:
    """Search for similar knowledge entries using cosine similarity."""
    if not settings.RAG_ENABLED:
        return []

    limit = limit or settings.RAG_TOP_K
    threshold = threshold or settings.RAG_SIMILARITY_THRESHOLD

    query_embedding = await generate_embedding(query)
    if query_embedding is None:
        return []

    async with async_session() as db:
        # pgvector cosine distance: 1 - cosine_similarity
        # Lower distance = more similar. similarity = 1 - distance.
        sql = text(
            """
            SELECT id, 1 - (embedding <=> :query_vec::vector) AS similarity
            FROM knowledge_entries
            WHERE user_id = :uid
              AND embedding IS NOT NULL
              AND extraction_status = 'success'
            ORDER BY embedding <=> :query_vec::vector
            LIMIT :lim
            """
        )
        rows = (
            await db.execute(
                sql,
                {"query_vec": str(query_embedding), "uid": user_id, "lim": limit},
            )
        ).fetchall()

        results: list[tuple[KnowledgeEntry, float]] = []
        for row in rows:
            similarity = float(row.similarity)
            if similarity < threshold:
                continue
            entry = (
                await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.id == row.id))
            ).scalar_one_or_none()
            if entry:
                results.append((entry, similarity))

        return results


# ---------------------------------------------------------------------------
# RAG context formatting
# ---------------------------------------------------------------------------


def format_rag_context(
    results: list[tuple[Any, float]],
    lang: str = "en",
) -> str:
    """Format search results into a system prompt section."""
    if not results:
        return ""

    if lang.startswith("zh"):
        header = "## 相关历史经验\n以下是从知识库检索到的相关经验，仅供参考（目标环境可能不同）：\n"
        tpl_target = "目标类型"
        tpl_vuln = "漏洞"
        tpl_tools = "工具"
        tpl_findings = "关键发现"
        tpl_outcome = "结果"
        tpl_exp = "经验"
        tpl_sim = "相似度"
    else:
        header = (
            "## Related Historical Experience\n"
            "The following experiences were retrieved from the knowledge base "
            "for reference only (target environments may differ):\n"
        )
        tpl_target = "Target type"
        tpl_vuln = "Vulnerability"
        tpl_tools = "Tools"
        tpl_findings = "Key findings"
        tpl_outcome = "Outcome"
        tpl_exp = "Experience"
        tpl_sim = "Similarity"

    lines = [header]
    for idx, (entry, similarity) in enumerate(results, 1):
        scenario = getattr(entry, "scenario", "") or ""
        target_type = getattr(entry, "target_type", "") or ""
        vuln_type = getattr(entry, "vulnerability_type", "") or ""
        tools = getattr(entry, "tools_used", None) or []
        findings = getattr(entry, "key_findings", "") or ""
        outcome = getattr(entry, "outcome", "") or ""

        pct = f"{similarity * 100:.0f}%"
        lines.append(f"### {tpl_exp} {idx}: {scenario}（{tpl_sim}: {pct}）")
        lines.append(f"- {tpl_target}: {target_type} | {tpl_vuln}: {vuln_type}")
        if tools:
            tools_str = ", ".join(str(t) for t in tools) if isinstance(tools, list) else str(tools)
            lines.append(f"- {tpl_tools}: {tools_str}")
        if findings:
            lines.append(f"- {tpl_findings}: {findings}")
        lines.append(f"- {tpl_outcome}: {outcome}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience: search + format
# ---------------------------------------------------------------------------


async def search_and_format_knowledge(
    query: str,
    user_id: int,
    lang: str = "en",
) -> str:
    """Search similar knowledge and format as RAG context for system prompt."""
    results = await search_similar_knowledge(query, user_id)
    return format_rag_context(results, lang)
