import json
import logging
import math
from pathlib import Path
from typing import List, Optional, Tuple

from google import genai
from google.genai import types

from app.core.config import settings
from app.schemas.vision import SkinAnalysisResult, SkinFeatureScores

logger = logging.getLogger(__name__)

REFERENCE_EMBEDDINGS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "reference_embeddings.json"
)
REFERENCE_MEASUREMENTS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "reference_measurements.json"
)
AGE_GENDER_REFERENCE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "age_gender_reference.json"
)
REGION_REFERENCE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "region_reference.json"
)
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 768
RAG_TOP_K = 5

_reference_cache: List[dict] | None = None
_measurement_cache: List[dict] | None = None
_age_gender_reference_cache: Optional[dict] = None
_region_reference_cache: Optional[dict] = None

# STEP 4에서 measurement_data.csv(n=1,072) 전수 분석으로 산출한 백분위.
# (하위5%, 하위25%, 중앙값, 상위25%, 상위5%) 순서. RAG로 찾은 근접 사례의
# 실측 평균값을 0~100 점수로 환산하는 데 사용한다.
MOISTURE_PERCENTILES = (43.7, 54.3, 60.7, 66.8, 76.0)
ELASTICITY_PERCENTILES = (33, 42, 49, 57, 72)
WRINKLE_PERCENTILES = (14.0, 17.6, 21.0, 25.0, 32.5)  # 값이 낮을수록 좋음
PIGMENTATION_PERCENTILES = (57, 112, 157, 207, 266)  # 값이 낮을수록 좋음
PORE_PERCENTILES = (235, 548, 873, 1205, 1715)  # 값이 낮을수록 좋음

# 연령대별 anchor/피부나이 계산에서 SkinFeatureScores 필드 <-> 실측 지표 매핑.
# redness(붉은기)는 measurement_data.csv에 대응하는 장비 실측치가 없어 제외한다.
FEATURE_METRIC_PERCENTILES = {
    "moisture": (MOISTURE_PERCENTILES, True),
    "elasticity": (ELASTICITY_PERCENTILES, True),
    "wrinkle": (WRINKLE_PERCENTILES, False),
    "pigmentation": (PIGMENTATION_PERCENTILES, False),
    "pore": (PORE_PERCENTILES, False),
}
FEATURE_METRIC_LABELS_KO = {
    "moisture": "수분",
    "elasticity": "탄력",
    "wrinkle": "주름(눈가 거칠기)",
    "pigmentation": "색소침착(반점 개수)",
    "pore": "모공(개수)",
}
GENDER_LABEL_KO = {"female": "여성", "male": "남성"}

REGION_LABELS_KO = {
    "forehead": "이마",
    "nose": "코(T존)",
    "cheek_l": "왼쪽 볼",
    "cheek_r": "오른쪽 볼",
    "chin": "턱",
}
REGION_METRIC_LABELS_KO = {"moisture": "수분", "elasticity": "탄력", "pore": "모공(개수)"}

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

