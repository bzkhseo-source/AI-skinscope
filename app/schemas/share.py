from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.vision import SkinFeatureScores


class ShareCreateRequest(BaseModel):
    user_id: str = Field(..., description="기록 소유자 확인용 사용자 식별자")


class ShareLinkResponse(BaseModel):
    token: str = Field(..., description="공유 링크에 쓰이는 추측 불가능한 토큰")
    expires_at: datetime = Field(..., description="이 시각 이후로는 링크가 만료되어 조회 불가")


class SharedResultView(BaseModel):
    """공유 링크로 접근했을 때 보여주는 결과 요약 (핵심 정보만, 개인정보/사진 제외)"""

    overall_score: int
    needs_dermatologist: bool
    feature_scores: SkinFeatureScores
    ai_focus: Optional[str] = None
    ai_detail: Optional[str] = None
    ai_summary: str
    care_tips: List[str] = Field(default_factory=list)
    created_at: datetime
