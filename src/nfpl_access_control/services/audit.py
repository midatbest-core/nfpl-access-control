"""Append-only audit recording used inside caller-owned transactions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from nfpl_access_control.authorization import AuthorizationDecision
from nfpl_access_control.models import AuditEvent, Job, User


def job_snapshot(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "reference": job.reference,
        "client_id": job.client_id,
        "branch_id": job.branch_id,
        "direction": job.direction.value,
        "mode": job.mode.value,
        "stage": job.stage.value,
        "goods_description": job.goods_description,
        "container_reference": job.container_reference,
        "checklist_data": job.checklist_data,
        "checklist_revision": job.checklist_revision,
        "prepared_by_user_id": job.prepared_by_user_id,
        "checked_by_user_id": job.checked_by_user_id,
        "filed_by_user_id": job.filed_by_user_id,
        "version": job.version,
    }


class AuditService:
    def __init__(self, session: Session):
        self.session = session

    def record(
        self,
        *,
        actor: User,
        action: str,
        reason: str,
        occurred_at: datetime,
        job: Job | None = None,
        before: dict[str, object] | None = None,
        after: dict[str, object] | None = None,
        decision: AuthorizationDecision | None = None,
        context: dict[str, object] | None = None,
    ) -> AuditEvent:
        authorization_context: dict[str, object] = dict(context or {})
        if decision is not None:
            authorization_context.update(
                {
                    "allowed": decision.allowed,
                    "reason_code": decision.reason_code.value,
                    "permission": decision.permission.value,
                    "explanation": decision.explanation,
                }
            )
        event = AuditEvent(
            job_id=job.id if job else None,
            actor_user_id=actor.id,
            action=action,
            occurred_at=occurred_at,
            reason=reason,
            before_state=before,
            after_state=after,
            authorization_context=authorization_context,
        )
        self.session.add(event)
        return event
