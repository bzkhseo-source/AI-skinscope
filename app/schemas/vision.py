from typing import List, Optional
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


class RegionScore(BaseModel):
    """얼굴 한 부위(이마/코/볼/턱)에 대한 세부 점수. 모든 점수는 높을수록 양호함을 의미한다."""

    pore: int = Field(..., ge=0, le=100, description="이 부위의 모공 상태 점수")
    oiliness: int = Field(..., ge=0, le=100, description="이 부위의 유분/피지 상태 점수 (유분이 적을수록 높은 점수)")
    trouble: int = Field(
        ..., ge=0, le=100, description="이 부위의 트러블(여드름/뾰루지) 상태 점수 (트러블이 적을수록 높은 점수)"
    )
    note: str = Field(..., description="이 부위에 대한 한 줄 관찰 소견")


class RegionalScores(BaseModel):
    """얼굴을 이마/코(T존)/양볼/턱 5개 구역으로 나눈 세부 분석 결과"""

    forehead: RegionScore = Field(..., description="이마")
    nose: RegionScore = Field(
        ...,
        description=(
            "코(T존). 이 부위는 참고 데이터셋에 장비 실측치가 없으므로 "
            "사진에서 관찰되는 시각적 특징만으로 판단한다."
        ),
    )
    cheek_l: RegionScore = Field(..., description="왼쪽 볼 (사진 기준 왼쪽)")
    cheek_r: RegionScore = Field(..., description="오른쪽 볼 (사진 기준 오른쪽)")
    chin: RegionScore = Field(..., description="턱")


class ColorSwatch(BaseModel):
    """퍼스널컬러 추천/회피 색상 하나"""

    label_ko: str = Field(..., description="색상 이름 (예: '코랄 레드', '스카이 블루')")
    hex: str = Field(..., description="HEX 색상 코드 (예: '#RRGGBB')")
    category: str = Field(..., description="색상 용도 카테고리 (예: '립/블러셔', '의상', '헤어컬러')")


class PersonalColorResult(BaseModel):
    """퍼스널컬러(피부톤 어울리는 컬러) 참고용 진단 결과. 의료/건강 판단과 무관한 재미 요소."""

    undertone: str = Field(..., description="피부 언더톤: 'warm' | 'cool' | 'neutral'")
    season_label_ko: str = Field(
        ..., description="봄 웜톤 등 시즌 라벨 (확신이 낮으면 '웜톤'/'쿨톤'처럼 웜/쿨까지만)"
    )
    recommended_colors: List[ColorSwatch] = Field(default_factory=list)
    colors_to_avoid: List[ColorSwatch] = Field(default_factory=list)
    note: str = Field(
        ..., description="판단 근거 1문장 + 참고용 명시 ('사진 조명에 따라 오차가 있을 수 있는 참고용 결과')"
    )


class SkinAnalysisResult(BaseModel):
    """Gemini Vision 분석 결과 전체"""

    image_quality_ok: bool = Field(
        ...,
        description=(
            "사진에서 피부/얼굴 영역을 충분히 인식하여 분석했는지 여부. "
            "흐릿함, 과도한 어둠, 가림, 피부와 무관한 사진 등으로 분석이 "
            "어려운 경우 false로 설정한다."
        ),
    )
    quality_note: Optional[str] = Field(
        default=None,
        description="image_quality_ok가 false일 때, 어떤 문제인지 간단히 설명 (예: '얼굴이 인식되지 않았습니다').",
    )
    overall_score: int = Field(..., ge=0, le=100, description="종합 피부 건강 점수")
    feature_scores: SkinFeatureScores
    suspected_patterns: List[SuspectedPattern] = Field(default_factory=list)
    care_tips: List[str] = Field(default_factory=list, description="관리 루틴 코칭 메시지")
    needs_dermatologist: bool = Field(
        ..., description="심각도가 높아 전문의 상담을 권장해야 하는지 여부"
    )
    ai_summary: str = Field(..., description="AI가 생성한 종합 소견 (진단 아님 명시 포함)")
    ai_focus: Optional[str] = Field(
        default=None,
        description=(
            "구조화된 AI 소견 ①: 가장 우선적으로 관리해야 할 포인트를 한 줄로 "
            "요약 (예: '모공 관리에 가장 집중해보세요'). 면책 문구는 포함하지 않는다."
        ),
    )
    ai_detail: Optional[str] = Field(
        default=None,
        description=(
            "구조화된 AI 소견 ②: ai_focus로 판단한 시각적 근거를 1~2문장으로 "
            "설명 (예: '다른 항목에 비해 모공이 두드러지게 관찰됩니다')."
        ),
    )
    regional_scores: Optional[RegionalScores] = Field(
        default=None,
        description="이마/코(T존)/왼쪽볼/오른쪽볼/턱 5개 구역별 세부 분석 (모공/유분/트러블)",
    )
    personal_color: Optional[PersonalColorResult] = Field(
        default=None,
        description="퍼스널컬러 참고용 추천 (피부 건강 판단과 무관한 재미/참고 기능)",
    )