"""Audited client queries and Admin attention messages for shipment work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import AuthorizationDecision, AuthorizationEngine, Scope
from nfpl_access_control.models import AuditEvent, Job, Permission, User, UserKind
from nfpl_access_control.services.audit import AuditService
from nfpl_access_control.services.notifications import NotificationService


class AttentionAccessError(PermissionError):
    def __init__(self, decision: AuthorizationDecision):
        super().__init__(decision.explanation)
        self.decision = decision


class AttentionValidationError(ValueError):
    pass


class AttentionConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AttentionReceipt:
    audit_event_id: str
    delivered: int


class AttentionService:
    def __init__(self, session: Session):
        self.session = session
        self.authorization = AuthorizationEngine(session)
        self.audit = AuditService(session)
        self.notifications = NotificationService(session)

    def client_query(
        self,
        *,
        actor: User,
        job: Job,
        category: str,
        explanation: str,
        now: datetime | None = None,
    ) -> AttentionReceipt:
        current_time = now or datetime.now(UTC)
        decision = self.authorization.authorize_job(
            actor, Permission.CLIENT_HISTORY_VIEW, job, at=current_time
        )
        if actor.kind is not UserKind.CLIENT or not decision.allowed:
            self.audit.record(
                actor=actor,
                action="client.query_denied",
                reason=decision.explanation,
                occurred_at=current_time,
                job=job,
                decision=decision,
                denied=True,
            )
            self.session.flush()
            raise AttentionAccessError(decision)
        normalized_category = category.strip().lower()
        if normalized_category not in {
            "delay",
            "cancellation",
            "reopening",
            "missing_update",
            "other",
        }:
            raise AttentionValidationError("Select a supported query category.")
        reason = explanation.strip()
        if not reason:
            raise AttentionValidationError("A query explanation is required.")
        if len(reason) > 1000:
            raise AttentionValidationError("The query explanation is too long.")
        self._prevent_duplicate(
            actor=actor,
            job=job,
            action="client.query_raised",
            reason=reason,
            category=normalized_category,
        )
        event = self.audit.record(
            actor=actor,
            action="client.query_raised",
            reason=reason,
            occurred_at=current_time,
            job=job,
            decision=decision,
            context={"category": normalized_category},
        )
        self.session.flush()
        label = normalized_category.replace("_", " ")
        notifications = self.notifications.notify_admins(
            actor=actor,
            job=job,
            event_type="client_query",
            message=f"Client query about {label}: {reason}"[:500],
            event_key=f"client-query:{event.id}",
            now=current_time,
        )
        return AttentionReceipt(event.id, len(notifications))

    def admin_attention(
        self,
        *,
        actor: User,
        job: Job,
        explanation: str,
        now: datetime | None = None,
    ) -> AttentionReceipt:
        current_time = now or datetime.now(UTC)
        decision = self.authorization.authorize_admin(
            actor,
            Permission.JOB_UPDATE,
            requested_scope=Scope.for_job(job),
            at=current_time,
        )
        if not decision.allowed:
            self.audit.record(
                actor=actor,
                action="admin.attention_denied",
                reason=decision.explanation,
                occurred_at=current_time,
                job=job,
                decision=decision,
                denied=True,
            )
            self.session.flush()
            raise AttentionAccessError(decision)
        reason = explanation.strip()
        if not reason:
            raise AttentionValidationError("An attention explanation is required.")
        if len(reason) > 1000:
            raise AttentionValidationError("The attention explanation is too long.")
        self._prevent_duplicate(
            actor=actor,
            job=job,
            action="admin.attention_sent",
            reason=reason,
        )
        event = self.audit.record(
            actor=actor,
            action="admin.attention_sent",
            reason=reason,
            occurred_at=current_time,
            job=job,
            decision=decision,
        )
        self.session.flush()
        notifications = self.notifications.notify_job_staff(
            actor=actor,
            job=job,
            message=f"Admin attention requested: {reason}"[:500],
            event_key=f"admin-attention:{event.id}",
            now=current_time,
        )
        return AttentionReceipt(event.id, len(notifications))

    def _prevent_duplicate(
        self,
        *,
        actor: User,
        job: Job,
        action: str,
        reason: str,
        category: str | None = None,
    ) -> None:
        recent = self.session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.job_id == job.id,
                AuditEvent.actor_user_id == actor.id,
                AuditEvent.action == action,
                AuditEvent.affected_job_version == job.version,
            )
            .order_by(AuditEvent.occurred_at.desc())
            .limit(20)
        )
        for event in recent:
            same_category = (
                category is None or event.authorization_context.get("category") == category
            )
            if event.reason == reason and same_category:
                raise AttentionConflictError(
                    "An identical message was already sent for this shipment version."
                )
