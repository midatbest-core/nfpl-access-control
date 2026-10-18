"""Database-backed, authorization-aware in-app notifications."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import AuthorizationEngine, Scope
from nfpl_access_control.authorization.roles import CLIENT_VIEWER_ROLE
from nfpl_access_control.models import (
    AccountStatus,
    Job,
    JobDelegation,
    JobResponsibility,
    Notification,
    Permission,
    ResponsibilityType,
    Role,
    RoleAssignment,
    RolePermission,
    User,
    UserKind,
)
from nfpl_access_control.services.audit import AuditService


class NotificationAccessError(PermissionError):
    pass


class NotificationValidationError(ValueError):
    pass


class NotificationService:
    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditService(session)

    def create(
        self,
        *,
        actor: User,
        recipient_user_id: str,
        event_type: str,
        message: str,
        target_path: str,
        dedupe_key: str,
        job: Job | None = None,
        is_client_safe: bool = False,
        now: datetime | None = None,
    ) -> Notification | None:
        current_time = now or datetime.now(UTC)
        existing = self.session.scalar(
            select(Notification).where(Notification.dedupe_key == dedupe_key)
        )
        if existing is not None:
            return existing
        recipient = self.session.get(User, recipient_user_id)
        if (
            recipient is None
            or not recipient.is_active
            or recipient.account_status is not AccountStatus.ACTIVE
        ):
            return None
        if not event_type.strip() or not message.strip() or not target_path.startswith("/v1/"):
            raise NotificationValidationError("Notification content or target is invalid.")
        notification = Notification(
            recipient_user_id=recipient.id,
            job_id=job.id if job else None,
            job_reference=job.reference if job else None,
            event_type=event_type.strip(),
            message=message.strip(),
            target_path=target_path,
            dedupe_key=dedupe_key,
            created_at=current_time,
            is_client_safe=is_client_safe,
        )
        self.session.add(notification)
        self.session.flush()
        self.audit.record(
            actor=actor,
            action="notification.created",
            reason="Actionable in-app notification created.",
            occurred_at=current_time,
            job=job,
            context={
                "notification_id": notification.id,
                "recipient_user_id": recipient.id,
                "event_type": notification.event_type,
                "dedupe_key": dedupe_key,
            },
        )
        self.session.flush()
        return notification

    def notify_responsibility(
        self,
        *,
        actor: User,
        job: Job,
        responsibility: ResponsibilityType,
        event_type: str,
        message: str,
        event_key: str,
        now: datetime,
    ) -> list[Notification]:
        recipient_ids = set(
            self.session.scalars(
                select(JobResponsibility.user_id).where(
                    JobResponsibility.job_id == job.id,
                    JobResponsibility.responsibility == responsibility,
                    JobResponsibility.user_id.is_not(None),
                )
            )
        )
        recipient_ids.update(
            self.session.scalars(
                select(JobDelegation.delegate_user_id).where(
                    JobDelegation.job_id == job.id,
                    JobDelegation.responsibility == responsibility,
                    JobDelegation.valid_from <= now,
                    JobDelegation.valid_until > now,
                    or_(JobDelegation.revoked_at.is_(None), JobDelegation.revoked_at > now),
                )
            )
        )
        notifications = [
            self.create(
                actor=actor,
                recipient_user_id=recipient_id,
                event_type=event_type,
                message=message,
                target_path=f"/v1/jobs/{job.id}",
                dedupe_key=f"{event_key}:{recipient_id}",
                job=job,
                now=now,
            )
            for recipient_id in sorted(recipient_ids)
            if recipient_id is not None
        ]
        return [item for item in notifications if item is not None]

    def notify_client_viewers(
        self,
        *,
        actor: User,
        job: Job,
        event_type: str,
        message: str,
        event_key: str,
        now: datetime,
    ) -> list[Notification]:
        recipients = self.session.scalars(
            select(User.id)
            .join(RoleAssignment, RoleAssignment.user_id == User.id)
            .join(Role, Role.id == RoleAssignment.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .where(
                User.kind == UserKind.CLIENT,
                User.is_active.is_(True),
                User.account_status == AccountStatus.ACTIVE,
                Role.slug == CLIENT_VIEWER_ROLE,
                RolePermission.permission == Permission.CLIENT_HISTORY_VIEW,
                RoleAssignment.valid_from <= now,
                or_(RoleAssignment.valid_until.is_(None), RoleAssignment.valid_until > now),
                or_(RoleAssignment.revoked_at.is_(None), RoleAssignment.revoked_at > now),
                or_(
                    RoleAssignment.all_clients.is_(True), RoleAssignment.client_id == job.client_id
                ),
                or_(
                    RoleAssignment.all_branches.is_(True), RoleAssignment.branch_id == job.branch_id
                ),
                or_(
                    RoleAssignment.all_directions.is_(True),
                    RoleAssignment.direction == job.direction,
                ),
                or_(RoleAssignment.all_modes.is_(True), RoleAssignment.mode == job.mode),
            )
            .distinct()
        )
        notifications = [
            self.create(
                actor=actor,
                recipient_user_id=recipient_id,
                event_type=event_type,
                message=message,
                target_path=f"/v1/client/jobs/{job.id}/status",
                dedupe_key=f"{event_key}:client:{recipient_id}",
                job=job,
                is_client_safe=True,
                now=now,
            )
            for recipient_id in recipients
        ]
        return [item for item in notifications if item is not None]

    def notify_admins(
        self,
        *,
        actor: User,
        job: Job,
        event_type: str,
        message: str,
        event_key: str,
        now: datetime,
    ) -> list[Notification]:
        engine = AuthorizationEngine(self.session)
        recipients = self.session.scalars(
            select(User).where(
                User.kind == UserKind.STAFF,
                User.account_status == AccountStatus.ACTIVE,
                User.is_active.is_(True),
            )
        )
        notifications = [
            self.create(
                actor=actor,
                recipient_user_id=recipient.id,
                event_type=event_type,
                message=message,
                target_path=f"/v1/jobs/{job.id}",
                dedupe_key=f"{event_key}:{recipient.id}",
                job=job,
                now=now,
            )
            for recipient in recipients
            if engine.authorize_admin(
                recipient,
                Permission.JOB_UPDATE,
                requested_scope=Scope.for_job(job),
                at=now,
            ).allowed
        ]
        return [item for item in notifications if item is not None]

    def notify_job_staff(
        self,
        *,
        actor: User,
        job: Job,
        message: str,
        event_key: str,
        now: datetime,
    ) -> list[Notification]:
        recipient_ids = set(
            self.session.scalars(
                select(JobResponsibility.user_id).where(
                    JobResponsibility.job_id == job.id,
                    JobResponsibility.user_id.is_not(None),
                )
            )
        )
        recipient_ids.update(
            self.session.scalars(
                select(JobDelegation.delegate_user_id).where(
                    JobDelegation.job_id == job.id,
                    JobDelegation.valid_from <= now,
                    JobDelegation.valid_until > now,
                    or_(JobDelegation.revoked_at.is_(None), JobDelegation.revoked_at > now),
                )
            )
        )
        notifications = [
            self.create(
                actor=actor,
                recipient_user_id=recipient_id,
                event_type="admin_attention",
                message=message,
                target_path=f"/v1/jobs/{job.id}",
                dedupe_key=f"{event_key}:{recipient_id}",
                job=job,
                now=now,
            )
            for recipient_id in sorted(recipient_ids)
            if recipient_id is not None and recipient_id != actor.id
        ]
        return [item for item in notifications if item is not None]

    def list_for_actor(
        self,
        *,
        actor: User,
        limit: int = 50,
        before: datetime | None = None,
        unread_only: bool = False,
        now: datetime | None = None,
    ) -> list[Notification]:
        if not 1 <= limit <= 100:
            raise NotificationValidationError("Notification limit must be between 1 and 100.")
        current_time = now or datetime.now(UTC)
        visible_job = AuthorizationEngine.job_scope_predicate(
            actor, Permission.JOB_VIEW, at=current_time
        )
        statement = (
            select(Notification)
            .outerjoin(Job, Job.id == Notification.job_id)
            .where(
                Notification.recipient_user_id == actor.id,
                or_(Notification.job_id.is_(None), and_(Job.id.is_not(None), visible_job)),
            )
        )
        if actor.kind is UserKind.CLIENT:
            statement = statement.where(Notification.is_client_safe.is_(True))
        if unread_only:
            statement = statement.where(Notification.read_at.is_(None))
        if before is not None:
            statement = statement.where(Notification.created_at < before)
        return list(
            self.session.scalars(
                statement.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(
                    limit
                )
            )
        )

    def unread_count(self, *, actor: User, now: datetime | None = None) -> int:
        current_time = now or datetime.now(UTC)
        visible_job = AuthorizationEngine.job_scope_predicate(
            actor, Permission.JOB_VIEW, at=current_time
        )
        statement = (
            select(func.count(Notification.id))
            .outerjoin(Job, Job.id == Notification.job_id)
            .where(
                Notification.recipient_user_id == actor.id,
                Notification.read_at.is_(None),
                or_(Notification.job_id.is_(None), and_(Job.id.is_not(None), visible_job)),
            )
        )
        if actor.kind is UserKind.CLIENT:
            statement = statement.where(Notification.is_client_safe.is_(True))
        return int(self.session.scalar(statement) or 0)

    def mark_all_read(self, *, actor: User, now: datetime | None = None) -> int:
        current_time = now or datetime.now(UTC)
        visible_job = AuthorizationEngine.job_scope_predicate(
            actor, Permission.JOB_VIEW, at=current_time
        )
        statement = (
            select(Notification.id)
            .outerjoin(Job, Job.id == Notification.job_id)
            .where(
                Notification.recipient_user_id == actor.id,
                Notification.read_at.is_(None),
                or_(Notification.job_id.is_(None), and_(Job.id.is_not(None), visible_job)),
            )
        )
        if actor.kind is UserKind.CLIENT:
            statement = statement.where(Notification.is_client_safe.is_(True))
        notification_ids = list(self.session.scalars(statement))
        if not notification_ids:
            return 0
        result = self.session.execute(
            update(Notification)
            .where(Notification.id.in_(notification_ids))
            .values(read_at=current_time)
        )
        return int(result.rowcount or 0)

    def mark_read(
        self, *, actor: User, notification_id: str, now: datetime | None = None
    ) -> Notification:
        current_time = now or datetime.now(UTC)
        notification = self.session.scalar(
            select(Notification)
            .where(
                Notification.id == notification_id,
                Notification.recipient_user_id == actor.id,
            )
            .with_for_update()
        )
        if notification is None:
            raise NotificationAccessError("Notification not found or not visible.")
        if notification.job_id is not None:
            job = self.session.get(Job, notification.job_id)
            if (
                job is None
                or not AuthorizationEngine(self.session)
                .authorize_job(actor, Permission.JOB_VIEW, job, at=current_time)
                .allowed
            ):
                raise NotificationAccessError("Notification not found or not visible.")
        if actor.kind is UserKind.CLIENT and not notification.is_client_safe:
            raise NotificationAccessError("Notification not found or not visible.")
        if notification.read_at is None:
            notification.read_at = current_time
        return notification
