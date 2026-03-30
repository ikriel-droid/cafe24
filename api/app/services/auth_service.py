from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import OperatorRole, OperatorUser


def authenticate_operator(session: Session, email: str, password: str) -> OperatorUser:
    normalized_email = email.strip().lower()
    operator = session.scalar(select(OperatorUser).where(OperatorUser.email == normalized_email))
    if operator is None or not operator.is_active or not verify_password(password, operator.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return operator


def get_operator_by_id(session: Session, operator_id: int) -> OperatorUser | None:
    return session.get(OperatorUser, operator_id)


def require_operator_role(operator: OperatorUser, *roles: OperatorRole) -> OperatorUser:
    if operator.role not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )
    return operator


def can_view_audit_logs(operator: OperatorUser) -> bool:
    return operator.role == OperatorRole.MANAGER
