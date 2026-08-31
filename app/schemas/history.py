from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.vision import SkinFeatureScores


class HistoryEntry(BaseModel):
    """이력 목록의 개별 항목 (요약본)"""

    id: int
    created_at: datetime
    overall_score: int
    needs_dermatologist: bool

    class Config:
        from_attributes = True


class TrendInfo(BaseModel):
    """가장 최근 두 기록을 비교한 변화 추세"""

    previous_score: int
    latest_score: int
    score_delta: int = Field(..., description="latest_score - previous_score. 양수면 개선")
    coaching_message: str


class HistoryResponse(BaseModel):
    user_id: str
    entries: List[HistoryEntry]
    trend: Optional[TrendInfo] = None


class SeriesPoint(BaseModel):
    """시계열 분석용 단일 시점 데이터 (오래된 순 정렬)"""

    id: int
    created_at: datetime
    overall_score: int
    feature_scores: SkinFeatureScores
    skin_age: Optional[int] = None


class FeatureTrendSummary(BaseModel):
    """항목 하나의 전체 기간 변화 추세 (선형 회귀 기울기 기반)"""

    key: str
    label_ko: str
    first_score: int
    last_score: int
    delta: int = Field(..., description="last_score - first_score. 양수면 개선")
    direction: str = Field(..., description="'improving' | 'declining' | 'stable'")


class TrendSeriesResponse(BaseModel):
    """이력 전체를 시계열로 분석한 결과 (FR-09 확장: 2건 비교가 아닌 전체 기간 추세)"""

    user_id: str
    series: List[SeriesPoint]
    feature_trends: List[FeatureTrendSummary]
    overall_direction: str = Field(..., description="'improving' | 'declining' | 'stable'")
    summary_message: str


class TrendAnalysisResponse(BaseModel):
    """"이력분석" 버튼 클릭 시 제공하는 상세 리포트: 항목별 그래프용 시계열
    데이터 + AI가 생성한 관리 피드백. 그래프 데이터는 TrendSeriesResponse와
    동일하지만, ai_feedback은 Gemini를 호출해야 해서 비용이 들기 때문에
    /trend(자동 로드)와 분리된 별도 엔드포인트로 제공한다."""

    user_id: str
    series: List[SeriesPoint]
    feature_trends: List[FeatureTrendSummary]
    overall_direction: str
    ai_feedback: str = Field(..., description="변화 추세에 따른 AI 생성 관리 피드백")
    is_ai_generated: bool = Field(default=True, description="프론트에서 'AI 생성' 배지 표시용")