import logging
from typing import List

import httpx

from app.core.config import settings
from app.schemas.agent import HospitalInfo

logger = logging.getLogger(__name__)

KAKAO_LOCAL_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def search_nearby_dermatology_clinics(
    latitude: float,
    longitude: float,
    radius_m: int = 3000,
    limit: int = 5,
) -> List[HospitalInfo]:
    """
    카카오맵 키워드 검색 API로 주어진 좌표 근처의 피부과를 찾는다.
    이 함수가 AI Agent의 "도구(tool)" 역할을 한다.
    """
    if not settings.kakao_map_api_key:
        logger.warning("KAKAO_MAP_API_KEY가 설정되지 않아 병원 검색을 건너뜁니다.")
        return []

    headers = {"Authorization": f"KakaoAK {settings.kakao_map_api_key}"}
    params = {
        "query": "피부과",
        "x": str(longitude),
        "y": str(latitude),
        "radius": str(radius_m),
        "sort": "distance",
        "size": str(limit),
    }

    try:
        response = httpx.get(
            KAKAO_LOCAL_SEARCH_URL, headers=headers, params=params, timeout=5.0
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        logger.warning("카카오맵 검색 실패: %s", exc)
        return []

    hospitals: List[HospitalInfo] = []
    for doc in data.get("documents", []):
        distance_raw = doc.get("distance")
        hospitals.append(
            HospitalInfo(
                name=doc.get("place_name", ""),
                address=doc.get("road_address_name") or doc.get("address_name", ""),
                phone=doc.get("phone", ""),
                distance_m=int(distance_raw) if distance_raw else None,
                place_url=doc.get("place_url", ""),
            )
        )
    return hospitals