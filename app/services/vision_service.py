import json
import logging

from google import genai
from google.genai import types

from app.core.config import settings
from app.schemas.vision import SkinAnalysisResult

logger = logging.getLogger(__name__)

# AI Hub "안면부 피부질환 이미지 합성 데이터"(dataSetSn=71863)의
# diagnosis_info.desc 필드 원문을 그대로 사용한 few-shot 판단 기준.
DISEASE_REFERENCE = """
아래는 AI Hub 안면부 피부질환 이미지 합성 데이터의 공식 정의를 참고한
패턴 설명이다. 이 정의와 유사한 시각적 특징이 사진에서 명확히 관찰될
경우에만 suspected_patterns에 포함하고, 애매하면 포함하지 마라.

1. 건선(psoriasis): 인설이 쌓인 붉은 구진이나 판으로 나타나는 염증성 피부질환
2. 아토피피부염(atopic dermatitis): 심한 가려움을 동반하는 만성 습진의 일종
3. 여드름(acne): 면포와 구진, 농포, 결절 등으로 나타나는 피지선과 모낭의 만성질환
4. 지루피부염(seborrheic dermatitis): 두피, 눈썹, 코입주름 등 피지분비가 있는
   곳을 따라 발생하는 염증성 피부질환
5. 주사(rosacea): 얼굴의 가운데 부위에 발생하는 지속적인 홍반이 특징인
   염증성 피부질환
"""

# AI Hub "한국인 피부상태 측정 데이터"(dataSetSn=71645) 중 measurement_data.csv를
# 전수 분석(n=1,072)하여 산출한 정상 참고 범위. 사진만으로는 장비 실측이
# 불가능하므로, Gemini의 주관적 0~100 점수 판단을 이 실제 인구 분포에
# 맞춰 보정(anchor)하는 용도로만 사용한다.
POPULATION_REFERENCE = """
아래는 국내 성인 1,072명의 정밀 피부 측정 장비 실측 분포(AI Hub 한국인
피부상태 측정 데이터 기준)이다. 사진에서 장비 수치를 직접 측정할 수는
없지만, 아래 분포를 "무엇이 평균이고 무엇이 심한 축에 속하는지" 판단하는
기준점(anchor)으로 삼아 0~100 점수를 매겨라. 점수 50 = 중앙값(평균) 수준,
점수 90 이상 = 상위 5% 우수 수준, 점수 10 이하 = 하위 5% 열악한 수준을
의미하도록 보정하라.

- 수분: 평균 60%, 중앙값 60.7%, 하위5% 43.7%, 상위5% 76.0%
  (건조할수록 낮은 점수, 촉촉할수록 높은 점수)
- 탄력: 평균 49~51(Q0 기준), 하위5% 32~34, 상위5% 71~73
  (탄력이 낮을수록 낮은 점수)
- 주름(눈가 거칠기 Ra): 평균 21.7~21.9, 하위5%(양호) 14.0, 상위5%(심함) 32~33
  (거칠기 수치가 낮을수록 좋은 상태이므로 점수는 높게, 수치가 높을수록 점수 낮게)
- 색소침착(반점 개수): 평균 159개, 하위5%(양호) 57개, 상위5%(심함) 266개
  (개수가 적을수록 점수 높게)
- 모공(개수): 평균 880~930개, 하위5%(양호) 230~240개, 상위5%(심함) 1650~1780개
  (개수가 적을수록 점수 높게)
- 붉은기(redness): 위 데이터셋에는 별도 장비 측정치가 없으므로, 사진에서
  관찰되는 홍반·모세혈관 확장·염증 정도를 기준으로 임상적으로 판단하라.
"""

SYSTEM_PROMPT = f"""당신은 피부 상태를 참고용으로 스크리닝하는 AI 어시스턴트다.
절대 확정적인 의료 진단을 내리지 마라. 항상 "참고용이며 진단이 아니다"라는
전제를 유지하고, ai_summary 필드에도 이를 명시하라.

{DISEASE_REFERENCE}

{POPULATION_REFERENCE}

아래 6개 항목을 0~100 점수로 평가하라:
- pore(모공), elasticity(탄력), moisture(수분), wrinkle(주름),
  pigmentation(색소침착), redness(붉은기/염증)

overall_score는 6개 항목의 가중 평균이 아니라, 사진에서 관찰되는 전반적인
피부 건강 상태를 종합적으로 판단한 점수로 산출하라.

심각도가 높다고 판단되면(예: 화농성 병변이 넓게 퍼짐, 극심한 염증 등)
needs_dermatologist를 true로 설정하라.

반드시 아래 JSON 스키마와 정확히 일치하는 JSON만 응답하라. 다른 텍스트를
포함하지 마라.
"""


def _build_client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


def _call_gemini(client: genai.Client, model: str, image_bytes: bytes, mime_type: str) -> str:
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            SYSTEM_PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SkinAnalysisResult,
        ),
    )
    return response.text


def analyze_skin_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> SkinAnalysisResult:
    """
    피부 사진을 Gemini Vision으로 분석한다.
    기본 모델(gemini-3.6-flash) 호출 실패(쿼터 초과 등) 시
    대체 모델(gemini-3.5-flash-lite)로 자동 전환한다.
    """
    client = _build_client()
    models_to_try = [settings.gemini_primary_model, settings.gemini_fallback_model]

    last_error: Exception | None = None
    for model in models_to_try:
        try:
            raw_text = _call_gemini(client, model, image_bytes, mime_type)
            data = json.loads(raw_text)
            return SkinAnalysisResult.model_validate(data)
        except Exception as exc:  # noqa: BLE001 - 모델별 예외를 모두 잡아 fallback 처리
            logger.warning("Gemini 모델 %s 호출 실패: %s", model, exc)
            last_error = exc
            continue

    raise RuntimeError(f"모든 Gemini 모델 호출에 실패했습니다: {last_error}")