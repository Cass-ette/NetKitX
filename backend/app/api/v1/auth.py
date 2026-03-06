from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import authenticate_user, create_user, get_user_by_email, get_user_by_username

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
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token)
