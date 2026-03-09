import httpx
from datetime import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.core.terms import get_terms
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_username,
)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    existing = await get_user_by_username(session, body.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    existing_email = await get_user_by_email(session, body.email)
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = await create_user(session, body.username, body.email, body.password)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    user = await authenticate_user(session, body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(subject=user.username)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user's information."""
    return current_user


@router.get("/terms")
async def get_terms_content(lang: str = "en"):
    """Get terms of service content."""
    return get_terms(lang)


@router.post("/accept-terms", response_model=UserResponse)
async def accept_terms(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Accept terms of service."""
    current_user.terms_accepted_at = dt.utcnow()
    await session.commit()
    await session.refresh(current_user)
    return current_user


# ---------------------------------------------------------------------------
# GitHub OAuth
# ---------------------------------------------------------------------------

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


@router.get("/github")
async def github_login():
    """Redirect user to GitHub OAuth authorization page."""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")
    params = f"client_id={settings.GITHUB_CLIENT_ID}&scope=user:email"
    return RedirectResponse(f"{GITHUB_AUTH_URL}?{params}")


@router.get("/github/callback")
async def github_callback(code: str, session: AsyncSession = Depends(get_session)):
    """Handle GitHub OAuth callback: exchange code for token, get user info, login/register."""
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to get GitHub access token")

    # Get GitHub user info
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(GITHUB_USER_URL, headers=headers)
        gh_user = user_resp.json()

        # Get primary email (may be private)
        emails_resp = await client.get(GITHUB_EMAILS_URL, headers=headers)
        gh_emails = emails_resp.json()

    github_id = gh_user.get("id")
    username = gh_user.get("login", "")
    avatar_url = gh_user.get("avatar_url", "")

    # Find primary verified email
    email = ""
    if isinstance(gh_emails, list):
        for e in gh_emails:
            if e.get("primary") and e.get("verified"):
                email = e["email"]
                break
        if not email:
            for e in gh_emails:
                if e.get("verified"):
                    email = e["email"]
                    break
    if not email:
        email = gh_user.get("email") or f"{username}@github.local"

    # Find or create user
    result = await session.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()

    if not user:
        # Check if email already exists (link accounts)
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            # Link existing account to GitHub
            user.github_id = github_id
            user.avatar_url = avatar_url
            await session.commit()
        else:
            # Ensure unique username
            base_username = username
            suffix = 1
            while True:
                existing = await get_user_by_username(session, username)
                if not existing:
                    break
                username = f"{base_username}{suffix}"
                suffix += 1

            user = User(
                username=username,
                email=email,
                hashed_password="",
                github_id=github_id,
                avatar_url=avatar_url,
                role="admin"
                if (await session.execute(select(func.count(User.id)))).scalar() == 0
                else "user",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
    else:
        # Update avatar
        if avatar_url and user.avatar_url != avatar_url:
            user.avatar_url = avatar_url
            await session.commit()

    # Generate JWT and redirect to frontend with token
    jwt_token = create_access_token(subject=user.username)
    redirect_url = (
        f"{settings.ALLOWED_ORIGINS[0]}/auth/github?token={jwt_token}&username={user.username}"
    )
    return RedirectResponse(redirect_url)
