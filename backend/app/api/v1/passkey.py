"""Passkey authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.passkey import (
    PasskeyRegistrationBegin,
    PasskeyRegistrationComplete,
    PasskeyLoginBegin,
    PasskeyLoginComplete,
    PasskeyCredentialResponse,
)
from app.schemas.auth import TokenResponse
from app.services import passkey_service
from app.core.security import create_access_token

router = APIRouter()


@router.post("/register/begin")
async def begin_passkey_registration(
    request: PasskeyRegistrationBegin,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Begin passkey registration for the current user."""
    options = await passkey_service.begin_registration(session, current_user)
    return options


@router.post("/register/complete")
async def complete_passkey_registration(
    request: PasskeyRegistrationComplete,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Complete passkey registration."""
    try:
        credential = await passkey_service.complete_registration(
            session=session,
            user=current_user,
            credential_data=request.credential,
            challenge="",  # Challenge is retrieved from server-side storage
            name=request.name,
        )
        return PasskeyCredentialResponse.model_validate(credential)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to register passkey: {str(e)}",
        )


@router.post("/login/begin")
async def begin_passkey_login(
    request: PasskeyLoginBegin,
    session: AsyncSession = Depends(get_session),
):
    """Begin passkey authentication."""
    options = await passkey_service.begin_authentication(session)
    return options


@router.post("/login/complete", response_model=TokenResponse)
async def complete_passkey_login(
    request: PasskeyLoginComplete,
    session: AsyncSession = Depends(get_session),
):
    """Complete passkey authentication and return access token."""
    try:
        user = await passkey_service.complete_authentication(
            session=session,
            credential_data=request.credential,
            challenge="",  # Challenge is retrieved from server-side storage
        )

        access_token = create_access_token(data={"sub": user.username})
        return TokenResponse(access_token=access_token, token_type="bearer")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )


@router.get("/credentials", response_model=list[PasskeyCredentialResponse])
async def list_passkey_credentials(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all passkey credentials for the current user."""
    credentials = await passkey_service.list_credentials(session, current_user.id)
    return [PasskeyCredentialResponse.model_validate(c) for c in credentials]


@router.delete("/credentials/{credential_id}")
async def delete_passkey_credential(
    credential_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a passkey credential."""
    success = await passkey_service.delete_credential(session, current_user.id, credential_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )

    return {"message": "Credential deleted successfully"}