SYSTEM_PROMPT_TEMPLATE = """당신은 피부 상태를 참고용으로 스크리닝하는 AI 어시스턴트다.
절대 확정적인 의료 진단을 내리지 마라. 항상 "참고용이며 진단이 아니다"라는
전제를 유지하고, ai_summary 필드에도 이를 명시하라.

{disease_reference}

{population_reference}

{rag_evidence}

{region_reference}

가장 먼저, 사진에서 피부/얼굴 영역을 분석 가능한 수준으로 인식할 수 있는지
판단하라. 이 판단은 **관대하게** 하라 — 약간 어둡거나, 실내 조명이거나,
화질이 다소 낮아도 얼굴/피부 형태와 특징을 알아볼 수 있으면 true로 유지하라.
아래처럼 **분석이 도저히 불가능한 극단적인 경우에만** false로 판단하라:
- 얼굴이나 피부가 사진에 전혀 보이지 않음 (엉뚱한 대상, 풍경, 물건 등)
- 심하게 흔들리거나 초점이 완전히 나가서 형태조차 알아볼 수 없음
- 완전히 새까맣거나 완전히 하얗게 나와 아무것도 판별 불가능함
- 얼굴/피부 대부분이 물체로 가려져 분석할 영역이 거의 없음

image_quality_ok가 false인 경우 quality_note에 **반드시** 구체적인 이유를
한 문장으로 채워라(빈 값 금지). 이 경우 overall_score와 feature_scores는
모두 0으로 채우고, suspected_patterns는 빈 배열로, needs_dermatologist는
false로, ai_summary에는 "사진을 다시 촬영해 주세요" 취지의 안내만 담아라.
이 경우 아래의 점수화 지침은 적용하지 않는다.

image_quality_ok가 true인 경우에만 아래 6개 항목을 0~100 점수로 평가하라:
- pore(모공), elasticity(탄력), moisture(수분), wrinkle(주름),
  pigmentation(색소침착), redness(붉은기/염증)

overall_score는 6개 항목의 가중 평균이 아니라, 사진에서 관찰되는 전반적인
피부 건강 상태를 종합적으로 판단한 점수로 산출하라.

심각도가 높다고 판단되면(예: 화농성 병변이 넓게 퍼짐, 극심한 염증 등)
needs_dermatologist를 true로 설정하라.

image_quality_ok가 true인 경우, ai_focus와 ai_detail을 반드시 채워라:
- ai_focus: 6개 항목 중 가장 우선적으로 관리가 필요한 항목 하나를 짚어
  "~관리에 집중해보세요"처럼 실행 가능한 한 줄로 작성하라. "전문의와
  상담하세요", "진단이 아닙니다" 같은 면책성 표현은 ai_focus/ai_detail에
  절대 넣지 마라 (그 문구는 UI가 별도로 항상 표시하므로 여기서는 반복할
  필요가 없다).
- ai_detail: ai_focus로 짚은 판단의 시각적 근거를 1~2문장으로 설명하라
  (예: "다른 항목에 비해 모공이 두드러지고 T존 유분이 많아 보입니다").
- ai_summary에는 기존과 동일하게 전체 소견을 자유 문장으로 작성하되,
  ai_focus/ai_detail의 내용과 크게 모순되지 않도록 하라.

image_quality_ok가 true인 경우, regional_scores도 반드시 채워라. 얼굴을
이마(forehead)/코(nose, T존)/왼쪽볼(cheek_l)/오른쪽볼(cheek_r)/턱(chin)
5개 구역으로 나누어, 각 구역마다 pore(모공)/oiliness(유분)/trouble(트러블)
3개 점수(0~100, 높을수록 양호)와 note(한 줄 소견)를 채워라. 사진에 일부
구역이 잘 보이지 않으면(예: 앞머리에 이마가 가려짐) 보이는 범위 내에서
최선으로 추정하고 note에 그 사실을 언급하라. image_quality_ok가 false인
경우 regional_scores는 채우지 마라(생략).

반드시 아래 JSON 스키마와 정확히 일치하는 JSON만 응답하라. 다른 텍스트를
포함하지 마라.
"""


def _load_reference_embeddings() -> List[dict]:
    """RAG 참고 인덱스를 최초 1회만 로드해 캐시한다."""
    global _reference_cache
    if _reference_cache is not None:
        return _reference_cache

    if not REFERENCE_EMBEDDINGS_PATH.exists():
        logger.warning(
            "RAG 참고 인덱스 파일이 없습니다 (%s). RAG 근거 없이 진행합니다.",
            REFERENCE_EMBEDDINGS_PATH,
        )
        _reference_cache = []
        return _reference_cache

    data = json.loads(REFERENCE_EMBEDDINGS_PATH.read_text(encoding="utf-8"))
    _reference_cache = data
    logger.info("RAG 참고 인덱스 로드 완료: %d건", len(data))
    return _reference_cache


def _load_measurement_reference() -> List[dict]:
    """실측값 RAG 참고 인덱스를 최초 1회만 로드해 캐시한다."""
    global _measurement_cache
    if _measurement_cache is not None:
        return _measurement_cache

    if not REFERENCE_MEASUREMENTS_PATH.exists():
        logger.warning(
            "실측값 RAG 참고 인덱스 파일이 없습니다 (%s). 근거 없이 진행합니다.",
            REFERENCE_MEASUREMENTS_PATH,
        )
        _measurement_cache = []
        return _measurement_cache

    data = json.loads(REFERENCE_MEASUREMENTS_PATH.read_text(encoding="utf-8"))
    _measurement_cache = data
    logger.info("실측값 RAG 참고 인덱스 로드 완료: %d건", len(data))
    return _measurement_cache


