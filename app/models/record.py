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

    # 로드맵 G: 나이/성별 입력(선택) + 산출된 피부나이. 목록 화면에서 굳이
    # result_json을 파싱하지 않고도 바로 조회할 수 있도록 컬럼으로도 둔다.
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)
    skin_age = Column(Integer, nullable=True)

    # FR-10: 사용자 피드백 (분석 직후 선택적으로 제출)
    satisfaction_rating = Column(Integer, nullable=True)
    feedback_comment = Column(Text, nullable=True)