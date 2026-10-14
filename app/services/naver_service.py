import logging
from typing import Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SHOP_SEARCH_URL = "https://openapi.naver.com/v1/search/shop.json"
REQUEST_TIMEOUT = 1.5

# 화장품 완제품이 아닌 원료/벌크/DIY 재료 판매 상품을 걸러내기 위한 제목 키워드.
# "성분 화장품" 통합검색만으로는 이런 원료성 상품이 함께 잡혀(원문 민원 사례:
# 바쿠치올 검색 시 원료 판매처가 섞여 나옴), 완제품만 추리기 위해 추가한다.
RAW_MATERIAL_EXCLUDE_KEYWORDS = [
    "원료",
    "벌크",
    "대용량",
    "비누베이스",
    "공방",
    "소분",
    "diy",
    "캐리어오일",
    "원재료",
    "실험실",
]

# 네이버쇼핑 분류체계의 화장품/미용 대분류명(쇼핑인사이트 API 기준 코드 50000002와 동일 체계).
COSMETICS_CATEGORY_NAME = "화장품/미용"

# 성분 카탈로그가 유한(고민 8종 x 상위 5개 이내)해 사용자 요청마다 중복
# 조회가 많으므로, 프로세스 생존 기간 동안 영구 캐시해 API 호출을 최소화한다.
_search_cache: Dict[str, Optional[str]] = {}


def _is_finished_cosmetic_product(item: dict) -> bool:
    """검색 결과 한 건이 화장품 완제품인지(원료/벌크 판매가 아닌지) 판별한다."""
    title = (item.get("title") or "").lower()
    if any(keyword.lower() in title for keyword in RAW_MATERIAL_EXCLUDE_KEYWORDS):
        return False

    # category1이 응답에 있는데 "화장품/미용"이 아니라고 확실히 다른 경우에만
    # 제외한다. 필드가 비어있거나 예상과 다른 응답 형식이어도 안전하게
    # 통과시켜(관대한 원칙), 분류체계 변경에도 전체 추천이 깨지지 않게 한다.
    category1 = item.get("category1")
    if category1 and category1 != COSMETICS_CATEGORY_NAME:
        return False

    return True


def find_cosmetic_product_url(name_ko: str) -> Optional[str]:
    """네이버쇼핑 검색 API로 성분명이 들어간 화장품 완제품의 실제 상품 링크를 찾는다.

    API 키 미설정, 네트워크/응답 오류, 적합한 결과 없음 등 어떤 이유로든 찾지
    못하면 None을 반환한다 — 호출 측(ingredient_service)이 기존 범용 검색
    링크(search.shopping.naver.com)로 대체하도록 하기 위함이다(장애 허용
    원칙, kakao_service.py/uv_service.py와 동일 패턴).
    """
    if not settings.naver_client_id or not settings.naver_client_secret:
        return None

    if name_ko in _search_cache:
        return _search_cache[name_ko]

    url: Optional[str] = None
    try:
        response = httpx.get(
            SHOP_SEARCH_URL,
            params={
                "query": f"{name_ko} 성분 화장품",
                "display": 20,
                "sort": "sim",
            },
            headers={
                "X-Naver-Client-Id": settings.naver_client_id,
                "X-Naver-Client-Secret": settings.naver_client_secret,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        for item in items:
            if _is_finished_cosmetic_product(item):
                url = item.get("link") or None
                break
    except (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError) as exc:
        logger.warning("네이버쇼핑 검색 실패 (성분: %s): %s", name_ko, exc)
        url = None

    _search_cache[name_ko] = url
    return url