def _load_age_gender_reference() -> dict:
    """연령대×성별 백분위 참고 데이터를 최초 1회만 로드해 캐시한다.

    scripts/build_age_gender_reference.py가 AI Hub 한국인 피부상태 측정
    데이터의 meta_data.csv(나이·성별) + measurement_data.csv(실측값)를
    조인해 전수 분석으로 만든 결과다.
    """
    global _age_gender_reference_cache
    if _age_gender_reference_cache is not None:
        return _age_gender_reference_cache

    if not AGE_GENDER_REFERENCE_PATH.exists():
        logger.warning(
            "연령대별 참고 데이터 파일이 없습니다 (%s). 전체 인구 anchor로 대체합니다.",
            AGE_GENDER_REFERENCE_PATH,
        )
        _age_gender_reference_cache = {}
        return _age_gender_reference_cache

    _age_gender_reference_cache = json.loads(
        AGE_GENDER_REFERENCE_PATH.read_text(encoding="utf-8")
    )
    return _age_gender_reference_cache


def _select_age_gender_group(
    age: Optional[int], gender: Optional[str]
) -> Tuple[Optional[dict], Optional[str]]:
    """나이·성별에 맞는 참고 그룹을 고른다.

    연령대+성별 그룹이 있고 표본이 충분하면 그것을, 아니면 연령대 그룹,
    그것도 부족하면 전체 인구로 순서대로 대체(fallback)한다.
    """
    ref = _load_age_gender_reference()
    if not ref or age is None:
        return None, None

    min_size = ref.get("min_group_size", 15)
    age_band = min(max((age // 10) * 10, 10), 60)

    if gender in GENDER_LABEL_KO:
        group = ref.get("by_age_gender", {}).get(f"{age_band}_{gender}")
        if group and group["count"] >= min_size:
            return group, f"{age_band}대 {GENDER_LABEL_KO[gender]}"

    group = ref.get("by_age_band", {}).get(str(age_band))
    if group and group["count"] >= min_size:
        return group, f"{age_band}대"

    overall = ref.get("overall")
    if overall:
        return overall, "전체"
    return None, None


def _build_dynamic_population_text(age: Optional[int], gender: Optional[str]) -> Optional[str]:
    """사용자가 나이를 입력한 경우, 전체 인구 대신 동일 연령대(±성별) anchor 텍스트를 만든다."""
    group, label = _select_age_gender_group(age, gender)
    if not group or not label:
        return None

    lines = []
    for metric, kor_label in FEATURE_METRIC_LABELS_KO.items():
        stats = group.get(metric)
        if not stats:
            continue
        lines.append(
            f"- {kor_label}: {label} 평균(중앙값) {stats['p50']}, "
            f"하위5% {stats['p5']}, 상위5% {stats['p95']}"
        )
    if not lines:
        return None
    body = "\n".join(lines)

    return f"""아래는 국내 {label} {group['count']}명의 정밀 피부 측정 장비 실측 분포(AI Hub
한국인 피부상태 측정 데이터 기준, 사용자와 동일한 연령대{"·성별" if "여성" in label or "남성" in label else ""}
그룹)이다. 사진에서 장비 수치를 직접 측정할 수는 없지만, 아래 분포를 "이 연령대에서
무엇이 평균이고 무엇이 심한 축에 속하는지" 판단하는 기준점(anchor)으로 삼아 0~100
점수를 매겨라. 점수 50 = 이 그룹 중앙값 수준, 점수 90 이상 = 이 그룹 상위 5% 우수
수준, 점수 10 이하 = 이 그룹 하위 5% 열악한 수준을 의미하도록 보정하라.

{body}
- 붉은기(redness): 이 데이터셋에는 별도 장비 측정치가 없으므로, 사진에서 관찰되는
  홍반·모세혈관 확장·염증 정도를 기준으로 임상적으로 판단하라."""


def _age_band_score_profile(age_band_key: str) -> Optional[dict]:
    """특정 연령대 그룹의 중앙값을, 전체 인구 백분위 기준 0~100 점수로 환산한다.

    피부나이 계산 시 사용자의 feature_scores(이미 0~100 스케일)와 같은
    스케일에서 비교하기 위해 필요하다.
    """
    ref = _load_age_gender_reference()
    group = ref.get("by_age_band", {}).get(age_band_key)
    if not group:
        return None

    profile = {}
    for metric, (percentiles, higher_is_better) in FEATURE_METRIC_PERCENTILES.items():
        stats = group.get(metric)
        if not stats:
            return None
        profile[metric] = _interp_score(stats["p50"], percentiles, higher_is_better)
    return profile


def compute_skin_age(feature_scores: SkinFeatureScores) -> Optional[int]:
    """사용자의 feature_scores와 가장 가까운(유클리드 거리 최소) 연령대의 대표 나이를 구한다.

    사용자가 실제 나이를 입력했는지 여부와 무관하게, "이 피부 특징이 어느
    연령대 평균과 가장 비슷한가"를 계산하는 독립적인 지표다.
    """
    ref = _load_age_gender_reference()
    by_age_band = ref.get("by_age_band", {})
    if not by_age_band:
        return None

    user_vec = {metric: getattr(feature_scores, metric) for metric in FEATURE_METRIC_PERCENTILES}

    best_band: Optional[int] = None
    best_distance: Optional[float] = None
    for age_band_key in by_age_band:
        profile = _age_band_score_profile(age_band_key)
        if profile is None:
            continue
        distance = math.sqrt(
            sum((user_vec[metric] - profile[metric]) ** 2 for metric in FEATURE_METRIC_PERCENTILES)
        )
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_band = int(age_band_key)

    if best_band is None:
        return None
    return best_band + 5  # 구간 대표값(예: "20대" 구간 -> 25세)으로 근사


def build_peer_comparison_note(
    feature_scores: SkinFeatureScores, age: Optional[int], gender: Optional[str]
) -> Optional[str]:
    """동년배(±성별) 그룹과 비교했을 때 가장 두드러진 차이를 한 문장으로 만든다.

    Gemini를 다시 호출하지 않고, 이미 계산된 feature_scores와 사전 집계된
    연령대 그룹 통계만으로 결정론적으로 생성한다.
    """
    if age is None:
        return None

    group, label = _select_age_gender_group(age, gender)
    if not group or not label:
        return None

    diffs = []
    for metric, (percentiles, higher_is_better) in FEATURE_METRIC_PERCENTILES.items():
        stats = group.get(metric)
        if not stats:
            continue
        group_score = _interp_score(stats["p50"], percentiles, higher_is_better)
        user_score = getattr(feature_scores, metric)
        diffs.append((metric, user_score - group_score))

    if not diffs:
        return None

    diffs.sort(key=lambda item: item[1])
    worst_metric, worst_diff = diffs[0]
    best_metric, best_diff = diffs[-1]

    if worst_diff <= -8:
        return f"{label} 평균과 비교했을 때 {FEATURE_METRIC_LABELS_KO[worst_metric]}이(가) 다소 낮은 편입니다."
    if best_diff >= 8:
        return f"{label} 평균과 비교했을 때 {FEATURE_METRIC_LABELS_KO[best_metric]}이(가) 우수한 편입니다."
    return f"{label} 평균과 전반적으로 비슷한 수준입니다."


def _load_region_reference() -> dict:
    """부위별(이마/왼쪽볼/오른쪽볼/턱) 실측 백분위 참고 데이터를 최초 1회만 로드해 캐시한다."""
    global _region_reference_cache
    if _region_reference_cache is not None:
        return _region_reference_cache

    if not REGION_REFERENCE_PATH.exists():
        logger.warning(
            "부위별 참고 데이터 파일이 없습니다 (%s). anchor 없이 진행합니다.",
            REGION_REFERENCE_PATH,
        )
        _region_reference_cache = {}
        return _region_reference_cache

    _region_reference_cache = json.loads(REGION_REFERENCE_PATH.read_text(encoding="utf-8"))
    return _region_reference_cache


def _build_region_reference_text() -> str:
    """5개 구역별 세부 분석(로드맵 H)을 위한 참고 텍스트를 만든다.

    이마/왼쪽볼/오른쪽볼/턱은 실측 데이터 기반 anchor를 제공하고, 코(T존)는
    이 데이터셋에 대응하는 장비 실측치가 없어(스마트폰 라벨 facepart 2/7번
    슬롯이 전 피험자에서 비어 있음을 확인) 시각적 판단만 사용하도록 명시한다.
    """
    ref = _load_region_reference()
    regions = ref.get("regions", {})
    if not regions:
        return (
            "부위별(이마/코/왼쪽볼/오른쪽볼/턱) 참고 실측 데이터가 없으므로, "
            "regional_scores의 모든 항목은 사진에서 관찰되는 시각적 특징만으로 판단하라."
        )

    lines = []
    for region_key, region_label in REGION_LABELS_KO.items():
        stats = regions.get(region_key)
        if not stats:
            lines.append(f"- {region_label}: 장비 실측 데이터 없음 (시각적 판단만 사용)")
            continue
        metric_parts = []
        for metric, metric_label in REGION_METRIC_LABELS_KO.items():
            metric_stats = stats.get(metric)
            if not metric_stats:
                continue
            metric_parts.append(
                f"{metric_label} 평균 {metric_stats['p50']}(하위5% {metric_stats['p5']}~"
                f"상위5% {metric_stats['p95']})"
            )
        lines.append(f"- {region_label}: " + ", ".join(metric_parts))

    body = "\n".join(lines)
    return f"""아래는 국내 1,072명의 부위별 정밀 피부 측정 장비 실측 분포(AI Hub 한국인
피부상태 측정 데이터 기준)다. regional_scores의 각 부위를 평가할 때, 실측치가
있는 부위는 아래 분포를 "무엇이 평균이고 무엇이 심한 축에 속하는지" 판단하는
참고 기준점으로 삼아라. 다만 이 데이터셋에는 유분(oiliness)·트러블(trouble)에
대한 장비 실측치가 전혀 없으므로, pore를 제외한 oiliness/trouble 점수는 모든
부위에서 사진의 시각적 특징(피지 반짝임, 뾰루지/블랙헤드 등)만으로 판단하라.

{body}"""


def _interp_score(
    value: float, percentiles: Tuple[float, float, float, float, float], higher_is_better: bool = True
) -> int:
    """백분위 5개 지점(하위5/25/중앙/상위25/상위5)을 기준으로 0~100 점수로 선형 보간한다."""
    p5, p25, p50, p75, p95 = percentiles
    xs = [p5, p25, p50, p75, p95]
    ys = [5, 25, 50, 75, 95] if higher_is_better else [95, 75, 50, 25, 5]

    if value <= xs[0]:
        return max(0, min(100, round(ys[0])))
    if value >= xs[-1]:
        return max(0, min(100, round(ys[-1])))

    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        y0, y1 = ys[i], ys[i + 1]
        if x0 <= value <= x1:
            if x1 == x0:
                return round(y0)
            ratio = (value - x0) / (x1 - x0)
            return round(y0 + ratio * (y1 - y0))
    return 50


def _retrieve_similar_measurements(
    user_embedding: List[float] | None,
) -> List[dict]:
    """사용자 사진 임베딩과 가장 닮은 실제 인물 top-k의 실측 프로필을 반환."""
    if user_embedding is None:
        return []

    reference = _load_measurement_reference()
    if not reference:
        return []

    scored = [
        (item["raw"], _cosine_similarity(user_embedding, item["embedding"])) for item in reference
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [raw for raw, _ in scored[:RAG_TOP_K]]


def _build_measurement_evidence_text(similar_profiles: List[dict]) -> str:
    if not similar_profiles:
        return ""

    def avg_of(key: str) -> float | None:
        vals = [p[key] for p in similar_profiles if p.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    moisture = avg_of("moisture")
    elasticity = avg_of("elasticity")
    wrinkle = avg_of("wrinkle_ra")
    pigmentation = avg_of("pigmentation_count")
    pore = avg_of("pore_count")

    lines = []
    if moisture is not None:
        lines.append(f"- 수분 예상 점수: {_interp_score(moisture, MOISTURE_PERCENTILES)}")
    if elasticity is not None:
        lines.append(f"- 탄력 예상 점수: {_interp_score(elasticity, ELASTICITY_PERCENTILES)}")
    if wrinkle is not None:
        lines.append(
            f"- 주름 예상 점수: {_interp_score(wrinkle, WRINKLE_PERCENTILES, higher_is_better=False)}"
        )
    if pigmentation is not None:
        lines.append(
            f"- 색소침착 예상 점수: {_interp_score(pigmentation, PIGMENTATION_PERCENTILES, higher_is_better=False)}"
        )
    if pore is not None:
        lines.append(f"- 모공 예상 점수: {_interp_score(pore, PORE_PERCENTILES, higher_is_better=False)}")

    if not lines:
        return ""

    body = "\n".join(lines)
    return f"""아래는 한국인 피부상태 측정 데이터에서 이 사진과 이미지 임베딩
유사도가 가장 높은 실제 인물 {len(similar_profiles)}명의 정밀 장비 실측값을
0~100 점수로 환산한 평균이다. 이는 "닮은 사람들의 실제 측정 결과"이므로
최종 feature_scores를 정할 때 강한 참고 근거로 사용하되, 사진에서 직접
보이는 시각적 특징과 모순되면 시각적 관찰을 우선하라.

{body}"""


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed_image(client: genai.Client, image_bytes: bytes, mime_type: str) -> List[float]:
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type)],
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return list(result.embeddings[0].values)


def _retrieve_similar_cases(user_embedding: List[float] | None) -> List[Tuple[str, float]]:
    """사용자 사진 임베딩과 가장 유사한 참고 질환 사례 top-k를 (질환명, 유사도)로 반환."""
    if user_embedding is None:
        return []

    reference = _load_reference_embeddings()
    if not reference:
        return []

    scored = [
        (item["disease"], _cosine_similarity(user_embedding, item["embedding"]))
        for item in reference
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:RAG_TOP_K]


def _build_rag_evidence_text(similar_cases: List[Tuple[str, float]]) -> str:
    if not similar_cases:
        return ""

    counts: dict = {}
    for disease, _ in similar_cases:
        counts[disease] = counts.get(disease, 0) + 1

    total = len(similar_cases)
    lines = [
        f"- {disease}: {count}/{total}건 ({count / total * 100:.0f}%)"
        for disease, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)
    ]
    summary = "\n".join(lines)

    return f"""아래는 AI Hub 안면부 피부질환 이미지 합성 데이터에서 이 사진과
이미지 임베딩(gemini-embedding-2) 코사인 유사도가 가장 높은 상위 {total}건의
질환 라벨 분포다. 이는 실제 데이터셋 기반 근거이므로, suspected_patterns를
판단할 때 이 분포를 참고하여 근거를 강화하라. 다만 이 분포가 절대적 정답은
아니므로, 사진에서 직접 관찰되는 시각적 특징과 종합적으로 판단하라.

{summary}"""


def _build_client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


def _call_gemini(
    client: genai.Client, model: str, image_bytes: bytes, mime_type: str, system_prompt: str
) -> str:
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            system_prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SkinAnalysisResult,
        ),
    )
    return response.text


