import json
import logging
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from app.schemas.agent import ConcernProductRecommendation, IngredientRecommendation
from app.schemas.vision import SkinAnalysisResult

logger = logging.getLogger(__name__)

INGREDIENT_MAP_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "concern_ingredient_map.json"
)

# concern당 노출할 추천 성분 개수
TOP_INGREDIENTS_PER_CONCERN = 5
# 이 점수 미만인 항목만 "추가로 관리가 필요한 부위"로 간주해 두 번째 추천에 포함한다.
WEAK_SCORE_THRESHOLD = 70
# suspected_patterns에 여드름이 이 유사도 이상으로 나오면 성분 추천에 포함한다.
ACNE_PATTERN_SIMILARITY_THRESHOLD = 40

# scripts/build_ingredient_map.py의 CONCERN_KEY_MAP과 짝을 이루는 역방향 매핑.
# SkinFeatureScores 필드명 -> concern_ingredient_map.json의 concern key.
# moisture(수분)는 원본 데이터셋에 별도 카테고리가 없어 가장 가까운 개념인
# dryness(과각질_악건성)로 대응한다.
FEATURE_TO_CONCERN_KEY = {
    "pore": "pore",
    "elasticity": "elasticity",
    "wrinkle": "wrinkle",
    "pigmentation": "pigmentation",
    "redness": "redness",
    "moisture": "dryness",
}

_ingredient_map_cache: Optional[dict] = None


def _load_ingredient_concerns() -> dict:
    """concern_ingredient_map.json을 최초 1회만 로드해 캐시한다."""
    global _ingredient_map_cache
    if _ingredient_map_cache is not None:
        return _ingredient_map_cache

    if not INGREDIENT_MAP_PATH.exists():
        logger.warning(
            "성분 추천 데이터 파일이 없습니다 (%s). 성분 추천 없이 진행합니다.",
            INGREDIENT_MAP_PATH,
        )
        _ingredient_map_cache = {}
        return _ingredient_map_cache

    data = json.loads(INGREDIENT_MAP_PATH.read_text(encoding="utf-8"))
    _ingredient_map_cache = data.get("concerns", {})
    logger.info("성분 추천 데이터 로드 완료: %d개 고민 카테고리", len(_ingredient_map_cache))
    return _ingredient_map_cache


def _build_search_url(name_ko: str) -> str:
    """실시간 커머스 연동 대신, 성분명으로 검색할 수 있는 링크를 대체 제공한다."""
    query = quote(f"{name_ko} 성분 화장품")
    return f"https://search.shopping.naver.com/search/all?query={query}"


def _build_concern_recommendation(concern_key: str) -> Optional[ConcernProductRecommendation]:
    concerns = _load_ingredient_concerns()
    concern_data = concerns.get(concern_key)
    if not concern_data:
        return None

    # 카테고리 간 차별화를 위해 원칙적으로 specificity(이 카테고리에서 유독 많이
    # 언급되는 정도) 랭킹을 쓴다. 다만 표본이 적어 reliable_specificity가 False인
    # 카테고리(예: sensitivity)는 lift 값 자체가 불안정하므로 raw 빈도 랭킹으로
    # 대체한다 (docs/INGREDIENT_SPECIFICITY_SPEC.md 7절 참고).
    if concern_data.get("reliable_specificity") and concern_data.get(
        "top_ingredients_by_specificity"
    ):
        source_ingredients = concern_data["top_ingredients_by_specificity"]
    else:
        source_ingredients = concern_data.get("top_ingredients", [])

    ingredients: List[IngredientRecommendation] = []
    for item in source_ingredients[:TOP_INGREDIENTS_PER_CONCERN]:
        name_ko = item.get("name_ko") or item.get("inci_name", "")
        if not name_ko:
            continue
        ingredients.append(
            IngredientRecommendation(
                inci_name=item.get("inci_name", ""),
                name_ko=name_ko,
                efficacy=item.get("efficacy") or None,
                search_url=_build_search_url(name_ko),
            )
        )

    if not ingredients:
        return None

    return ConcernProductRecommendation(
        concern_key=concern_key,
        concern_label_ko=concern_data.get("label_ko", concern_key),
        ingredients=ingredients,
    )


def recommend_products(vision: SkinAnalysisResult) -> List[ConcernProductRecommendation]:
    """분석 결과에서 가장 관리가 필요한 부위를 골라 성분 추천 목록을 만든다.

    기획서 12-2절에 따라 실시간 커머스 연동 대신 성분명 기반 검색 링크로
    대체한다. 사진 인식에 실패한 경우(image_quality_ok=false)에는 추천하지
    않는다.
    """
    if not vision.image_quality_ok:
        return []

    scores = vision.feature_scores.model_dump()
    weak_features = sorted(scores.items(), key=lambda kv: kv[1])

    # "가볍게" 추천한다는 취지(피드백 #51)에 맞춰 항상 최대 2개 고민까지만 보여준다.
    # 1순위는 항상 가장 취약한 항목이고, 2순위는 여드름 의심 패턴이 뚜렷하면
    # 그것을(진단이 아닌 참고 안내이지만 실사용자 요구가 컸던 항목, 피드백 #2) 우선하고,
    # 아니면 두 번째로 취약한 항목(70점 미만일 때만)을 사용한다.
    concern_keys: List[str] = []
    if weak_features:
        concern_keys.append(FEATURE_TO_CONCERN_KEY[weak_features[0][0]])

    acne_matched = any(
        "여드름" in pattern.name and pattern.similarity >= ACNE_PATTERN_SIMILARITY_THRESHOLD
        for pattern in vision.suspected_patterns
    )

    if acne_matched and "acne" not in concern_keys:
        concern_keys.append("acne")
    else:
        for feature_name, score in weak_features[1:]:
            if score >= WEAK_SCORE_THRESHOLD:
                break
            key = FEATURE_TO_CONCERN_KEY[feature_name]
            if key not in concern_keys:
                concern_keys.append(key)
                break

    recommendations = []
    for key in concern_keys:
        rec = _build_concern_recommendation(key)
        if rec:
            recommendations.append(rec)
    return recommendations
