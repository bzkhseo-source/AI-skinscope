from typing import List
from pydantic import BaseModel, Field


class SuspectedPattern(BaseModel):
    """유사 증상 패턴 (진단이 아닌 참고용 안내)"""

    name: str = Field(..., description="패턴명 (예: 여드름, 지루피부염 등)")
    similarity: int = Field(..., ge=0, le=100, description="유사도 점수 0~100")
    note: str = Field(..., description="해당 패턴과 유사하다고 판단한 근거 설명")


class SkinFeatureScores(BaseModel):
    """한국인 피부상태 측정 데이터의 라벨 체계를 참고한 항목별 점수"""

    pore: int = Field(..., ge=0, le=100, description="모공 상태 점수")
    elasticity: int = Field(..., ge=0, le=100, description="탄력 점수")
    moisture: int = Field(..., ge=0, le=100, description="수분 점수")
    wrinkle: int = Field(..., ge=0, le=100, description="주름 점수")
    pigmentation: int = Field(..., ge=0, le=100, description="색소침착 점수")
    redness: int = Field(..., ge=0, le=100, description="붉은기/염증 점수")


class SkinAnalysisResult(BaseModel):
    """Gemini Vision 분석 결과 전체"""

    overall_score: int = Field(..., ge=0, le=100, description="종합 피부 건강 점수")
    feature_scores: SkinFeatureScores
    suspected_patterns: List[SuspectedPattern] = Field(default_factory=list)
    care_tips: List[str] = Field(default_factory=list, description="관리 루틴 코칭 메시지")
    needs_dermatologist: bool = Field(
        ..., description="심각도가 높아 전문의 상담을 권장해야 하는지 여부"
    )
    ai_summary: str = Field(..., description="AI가 생성한 종합 소견 (진단 아님 명시 포함)")