"""Whitelist service: target extraction, matching, validation."""

import ipaddress
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.whitelist import AuthorizedTarget
from app.schemas.whitelist import WhitelistTargetCreate


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


async def add_target(
    session: AsyncSession, user_id: int, data: WhitelistTargetCreate
) -> AuthorizedTarget:
    """Add a new authorized target."""
    target = AuthorizedTarget(
        user_id=user_id,
        target_type=data.target_type,
        target_value=data.target_value.strip().lower(),
        declaration=data.declaration,
        notes=data.notes,
    )
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return target


async def remove_target(session: AsyncSession, user_id: int, target_id: int) -> bool:
    """Remove an authorized target."""
    result = await session.execute(
        select(AuthorizedTarget).where(
            AuthorizedTarget.id == target_id, AuthorizedTarget.user_id == user_id
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        return False
    await session.delete(target)
    await session.commit()
    return True


async def list_targets(session: AsyncSession, user_id: int) -> list[AuthorizedTarget]:
    """List all authorized targets for a user."""
    result = await session.execute(
        select(AuthorizedTarget)
        .where(AuthorizedTarget.user_id == user_id)
        .order_by(AuthorizedTarget.created_at.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Target extraction from plugin params
# ---------------------------------------------------------------------------


def extract_targets_from_params(params: dict) -> list[str]:
    """Extract all target values from plugin parameters.

    Covers all 14 built-in plugins:
    - port-scan, dir-scan, subdomain-enum, dns-query, whois-lookup, ssl-check, http-header, waf-detect, cms-detect, tech-stack, xss-scan, sql-inject, file-upload, api-fuzz
    """
    targets = []

    # URL-based params (extract hostname)
    for key in ["url", "trigger_url"]:
        if key in params and params[key]:
            parsed = urlparse(str(params[key]))
            if parsed.hostname:
                targets.append(parsed.hostname.lower())

    # Direct domain/host/target params
    for key in ["domain", "target", "host"]:
        if key in params and params[key]:
            targets.append(str(params[key]).strip().lower())

    return list(set(targets))  # deduplicate


# ---------------------------------------------------------------------------
# Target matching logic
# ---------------------------------------------------------------------------


def _is_subdomain(candidate: str, parent: str) -> bool:
    """Check if candidate is a subdomain of parent.

    Example: api.example.com is subdomain of example.com
    """
    if candidate == parent:
        return True
    return candidate.endswith(f".{parent}")


def _is_ip_in_cidr(ip_str: str, cidr_str: str) -> bool:
    """Check if IP is within CIDR range."""
    try:
        ip = ipaddress.ip_address(ip_str)
        network = ipaddress.ip_network(cidr_str, strict=False)
        return ip in network
    except ValueError:
        return False


async def is_target_authorized(session: AsyncSession, user_id: int, target: str) -> bool:
    """Check if a target is authorized for the user.

    Matching rules:
    - domain: exact match + subdomain match (example.com covers *.example.com)
    - ip: exact match
    - cidr: IP in network range
    """
    result = await session.execute(
        select(AuthorizedTarget).where(AuthorizedTarget.user_id == user_id)
    )
    authorized = result.scalars().all()

    target_lower = target.strip().lower()

    for auth in authorized:
        if auth.target_type == "domain":
            if _is_subdomain(target_lower, auth.target_value):
                return True
        elif auth.target_type == "ip":
            if target_lower == auth.target_value:
                return True
        elif auth.target_type == "cidr":
            # Check if target is an IP and within CIDR
            if _is_ip_in_cidr(target_lower, auth.target_value):
                return True

    return False


# ---------------------------------------------------------------------------
# Validation entry point
# ---------------------------------------------------------------------------


async def validate_targets(
    session: AsyncSession, user_id: int, is_admin: bool, params: dict
) -> tuple[bool, str | None]:
    """Validate that all targets in params are authorized.

    Returns: (is_valid, error_message)
    """
    # Admin bypass
    if is_admin:
        return True, None

    targets = extract_targets_from_params(params)
    if not targets:
        # No targets found — allow (e.g., utility plugins)
        return True, None

    unauthorized = []
    for target in targets:
        if not await is_target_authorized(session, user_id, target):
            unauthorized.append(target)

    if unauthorized:
        return False, f"Unauthorized targets: {', '.join(unauthorized)}"

    return True, None
