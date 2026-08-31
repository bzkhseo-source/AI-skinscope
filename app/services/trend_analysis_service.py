import logging
from typing import Optional

from google import genai
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.history import TrendAnalysisResponse
from app.services.memory_service import build_trend_series

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = "지금은 관리 피드백을 만들기 어려워요, 잠시 후 다시 시도해주세요."

SYSTEM_PROMPT_TEMPLATE = """당신은 피부 관리를 참고용으로 코칭하는 AI 어시스턴트다. 아래는 한 사용자의
최근 피부 분석 이력 시계열을 항목별로 분석한 요약이다. 이 추세를 근거로,
악화되고 있는 항목은 구체적인 관리 방법을 조언하고, 개선되고 있는 항목은
그 이유를 추정해 짧게 칭찬하며 유지 방법을 알려줘라.

지침:
- 근거에 없는 내용(특정 질병 원인 단정 등)은 추측하지 마라.
- 참고용 정보이며 의료 진단이 아님을 자연스럽게 포함하라.
- 4~6문장 이내로 간결하게 작성하라.

[전체 요약]
{summary_message}

[항목별 변화 (첫 기록 → 최근 기록, 방향)]
{feature_trends_text}
"""


def _build_feature_trends_text(feature_trends) -> str:
    lines = []
    direction_ko = {"improving": "개선", "declining": "악화", "stable": "유지"}
    for t in feature_trends:
        lines.append(
            f"- {t.label_ko}: {t.first_score} → {t.last_score} "
            f"({direction_ko.get(t.direction, t.direction)})"
        )
    return "\n".join(lines)


def _generate_ai_feedback(summary_message: str, feature_trends) -> str:
    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        summary_message=summary_message,
        feature_trends_text=_build_feature_trends_text(feature_trends),
    )

    for model in (settings.gemini_primary_model, settings.gemini_fallback_model):
        try:
            response = client.models.generate_content(model=model, contents=[prompt])
            answer = (response.text or "").strip()
            if answer:
                return answer
        except Exception as exc:  # noqa: BLE001
            logger.warning("이력 분석 AI 피드백 생성 실패(모델 %s): %s", model, exc)

    return FALLBACK_MESSAGE


def build_trend_analysis(db: Session, user_id: str) -> Optional[TrendAnalysisResponse]:
    """"이력분석" 버튼 클릭 시 호출된다. 기존 build_trend_series()로 그래프용
    시계열 데이터를 얻고, 그 추세를 근거로 Gemini에게 관리 피드백을 생성시킨다."""
    trend = build_trend_series(db, user_id)
    if trend is None:
        return None

    ai_feedback = _generate_ai_feedback(trend.summary_message, trend.feature_trends)

    return TrendAnalysisResponse(
        user_id=trend.user_id,
        series=trend.series,
        feature_trends=trend.feature_trends,
        overall_direction=trend.overall_direction,
        ai_feedback=ai_feedback,
    )
