import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.share_link import ShareLink
from app.schemas.share import SharedResultView
from app.services.memory_service import get_record, load_agent_result


def create_share_link(db: Session, user_id: str, record_id: int) -> Optional[ShareLink]:
    """본인 소유 기록에 한해 추측 불가능한 토큰의 공유 링크를 발급한다.

    같은 기록에 대해 매번 새 토큰을 발급한다(단순함 우선 — 이전에 발급한
    링크가 남아있어도 별 문제가 없고, 별도로 무효화할 필요도 없다).
    """
    record = get_record(db, user_id, record_id)
    if record is None:
        return None

    link = ShareLink(
        token=secrets.token_urlsafe(24),
        record_id=record_id,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.share_link_expiry_days),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def get_shared_result(db: Session, token: str) -> Optional[SharedResultView]:
    """유효한(만료되지 않은) 토큰이면 공유용으로 축약된 결과를 반환한다."""
    link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if link is None:
        return None

    expires_at = link.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None

    record = get_record(db, link.user_id, link.record_id)
    if record is None:
        return None

    agent_result = load_agent_result(record)
    vision = agent_result.vision

    return SharedResultView(
        overall_score=vision.overall_score,
        needs_dermatologist=agent_result.needs_dermatologist,
        feature_scores=vision.feature_scores,
        ai_focus=vision.ai_focus,
        ai_detail=vision.ai_detail,
        ai_summary=vision.ai_summary,
        care_tips=vision.care_tips,
        created_at=record.created_at,
    )
