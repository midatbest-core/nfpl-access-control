"""FastAPI dependencies shared by protected routes."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from nfpl_access_control.db.session import get_db
from nfpl_access_control.models import User
from nfpl_access_control.services.authentication import authenticate_api_token

bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[Session, Depends(get_db)]


def get_current_actor(
    session: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Return the database-backed actor or a deliberately generic 401 response."""

    actor = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        actor = authenticate_api_token(session, credentials.credentials)
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credential",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return actor


CurrentActor = Annotated[User, Depends(get_current_actor)]
