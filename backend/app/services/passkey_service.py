"""Passkey authentication service using WebAuthn."""

import base64
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier

from app.core.config import settings
from app.models.passkey import PasskeyCredential
from app.models.user import User


# Temporary in-memory challenge storage (use Redis in production)
_challenge_store: dict[int, bytes] = {}
_auth_challenge: bytes | None = None  # For authentication (no user ID yet)


# WebAuthn configuration
RP_ID = settings.DOMAIN or "localhost"
RP_NAME = "NetKitX"
ORIGIN = f"https://{RP_ID}" if settings.DOMAIN else "http://localhost:3000"


async def begin_registration(
    session: AsyncSession,
    user: User,
) -> dict:
    """Generate registration options for a new passkey."""
    # Get existing credentials to exclude
    result = await session.execute(
        select(PasskeyCredential).where(PasskeyCredential.user_id == user.id)
    )
    existing_creds = result.scalars().all()

    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=cred.credential_id) for cred in existing_creds
    ]

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=str(user.id).encode(),
        user_name=user.username,
        user_display_name=user.username,
        exclude_credentials=exclude_credentials,
        authenticator_selection={
            "resident_key": "preferred",
            "user_verification": UserVerificationRequirement.PREFERRED,
        },
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )

    # Store challenge for this user
    _challenge_store[user.id] = options.challenge

    # Store challenge in session (in production, use Redis or similar)
    # For now, we'll return it and expect it back
    return json.loads(options_to_json(options))


async def complete_registration(
    session: AsyncSession,
    user: User,
    credential_data: dict,
    challenge: str,
    name: str | None = None,
) -> PasskeyCredential:
    """Verify and store a new passkey credential."""
    # Retrieve stored challenge
    expected_challenge = _challenge_store.pop(user.id, None)
    if not expected_challenge:
        raise ValueError("No challenge found for this user")

    verification = verify_registration_response(
        credential=credential_data,
        expected_challenge=expected_challenge,
        expected_origin=ORIGIN,
        expected_rp_id=RP_ID,
    )

    # Create credential record
    credential = PasskeyCredential(
        user_id=user.id,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=credential_data.get("response", {}).get("transports"),
        name=name,
    )

    session.add(credential)
    await session.commit()
    await session.refresh(credential)

    return credential


async def begin_authentication(
    session: AsyncSession,
) -> dict:
    """Generate authentication options for passkey login."""
    global _auth_challenge

    # Get all credentials (we don't know which user yet)
    # In production, you might want to limit this or use resident keys
    result = await session.execute(select(PasskeyCredential))
    all_creds = result.scalars().all()

    allow_credentials = [
        PublicKeyCredentialDescriptor(
            id=cred.credential_id,
            transports=cred.transports or [],
        )
        for cred in all_creds
    ]

    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=allow_credentials if allow_credentials else None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    # Store challenge globally (since we don't know the user yet)
    _auth_challenge = options.challenge

    return json.loads(options_to_json(options))


async def complete_authentication(
    session: AsyncSession,
    credential_data: dict,
    challenge: str,
) -> User:
    """Verify passkey assertion and return authenticated user."""
    global _auth_challenge

    if not _auth_challenge:
        raise ValueError("No authentication challenge found")

    # Extract credential ID from response
    credential_id = base64.urlsafe_b64decode(credential_data["id"])

    # Find the credential
    result = await session.execute(
        select(PasskeyCredential).where(PasskeyCredential.credential_id == credential_id)
    )
    credential = result.scalar_one_or_none()

    if not credential:
        raise ValueError("Credential not found")

    # Verify the assertion
    verification = verify_authentication_response(
        credential=credential_data,
        expected_challenge=_auth_challenge,
        expected_origin=ORIGIN,
        expected_rp_id=RP_ID,
        credential_public_key=credential.public_key,
        credential_current_sign_count=credential.sign_count,
    )

    # Clear the challenge
    _auth_challenge = None

    # Update sign count and last used
    credential.sign_count = verification.new_sign_count
    credential.last_used_at = datetime.utcnow()
    await session.commit()

    # Get and return the user
    result = await session.execute(select(User).where(User.id == credential.user_id))
    user = result.scalar_one()

    return user


async def list_credentials(
    session: AsyncSession,
    user_id: int,
) -> list[PasskeyCredential]:
    """List all passkey credentials for a user."""
    result = await session.execute(
        select(PasskeyCredential)
        .where(PasskeyCredential.user_id == user_id)
        .order_by(PasskeyCredential.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_credential(
    session: AsyncSession,
    user_id: int,
    credential_id: int,
) -> bool:
    """Delete a passkey credential."""
    result = await session.execute(
        select(PasskeyCredential).where(
            PasskeyCredential.id == credential_id,
            PasskeyCredential.user_id == user_id,
        )
    )
    credential = result.scalar_one_or_none()

    if not credential:
        return False

    await session.delete(credential)
    await session.commit()
    return True
