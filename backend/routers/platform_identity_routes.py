"""
MODULE: Platform Identity Routes
PURPOSE: Tenant/user/membership administration endpoints for platform admins.
DOES: CRUD and status updates for identity-scoped platform resources.
DOES NOT: Handle API key, LLM routing, or audit export logic.
INVARIANTS: Endpoint paths and response models stay backward-compatible.
SAFE CHANGE: Keep side effects (audit writes) unchanged per operation.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.adapters.api.dependencies import AuthContext, require_platform_admin
from src.adapters.db.audit_recorder import record_admin_audit
from src.adapters.db.tenant_models import Tenant
from src.adapters.db.user_models import TenantMembership, User
from src.infra.database import get_session
from src.infra.security import hash_password

from .platform_schemas import (
    MembershipCreateRequest,
    MembershipResponse,
    MembershipStatusUpdateRequest,
    TenantCreateRequest,
    TenantResponse,
    TenantStatusUpdateRequest,
    UserCreateRequest,
    UserResponse,
    UserStatusUpdateRequest,
)

router = APIRouter()


@router.get("/tenants", response_model=List[TenantResponse])
def list_tenants(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    tenants = session.exec(select(Tenant).order_by(Tenant.created_at.desc())).all()
    return [
        TenantResponse(
            id=t.id,
            name=t.name,
            status=t.status,
            created_at=t.created_at,
        )
        for t in tenants
    ]


@router.post("/tenants", response_model=TenantResponse)
def create_tenant(
    payload: TenantCreateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant name is required")

    tenant = Tenant(name=name)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="tenant.create",
        target_type="tenant",
        target_id=str(tenant.id),
        tenant_id=tenant.id,
        metadata={"name": tenant.name, "status": tenant.status},
    )
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        status=tenant.status,
        created_at=tenant.created_at,
    )


@router.get("/users", response_model=List[UserResponse])
def list_users(
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    users = session.exec(select(User).order_by(User.created_at.desc())).all()
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            is_active=u.is_active,
            is_platform_admin=u.is_platform_admin,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse)
def create_user(
    payload: UserCreateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        is_platform_admin=payload.is_platform_admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="user.create",
        target_type="user",
        target_id=str(user.id),
        metadata={"email": user.email, "is_platform_admin": user.is_platform_admin},
    )
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_platform_admin=user.is_platform_admin,
        created_at=user.created_at,
    )


@router.post("/tenants/{tenant_id}/memberships", response_model=MembershipResponse)
def create_membership(
    tenant_id: int,
    payload: MembershipCreateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    user = session.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    membership = TenantMembership(
        user_id=payload.user_id,
        tenant_id=tenant_id,
        role=payload.role,
    )
    session.add(membership)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Membership already exists",
        ) from exc

    session.refresh(membership)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="membership.create",
        target_type="tenant_membership",
        target_id=str(membership.id),
        tenant_id=tenant_id,
        metadata={"user_id": membership.user_id, "role": membership.role},
    )
    return MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        is_active=membership.is_active,
    )


@router.get("/tenants/{tenant_id}/memberships", response_model=List[MembershipResponse])
def list_memberships(
    tenant_id: int,
    session: Session = Depends(get_session),
    _context: AuthContext = Depends(require_platform_admin),
):
    memberships = session.exec(select(TenantMembership).where(TenantMembership.tenant_id == tenant_id)).all()
    return [
        MembershipResponse(
            id=m.id,
            user_id=m.user_id,
            tenant_id=m.tenant_id,
            role=m.role,
            is_active=m.is_active,
        )
        for m in memberships
    ]


@router.patch("/tenants/{tenant_id}/status", response_model=TenantResponse)
def update_tenant_status(
    tenant_id: int,
    payload: TenantStatusUpdateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    tenant.status = payload.status
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="tenant.status.update",
        target_type="tenant",
        target_id=str(tenant.id),
        tenant_id=tenant.id,
        metadata={"status": tenant.status},
    )
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        status=tenant.status,
        created_at=tenant.created_at,
    )


@router.patch("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = payload.is_active
    session.add(user)
    session.commit()
    session.refresh(user)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="user.status.update",
        target_type="user",
        target_id=str(user.id),
        metadata={"is_active": user.is_active},
    )
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_platform_admin=user.is_platform_admin,
        created_at=user.created_at,
    )


@router.patch("/tenants/{tenant_id}/memberships/{membership_id}/status", response_model=MembershipResponse)
def update_membership_status(
    tenant_id: int,
    membership_id: int,
    payload: MembershipStatusUpdateRequest,
    session: Session = Depends(get_session),
    context: AuthContext = Depends(require_platform_admin),
):
    membership = session.exec(
        select(TenantMembership).where(
            TenantMembership.id == membership_id,
            TenantMembership.tenant_id == tenant_id,
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    membership.is_active = payload.is_active
    session.add(membership)
    session.commit()
    session.refresh(membership)
    record_admin_audit(
        session,
        actor_user_id=context.user.id,
        action="membership.status.update",
        target_type="tenant_membership",
        target_id=str(membership.id),
        tenant_id=tenant_id,
        metadata={"is_active": membership.is_active},
    )
    return MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        is_active=membership.is_active,
    )