def analyze_skin_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    age: Optional[int] = None,
    gender: Optional[str] = None,
) -> SkinAnalysisResult:
    """
    피부 사진을 Gemini Vision으로 분석한다.
    기본 모델(gemini-3.6-flash) 호출 실패(쿼터 초과 등) 시
    대체 모델(gemini-3.5-flash-lite)로 자동 전환한다.

    RAG: 사용자 사진 임베딩(gemini-embedding-2)을 한 번 계산해
    ① AI Hub 질환 이미지 데이터셋과의 유사도, ② 한국인 피부상태 측정
    데이터의 실측값 두 가지 근거를 함께 프롬프트에 반영한다.

    age(나이)가 주어지면 전체 인구 anchor 대신 동일 연령대(·성별) 그룹의
    실측 분포를 anchor로 사용한다 (로드맵 G "동년배 비교"). 나이 미입력 시
    기존과 동일하게 전체 인구 anchor를 사용한다(하위 호환).
    """
    client = _build_client()

    try:
        user_embedding = _embed_image(client, image_bytes, mime_type)
    except Exception as exc:  # noqa: BLE001
        logger.warning("사용자 이미지 임베딩 실패, RAG 근거 없이 진행합니다: %s", exc)
        user_embedding = None

    similar_cases = _retrieve_similar_cases(user_embedding)
    disease_evidence = _build_rag_evidence_text(similar_cases)

    similar_measurements = _retrieve_similar_measurements(user_embedding)
    measurement_evidence = _build_measurement_evidence_text(similar_measurements)

    rag_evidence = "\n\n".join(part for part in [disease_evidence, measurement_evidence] if part)

    population_reference = _build_dynamic_population_text(age, gender) or POPULATION_REFERENCE
    region_reference = _build_region_reference_text()

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        disease_reference=DISEASE_REFERENCE,
        population_reference=population_reference,
        rag_evidence=rag_evidence,
        region_reference=region_reference,
    )

    models_to_try = [settings.gemini_primary_model, settings.gemini_fallback_model]

    last_error: Exception | None = None
    for model in models_to_try:
        try:
            raw_text = _call_gemini(client, model, image_bytes, mime_type, system_prompt)
            data = json.loads(raw_text)
            return SkinAnalysisResult.model_validate(data)
        except Exception as exc:  # noqa: BLE001 - 모델별 예외를 모두 잡아 fallback 처리
            logger.warning("Gemini 모델 %s 호출 실패: %s", model, exc)
            last_error = exc
            continue

    raise RuntimeError(f"모든 Gemini 모델 호출에 실패했습니다: {last_error}")