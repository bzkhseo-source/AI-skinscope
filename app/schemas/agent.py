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


class AgentResult(BaseModel):
    """AI Agent가 최종적으로 사용자에게 반환하는 결과"""

    vision: SkinAnalysisResult
    needs_dermatologist: bool = Field(..., description="Agent가 최종 판단한 병원 방문 권장 여부")
    recommendation_message: str = Field(..., description="Agent가 생성한 종합 안내 메시지")
    hospitals: List[HospitalInfo] = Field(
        default_factory=list, description="심각도가 높을 때만 채워지는 근처 피부과 목록"
    )