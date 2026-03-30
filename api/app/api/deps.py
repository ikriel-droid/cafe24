from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import OperatorRole, OperatorUser
from app.services.auth_service import get_operator_by_id, require_operator_role


def get_current_operator(request: Request, db: Session = Depends(get_db)) -> OperatorUser:
    operator_id = request.session.get("operator_user_id")
    if not isinstance(operator_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    operator = get_operator_by_id(db, operator_id)
    if operator is None or not operator.is_active:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return operator


def require_manager(operator: OperatorUser = Depends(get_current_operator)) -> OperatorUser:
    return require_operator_role(operator, OperatorRole.MANAGER)


def require_agent_or_manager(operator: OperatorUser = Depends(get_current_operator)) -> OperatorUser:
    return require_operator_role(operator, OperatorRole.MANAGER, OperatorRole.AGENT)
