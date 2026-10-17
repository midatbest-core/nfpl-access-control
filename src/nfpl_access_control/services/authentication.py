"""Employee password authentication and revocable bearer sessions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nfpl_access_control.core.security import (
    generate_api_token,
    hash_api_token,
    hash_password,
    verify_password,
)
from nfpl_access_control.models import (
    AccountStateEvent,
    AccountStatus,
    ApiCredential,
    Branch,
    PasswordCredential,
    User,
    UserKind,
)
from nfpl_access_control.services.audit import AuditService

SESSION_LIFETIME = timedelta(hours=8)
LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCKOUT = timedelta(minutes=15)
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-value-never-used")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthenticationError(ValueError):
    def __init__(self, message: str, *, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


class RegistrationConflictError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: User
    token: str
    expires_at: datetime


def _as_utc(value: datetime) -> datetime:
    """Normalize timestamps returned by SQLite without changing the instant."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def validate_password_strength(password: str) -> None:
    if not 12 <= len(password) <= 128:
        raise AuthenticationError(
            "Password must contain between 12 and 128 characters.", status_code=422
        )
    if not all((any(c.islower() for c in password), any(c.isupper() for c in password))):
        raise AuthenticationError(
            "Password must include upper- and lowercase letters.", status_code=422
        )
    if not any(c.isdigit() for c in password):
        raise AuthenticationError("Password must include a number.", status_code=422)


def authenticate_api_token(
    session: Session, token: str, *, now: datetime | None = None
) -> User | None:
    """Resolve an active actor from a bearer token, failing closed on bad state."""

    if not token:
        return None

    credential = session.scalar(
        select(ApiCredential)
        .join(ApiCredential.user)
        .where(
            ApiCredential.token_hash == hash_api_token(token),
            ApiCredential.revoked_at.is_(None),
            User.is_active.is_(True),
            User.account_status == AccountStatus.ACTIVE,
        )
    )
    if credential is None:
        return None

    current_time = now or datetime.now(UTC)
    if credential.expires_at is not None and _as_utc(credential.expires_at) <= current_time:
        return None

    return credential.user


class EmployeeAuthenticationService:
    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditService(session)

    def register(
        self,
        *,
        display_name: str,
        email: str,
        password: str,
        branch_id: str,
        now: datetime | None = None,
    ) -> User:
        current_time = now or datetime.now(UTC)
        normalized_email = normalize_email(email)
        validate_password_strength(password)
        if not EMAIL_PATTERN.fullmatch(normalized_email):
            raise AuthenticationError("A valid email address is required.", status_code=422)
        if not display_name.strip():
            raise AuthenticationError("Employee name is required.", status_code=422)
        if self.session.scalar(select(User.id).where(func.lower(User.email) == normalized_email)):
            raise RegistrationConflictError("An account with this email already exists.")
        branch = self.session.get(Branch, branch_id)
        if branch is None:
            raise AuthenticationError("The selected branch does not exist.", status_code=422)

        user = User(
            email=normalized_email,
            display_name=display_name.strip(),
            kind=UserKind.STAFF,
            branch_id=branch.id,
            account_status=AccountStatus.PENDING,
            is_active=False,
        )
        user.password_credential = PasswordCredential(password_hash=hash_password(password))
        self.session.add(user)
        self.session.flush()
        self.session.add(
            AccountStateEvent(
                user_id=user.id,
                previous_status=None,
                status=AccountStatus.PENDING,
                effective_at=current_time,
                actor_user_id=user.id,
                reason="Employee self-registration submitted for Admin review.",
            )
        )
        self.audit.record(
            actor=user,
            action="account.registered",
            reason="Employee registration submitted.",
            occurred_at=current_time,
            context={"employee_id": user.id, "branch_id": branch.id},
        )
        self.session.flush()
        return user

    def login(
        self,
        *,
        email: str,
        password: str,
        now: datetime | None = None,
    ) -> LoginResult:
        current_time = now or datetime.now(UTC)
        normalized_email = normalize_email(email)
        credential = self.session.scalar(
            select(PasswordCredential)
            .join(PasswordCredential.user)
            .where(func.lower(User.email) == normalized_email)
        )
        if credential is None:
            verify_password(password, _DUMMY_PASSWORD_HASH)
            raise AuthenticationError("Invalid email or password.")

        locked = (
            credential.locked_until is not None and _as_utc(credential.locked_until) > current_time
        )
        password_valid = verify_password(password, credential.password_hash)
        if locked or not password_valid:
            if not locked:
                credential.failed_attempts += 1
                if credential.failed_attempts >= LOGIN_FAILURE_LIMIT:
                    credential.locked_until = current_time + LOGIN_LOCKOUT
            self.audit.record(
                actor=credential.user,
                action="account.login_denied",
                reason="Invalid credentials or temporary login lockout.",
                occurred_at=current_time,
                context={"employee_id": credential.user_id},
                denied=True,
            )
            self.session.flush()
            raise AuthenticationError("Invalid email or password.")

        user = credential.user
        if not user.is_active or user.account_status is not AccountStatus.ACTIVE:
            self.audit.record(
                actor=user,
                action="account.login_denied",
                reason="The account is not active.",
                occurred_at=current_time,
                context={"employee_id": user.id, "account_status": user.account_status.value},
                denied=True,
            )
            self.session.flush()
            raise AuthenticationError("Account is not active.", status_code=403)

        credential.failed_attempts = 0
        credential.locked_until = None
        token = generate_api_token()
        expires_at = current_time + SESSION_LIFETIME
        session_credential = ApiCredential(
            user_id=user.id,
            name="employee login session",
            token_hash=hash_api_token(token),
            expires_at=expires_at,
        )
        self.session.add(session_credential)
        self.session.flush()
        self.audit.record(
            actor=user,
            action="account.login",
            reason="Employee authenticated.",
            occurred_at=current_time,
            context={"session_id": session_credential.id, "expires_at": expires_at.isoformat()},
        )
        self.session.flush()
        return LoginResult(user=user, token=token, expires_at=expires_at)

    def logout(self, *, actor: User, token: str, now: datetime | None = None) -> None:
        current_time = now or datetime.now(UTC)
        credential = self.session.scalar(
            select(ApiCredential).where(
                ApiCredential.user_id == actor.id,
                ApiCredential.token_hash == hash_api_token(token),
                ApiCredential.revoked_at.is_(None),
            )
        )
        if credential is None:
            raise AuthenticationError("Invalid or expired authentication credential.")
        credential.revoked_at = current_time
        self.audit.record(
            actor=actor,
            action="account.logout",
            reason="Employee session revoked.",
            occurred_at=current_time,
            context={"session_id": credential.id},
        )
        self.session.flush()
