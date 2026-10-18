"""Database-filtered actionable employee work queues."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, case, func, or_, select, union_all
from sqlalchemy.orm import Session

from nfpl_access_control.authorization import AuthorizationEngine
from nfpl_access_control.models import (
    AccountStatus,
    Branch,
    Client,
    Job,
    JobDelegation,
    JobDirection,
    JobMode,
    JobResponsibility,
    JobStage,
    Permission,
    ResponsibilityType,
    User,
    UserKind,
)
from nfpl_access_control.services.absence import has_effective_absence


@dataclass(frozen=True, slots=True)
class WorkQueueItem:
    job_id: str
    reference: str
    client_id: str
    client_name: str
    branch_id: str
    branch_name: str
    direction: JobDirection
    mode: JobMode
    stage: JobStage
    responsibility: ResponsibilityType
    next_action: str
    feedback: str | None
    assigned_at: datetime
    priority: int
    version: int
    is_delegated: bool


class WorkQueueService:
    def __init__(self, session: Session):
        self.session = session

    def list(
        self,
        *,
        actor: User,
        limit: int = 50,
        cursor: str | None = None,
        search: str | None = None,
        now: datetime | None = None,
    ) -> list[WorkQueueItem]:
        items, _ = self.page(actor=actor, limit=limit, cursor=cursor, search=search, now=now)
        return items

    def page(
        self,
        *,
        actor: User,
        limit: int = 50,
        cursor: str | None = None,
        search: str | None = None,
        now: datetime | None = None,
    ) -> tuple[list[WorkQueueItem], str | None]:
        if not 1 <= limit <= 100:
            raise ValueError("Queue pagination is invalid.")
        current_time = now or datetime.now(UTC)
        if not self._active_staff(actor) or has_effective_absence(
            self.session, actor, current_time
        ):
            return [], None
        queue = self._union(actor, current_time).subquery()
        statement = (
            select(
                queue,
                Job.reference,
                Job.client_id,
                Job.branch_id,
                Job.direction,
                Job.mode,
                Job.stage,
                Job.last_return_reason,
                Job.version,
                Client.name,
                Branch.name.label("branch_name"),
            )
            .join(Job, Job.id == queue.c.job_id)
            .join(Client, Client.id == Job.client_id)
            .join(Branch, Branch.id == Job.branch_id)
        )
        normalized_search = search.strip() if search else ""
        if normalized_search:
            pattern = f"%{normalized_search}%"
            statement = statement.where(
                or_(
                    Job.id.ilike(pattern),
                    Job.reference.ilike(pattern),
                    Client.name.ilike(pattern),
                    Job.goods_description.ilike(pattern),
                )
            )
        if cursor is not None:
            priority, assigned_at, job_id = self._decode_cursor(cursor)
            statement = statement.where(
                or_(
                    queue.c.priority > priority,
                    and_(
                        queue.c.priority == priority,
                        queue.c.assigned_at > assigned_at,
                    ),
                    and_(
                        queue.c.priority == priority,
                        queue.c.assigned_at == assigned_at,
                        queue.c.job_id > job_id,
                    ),
                )
            )
        rows = self.session.execute(
            statement.order_by(queue.c.priority, queue.c.assigned_at, queue.c.job_id).limit(
                limit + 1
            )
        ).all()
        items = [
            WorkQueueItem(
                job_id=row.job_id,
                reference=row.reference,
                client_id=row.client_id,
                client_name=row.name,
                branch_id=row.branch_id,
                branch_name=row.branch_name,
                direction=row.direction,
                mode=row.mode,
                stage=row.stage,
                responsibility=ResponsibilityType(row.responsibility),
                next_action=row.next_action,
                feedback=row.last_return_reason,
                assigned_at=row.assigned_at,
                priority=row.priority,
                version=row.version,
                is_delegated=row.is_delegated,
            )
            for row in rows[:limit]
        ]
        next_cursor = self._encode_cursor(items[-1]) if len(rows) > limit and items else None
        return items, next_cursor

    def count(
        self,
        *,
        actor: User,
        search: str | None = None,
        now: datetime | None = None,
    ) -> int:
        current_time = now or datetime.now(UTC)
        if not self._active_staff(actor) or has_effective_absence(
            self.session, actor, current_time
        ):
            return 0
        queue = self._union(actor, current_time).subquery()
        statement = (
            select(func.count())
            .select_from(queue)
            .join(Job, Job.id == queue.c.job_id)
            .join(Client, Client.id == Job.client_id)
        )
        normalized_search = search.strip() if search else ""
        if normalized_search:
            pattern = f"%{normalized_search}%"
            statement = statement.where(
                or_(
                    Job.id.ilike(pattern),
                    Job.reference.ilike(pattern),
                    Client.name.ilike(pattern),
                    Job.goods_description.ilike(pattern),
                )
            )
        return int(self.session.scalar(statement) or 0)

    @staticmethod
    def _active_staff(actor: User) -> bool:
        return (
            actor.kind is UserKind.STAFF
            and actor.is_active
            and actor.account_status is AccountStatus.ACTIVE
        )

    @staticmethod
    def _encode_cursor(item: WorkQueueItem) -> str:
        value = f"{item.priority}|{item.assigned_at.isoformat()}|{item.job_id}"
        return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[int, datetime, str]:
        try:
            value = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
            priority_value, assigned_value, job_id = value.split("|", 2)
            priority = int(priority_value)
            assigned_at = datetime.fromisoformat(assigned_value)
            if assigned_at.tzinfo is None or assigned_at.utcoffset() is None or not job_id:
                raise ValueError
        except (ValueError, UnicodeDecodeError, binascii.Error) as error:
            raise ValueError("Queue cursor is invalid.") from error
        return priority, assigned_at, job_id

    def _union(self, actor: User, at: datetime):
        definitions = (
            (
                ResponsibilityType.FILING_OFFICER,
                Permission.JOB_FILE,
                (Job.stage == JobStage.CHECKED, Job.checked_by_user_id.is_not(None)),
                10,
                "File shipment or return for correction",
            ),
            (
                ResponsibilityType.CHECKER,
                Permission.JOB_CHECK,
                (
                    Job.stage == JobStage.PREPARED,
                    Job.prepared_by_user_id.is_not(None),
                    Job.prepared_by_user_id != actor.id,
                ),
                20,
                "Verify checklist",
            ),
            (
                ResponsibilityType.MAKER,
                Permission.JOB_PREPARE,
                (
                    Job.stage.in_((JobStage.CONFIRMED, JobStage.REOPENED)),
                    Job.maker_edit_locked.is_(False),
                ),
                30,
                "Prepare or correct shipment",
            ),
        )
        statements = []
        for responsibility, permission, stage_conditions, priority, action in definitions:
            direct_time = (
                select(JobResponsibility.assigned_at)
                .where(
                    JobResponsibility.job_id == Job.id,
                    JobResponsibility.responsibility == responsibility,
                    JobResponsibility.user_id == actor.id,
                )
                .correlate(Job)
                .scalar_subquery()
            )
            delegated_time = (
                select(func.min(JobDelegation.valid_from))
                .where(
                    JobDelegation.job_id == Job.id,
                    JobDelegation.responsibility == responsibility,
                    JobDelegation.delegate_user_id == actor.id,
                    JobDelegation.valid_from <= at,
                    JobDelegation.valid_until > at,
                    or_(JobDelegation.revoked_at.is_(None), JobDelegation.revoked_at > at),
                )
                .correlate(Job)
                .scalar_subquery()
            )
            responsible = or_(direct_time.is_not(None), delegated_time.is_not(None))
            statements.append(
                select(
                    Job.id.label("job_id"),
                    func.coalesce(direct_time, delegated_time).label("assigned_at"),
                    case((Job.id.is_not(None), priority)).label("priority"),
                    case((Job.id.is_not(None), responsibility.value)).label("responsibility"),
                    case((Job.id.is_not(None), action)).label("next_action"),
                    case((direct_time.is_(None), True), else_=False).label("is_delegated"),
                ).where(
                    Job.archived_at.is_(None),
                    *stage_conditions,
                    responsible,
                    AuthorizationEngine.job_scope_predicate(actor, permission, at=at),
                )
            )
        return union_all(*statements)
