from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from src.infra.database import get_session
from src.adapters.db.user_models import User, TenantMembership
from src.adapters.db.tenant_models import Tenant
from src.adapters.api.dependencies import AuthContext, require_authenticated_user
from src.infra.security import verify_password, create_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> Any:
    """
    Standard OAuth2 compatible token login.
    """
    user = session.exec(select(User).where(User.email == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # For MVP, we'll just use the first active tenant membership if it exists
    # If the user is a platform admin, they might not have a specific tenant link
    # but the token payload expects tenant_id if we want to use tenant routes.
    
    tenant_id = None
    membership = session.exec(
        select(TenantMembership).where(TenantMembership.user_id == user.id, TenantMembership.is_active == True)
    ).first()
    
    if membership:
        tenant_id = membership.tenant_id

    access_token_expires = timedelta(minutes=60 * 24 * 7) # 1 week
    access_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": tenant_id},
        expires_delta=access_token_expires,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "tenant_id": tenant_id,
        "is_platform_admin": bool(user.is_platform_admin),
    }

@router.get("/me")
def get_me(context: AuthContext = Depends(require_authenticated_user)):
    return {
        "id": context.user.id,
        "email": context.user.email,
        "is_active": context.user.is_active,
        "is_platform_admin": bool(context.user.is_platform_admin),
        "tenant_id": context.tenant.id if context.tenant else None,
    }
