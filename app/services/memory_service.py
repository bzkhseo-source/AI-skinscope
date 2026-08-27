import json
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.record import SkinRecord
from app.schemas.agent import AgentResult
from app.schemas.history import HistoryEntry, TrendInfo


def save_record(db: Session, user_id: str, agent_result: AgentResult) -> SkinRecord:
    record = SkinRecord(
        user_id=user_id,
        overall_score=agent_result.vision.overall_score,
        needs_dermatologist=agent_result.needs_dermatologist,
        result_json=agent_result.model_dump_json(),
        age=agent_result.age,
        gender=agent_result.gender,
        skin_age=agent_result.skin_age,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_history(db: Session, user_id: str, limit: int = 20) -> List[SkinRecord]:
    return (
        db.query(SkinRecord)
        .filter(SkinRecord.user_id == user_id)
        .order_by(SkinRecord.created_at.desc())
        .limit(limit)
        .all()
    )

def get_record(db: Session, user_id: str, record_id: int) -> Optional[SkinRecord]:
    return (
        db.query(SkinRecord)
        .filter(SkinRecord.user_id == user_id, SkinRecord.id == record_id)
        .first()
    )

def save_feedback(db: Session, user_id: str, record_id: int, rating: int, comment: Optional[str]) -> Optional[SkinRecord]:
    record = get_record(db, user_id, record_id)
    if record is None:
        return None
    record.satisfaction_rating = rating
    record.feedback_comment = comment
    db.commit()
    db.refresh(record)
    return record

def compute_trend(records: List[SkinRecord]) -> Optional[TrendInfo]:
    """가장 최근 두 기록(records[0]=최신, records[1]=이전)을 비교한다."""
    if len(records) < 2:
        return None

    latest, previous = records[0], records[1]
    delta = latest.overall_score - previous.overall_score

    if delta > 0:
        coaching_message = f"지난 기록보다 {delta}점 개선되었습니다. 좋은 관리 습관을 유지해보세요."
    elif delta < 0:
        coaching_message = f"지난 기록보다 {abs(delta)}점 낮아졌습니다. 최근 관리 루틴을 점검해보세요."
    else:
        coaching_message = "지난 기록과 점수가 동일합니다. 꾸준한 관리를 이어가보세요."

    return TrendInfo(
        previous_score=previous.overall_score,
        latest_score=latest.overall_score,
        score_delta=delta,
        coaching_message=coaching_message,
    )


def load_agent_result(record: SkinRecord) -> AgentResult:
    """저장된 JSON을 다시 AgentResult 객체로 복원한다 (상세 조회용)."""
    return AgentResult.model_validate(json.loads(record.result_json))