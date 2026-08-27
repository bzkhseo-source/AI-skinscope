import logging
from typing import Optional

from app.schemas.agent import AgentResult
from app.schemas.vision import SkinAnalysisResult
from app.services.ingredient_service import recommend_products
from app.services.kakao_service import search_nearby_dermatology_clinics
from app.services.vision_service import analyze_skin_image

logger = logging.getLogger(__name__)

# overall_score가 이 값 미만이면 Gemini가 needs_dermatologist=false를 냈더라도
# Agent가 자체 규칙으로 병원 방문 권장으로 상향 조정한다 (이중 안전장치).
OVERALL_SCORE_SAFETY_THRESHOLD = 40

DISCLAIMER = "본 결과는 AI 참고용 스크리닝이며 의료 진단이 아닙니다."


def _decide_needs_dermatologist(vision: SkinAnalysisResult) -> bool:
    """Gemini의 판단과 Agent의 규칙 기반 안전장치를 결합해 최종 결정한다."""
    if not vision.image_quality_ok:
        return False  # 사진 인식 실패 케이스는 병원 방문 권장 대상이 아님
    if vision.needs_dermatologist:
        return True
    if vision.overall_score < OVERALL_SCORE_SAFETY_THRESHOLD:
        return True
    return False


def _build_recommendation_message(vision: SkinAnalysisResult, needs_dermatologist: bool) -> str:
    if not vision.image_quality_ok:
        reason = vision.quality_note or "사진에서 피부 상태를 충분히 인식하지 못했습니다."
        return (
            f"{DISCLAIMER} {reason} 밝은 곳에서 얼굴/피부 부위가 선명하게 "
            "보이도록 다시 촬영해 주세요."
        )

    parts = [DISCLAIMER, vision.ai_summary]

    if needs_dermatologist:
        parts.append(
            "분석 결과 심각도가 다소 높게 나타나, 정확한 진단을 위해 "
            "가까운 피부과 방문을 권장드립니다. 아래 근처 병원 정보를 참고해주세요."
        )
    else:
        parts.append(
            "현재 상태는 비교적 양호하나, 증상이 지속되거나 악화될 경우 "
            "전문의 상담을 권장드립니다."
        )

    if vision.care_tips:
        tips = " / ".join(vision.care_tips)
        parts.append(f"관리 팁: {tips}")

    return " ".join(parts)


def run_skin_analysis_agent(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> AgentResult:
    """
    STEP 4의 Vision 분석 → Agent 판단 → (필요 시) 병원 검색 도구 호출까지
    이어지는 전체 파이프라인의 진입점.
    """
    vision_result = analyze_skin_image(image_bytes, mime_type=mime_type)
    needs_dermatologist = _decide_needs_dermatologist(vision_result)

    hospitals = []
    if needs_dermatologist and latitude is not None and longitude is not None:
        hospitals = search_nearby_dermatology_clinics(latitude, longitude)
    elif needs_dermatologist:
        logger.info("위치 정보가 없어 병원 검색 도구를 호출하지 않았습니다.")

    recommendation_message = _build_recommendation_message(vision_result, needs_dermatologist)
    product_recommendations = recommend_products(vision_result)

    return AgentResult(
        vision=vision_result,
        needs_dermatologist=needs_dermatologist,
        recommendation_message=recommendation_message,
        hospitals=hospitals,
        product_recommendations=product_recommendations,
    )