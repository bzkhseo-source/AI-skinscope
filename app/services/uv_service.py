import logging
from typing import Optional

import httpx

from app.core.config import settings
from app.schemas.uv import UVIndexResult

logger = logging.getLogger(__name__)

# One Call API 3.0("/data/3.0/onecall")은 무료 티어라도 별도의 "One Call by
# Call" 유료 플랜 구독 신청이 필요하다는 게 실제 키로 직접 확인됐다
# (구독 없이 호출하면 401 + "requires a separate subscription" 메시지).
# 추가 구독 절차 없이 기본 무료 키로 바로 쓸 수 있는 구 UV Index 전용
# 엔드포인트를 대신 사용한다.
UV_INDEX_URL = "https://api.openweathermap.org/data/2.5/uvi"

# WHO/미국 EPA 자외선 지수 표준 5단계 구간. (하한, 레벨키, 한글라벨, 안내문구)
# advice는 Gemini를 부르지 않고 이 표를 그대로 사용한다 — 비용 없이 즉시 응답,
# 실패 지점도 줄어든다.
UV_LEVELS = [
    (0.0, "low", "낮음", "자외선 지수가 낮아요. 평소 스킨케어 루틴이면 충분해요."),
    (3.0, "moderate", "보통", "자외선 지수가 보통이에요. 외출 시 자외선차단제(SPF30+)를 발라주세요."),
    (6.0, "high", "높음", "자외선 지수가 높아요. 자외선차단제를 꼼꼼히 바르고 가능하면 그늘을 이용하세요."),
    (8.0, "very_high", "매우 높음", "자외선 지수가 매우 높아요. SPF50+ 차단제와 모자·선글라스를 챙기고 한낮 외출은 피하세요."),
    (11.0, "extreme", "위험", "자외선 지수가 위험 수준이에요. 불필요한 외출은 자제하고 철저히 자외선을 차단하세요."),
]


def _classify(uv_index: float) -> tuple:
    level, label, advice = UV_LEVELS[0][1:]
    for threshold, lvl, lbl, adv in UV_LEVELS:
        if uv_index >= threshold:
            level, label, advice = lvl, lbl, adv
    return level, label, advice


def get_uv_index(latitude: float, longitude: float) -> Optional[UVIndexResult]:
    """OpenWeatherMap 구 UV Index 엔드포인트로 현재 위치의 자외선 지수를 조회한다.

    키 미설정·API 실패·네트워크 오류 시 모두 None을 반환한다 — UV 카드는
    필수 기능이 아니므로, 실패하면 프론트가 카드를 그냥 숨긴다.
    """
    if not settings.uv_api_key:
        logger.info("UV_API_KEY가 설정되지 않아 자외선 지수 조회를 건너뜁니다.")
        return None

    params = {"lat": str(latitude), "lon": str(longitude), "appid": settings.uv_api_key}

    try:
        response = httpx.get(UV_INDEX_URL, params=params, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        uv_index = float(data["value"])
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        logger.warning("자외선 지수 조회 실패: %s", exc)
        return None

    level, level_label_ko, advice = _classify(uv_index)
    return UVIndexResult(
        uv_index=uv_index, level=level, level_label_ko=level_label_ko, advice=advice
    )
