from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.models.database import Base


class SkinRecord(Base):
    """사용자별 피부 분석 결과 이력 (FR-08, FR-09 Long-term Memory)"""

    __tablename__ = "skin_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    overall_score = Column(Integer, nullable=False)
    needs_dermatologist = Column(Boolean, nullable=False)

    # AgentResult 전체를 JSON 문자열로 저장 (프로토타입 단계의 단순화된 저장 방식)
    result_json = Column(Text, nullable=False)

    # FR-10: 사용자 피드백 (분석 직후 선택적으로 제출)
    satisfaction_rating = Column(Integer, nullable=True)
    feedback_comment = Column(Text, nullable=True)