from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.vision import SkinAnalysisResult


class HospitalInfo(BaseModel):
    """카카오맵 검색으로 찾은 병원 정보"""

    name: str = Field(..., description="병원명")
    address: str = Field(..., description="지번 또는 도로명 주소")
    phone: str = Field(default="", description="전화번호 (정보 없으면 빈 문자열)")
    distance_m: Optional[int] = Field(default=None, description="검색 기준점으로부터 거리(m)")
    place_url: str = Field(default="", description="카카오맵 상세 페이지 URL")


class IngredientRecommendation(BaseModel):
    """AI Hub 스킨케어 성분-효능 추천 데이터 전수분석 결과에서 뽑은 성분 추천 항목"""

    inci_name: str = Field(..., description="성분의 INCI(국제화장품원료) 명칭")
    name_ko: str = Field(..., description="성분 한글명")
    efficacy: Optional[str] = Field(default=None, description="성분 효능 설명")
    search_url: str = Field(
        ..., description="실시간 커머스 연동 대신 제공하는 성분 관련 검색 링크"
    )


class ConcernProductRecommendation(BaseModel):
    """하나의 피부 고민 카테고리에 대한 추천 성분 묶음"""

    concern_key: str = Field(..., description="고민 카테고리 영문 키 (예: pore, wrinkle)")
    concern_label_ko: str = Field(..., description="고민 카테고리 한글 표시명")
    ingredients: List[IngredientRecommendation] = Field(default_factory=list)


class AgentResult(BaseModel):
    """AI Agent가 최종적으로 사용자에게 반환하는 결과"""

    record_id: Optional[int] = Field(
        default=None, description="저장된 기록의 ID (피드백 제출 시 사용)"
    )
    vision: SkinAnalysisResult
    needs_dermatologist: bool = Field(..., description="Agent가 최종 판단한 병원 방문 권장 여부")
    recommendation_message: str = Field(..., description="Agent가 생성한 종합 안내 메시지")
    hospitals: List[HospitalInfo] = Field(
        default_factory=list, description="심각도가 높을 때만 채워지는 근처 피부과 목록"
    )
    product_recommendations: List[ConcernProductRecommendation] = Field(
        default_factory=list,
        description="가장 관리가 필요한 고민 항목 기준으로 뽑은 성분 추천 (검색 링크 포함)",
    )
    age: Optional[int] = Field(default=None, description="사용자가 입력한 나이 (선택 입력)")
    gender: Optional[str] = Field(
        default=None, description="사용자가 입력한 성별 ('female'/'male', 선택 입력)"
    )
    skin_age: Optional[int] = Field(
        default=None,
        description="feature_scores와 가장 가까운 연령대 그룹을 기준으로 산출한 피부나이",
    )
    peer_comparison_note: Optional[str] = Field(
        default=None,
        description="나이를 입력한 경우, 동일 연령대(·성별) 그룹과 비교한 한 줄 코멘트",
    )