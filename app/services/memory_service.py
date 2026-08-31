import json
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.record import SkinRecord
from app.schemas.agent import AgentResult
from app.schemas.history import (
    FeatureTrendSummary,
    HistoryEntry,
    SeriesPoint,
    TrendInfo,
    TrendSeriesResponse,
)

# 시계열 분석(build_trend_series)에서 사용하는 6개 항목 — 모두 "높을수록 양호"로
# 통일된 척도이므로(featureScoreTier와 동일 규칙), 기울기 부호만으로 개선/악화를
# 판단할 수 있다.
FEATURE_KEYS = ["pore", "elasticity", "moisture", "wrinkle", "pigmentation", "redness"]
FEATURE_LABELS_KO = {
    "pore": "모공",
    "elasticity": "탄력",
    "moisture": "수분",
    "wrinkle": "주름",
    "pigmentation": "색소침착",
    "redness": "붉은기",
}
TREND_MIN_RECORDS = 2  # 시계열 분석 최소 기록 수
TREND_SLOPE_EPSILON = 0.5  # 이 이하의 기울기는 "변화 없음(stable)"으로 취급


def save_record(db: Session, user_id: str, agent_result: AgentResult) -> SkinRecord:
    record = SkinRecord(
        user_id=user_id,
        overall_score=agent_result.vision.overall_score,
        needs_dermatologist=agent_result.needs_dermatologist,
        result_json=agent_result.model_dump_json(),
        age=agent_result.age,
        gender=agent_result.gender,
        skin_age=agent_result.skin_age,
        skin_age_reliable=agent_result.skin_age_reliable,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_history(db: Session, user_id: str, limit: int = 20) -> List[SkinRecord]:
    return (
        db.query(SkinRecord)
        .filter(SkinRecord.user_id == user_id)
        .order_by(SkinRecord.created_at.desc())
        .limit(limit)
        .all()
    )

def get_record(db: Session, user_id: str, record_id: int) -> Optional[SkinRecord]:
    return (
        db.query(SkinRecord)
        .filter(SkinRecord.user_id == user_id, SkinRecord.id == record_id)
        .first()
    )

def get_history_series(db: Session, user_id: str, limit: int = 60) -> List[SkinRecord]:
    """시계열 분석용 — 오래된 순(과거→최신)으로 정렬해 반환한다."""
    return (
        db.query(SkinRecord)
        .filter(SkinRecord.user_id == user_id)
        .order_by(SkinRecord.created_at.asc())
        .limit(limit)
        .all()
    )


def delete_record(db: Session, user_id: str, record_id: int) -> bool:
    """이력 화면에서 개별 기록 삭제 (FR-12). user_id까지 함께 검사해 다른
    사용자의 기록을 지울 수 없도록 한다."""
    record = get_record(db, user_id, record_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True


def save_feedback(db: Session, user_id: str, record_id: int, rating: int, comment: Optional[str]) -> Optional[SkinRecord]:
    record = get_record(db, user_id, record_id)
    if record is None:
        return None
    record.satisfaction_rating = rating
    record.feedback_comment = comment
    db.commit()
    db.refresh(record)
    return record

def compute_trend(records: List[SkinRecord]) -> Optional[TrendInfo]:
    """가장 최근 두 기록(records[0]=최신, records[1]=이전)을 비교한다."""
    if len(records) < 2:
        return None

    latest, previous = records[0], records[1]
    delta = latest.overall_score - previous.overall_score

    if delta > 0:
        coaching_message = f"지난 기록보다 {delta}점 개선되었습니다. 좋은 관리 습관을 유지해보세요."
    elif delta < 0:
        coaching_message = f"지난 기록보다 {abs(delta)}점 낮아졌습니다. 최근 관리 루틴을 점검해보세요."
    else:
        coaching_message = "지난 기록과 점수가 동일합니다. 꾸준한 관리를 이어가보세요."

    return TrendInfo(
        previous_score=previous.overall_score,
        latest_score=latest.overall_score,
        score_delta=delta,
        coaching_message=coaching_message,
    )


def _linear_slope(values: List[int]) -> float:
    """최소자승법(least squares)으로 시점 인덱스(0..n-1) 대비 점수의 기울기를
    구한다. 최근 2건만 비교하던 기존 compute_trend()와 달리, 저장된 모든
    기록을 반영해 노이즈(사진 한 장의 우연한 편차)에 덜 흔들리는 추세를 본다."""
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    numerator = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    denominator = sum((i - mean_x) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _direction_from_slope(slope: float) -> str:
    if slope > TREND_SLOPE_EPSILON:
        return "improving"
    if slope < -TREND_SLOPE_EPSILON:
        return "declining"
    return "stable"


def build_trend_series(db: Session, user_id: str) -> Optional[TrendSeriesResponse]:
    """이력 전체를 시계열로 분석한다 (FR-09 확장). compute_trend()가 "가장 최근
    두 기록"만 비교하는 것과 달리, 저장된 모든 분석 결과의 6개 feature_score와
    overall_score 추이를 항목별로 계산한다. Gemini를 재호출하지 않고 저장된
    result_json만으로 결정론적으로 계산하므로 비용이 들지 않는다."""
    records = get_history_series(db, user_id)
    if len(records) < TREND_MIN_RECORDS:
        return None

    points: List[SeriesPoint] = []
    feature_series: Dict[str, List[int]] = {key: [] for key in FEATURE_KEYS}
    overall_series: List[int] = []

    for record in records:
        agent_result = load_agent_result(record)
        feature_scores = agent_result.vision.feature_scores
        points.append(
            SeriesPoint(
                id=record.id,
                created_at=record.created_at,
                overall_score=record.overall_score,
                feature_scores=feature_scores,
                skin_age=record.skin_age,
            )
        )
        overall_series.append(record.overall_score)
        for key in FEATURE_KEYS:
            feature_series[key].append(getattr(feature_scores, key))

    feature_trends: List[FeatureTrendSummary] = []
    for key in FEATURE_KEYS:
        series = feature_series[key]
        direction = _direction_from_slope(_linear_slope(series))
        feature_trends.append(
            FeatureTrendSummary(
                key=key,
                label_ko=FEATURE_LABELS_KO[key],
                first_score=series[0],
                last_score=series[-1],
                delta=series[-1] - series[0],
                direction=direction,
            )
        )

    overall_direction = _direction_from_slope(_linear_slope(overall_series))
    improving = [t.label_ko for t in feature_trends if t.direction == "improving"]
    declining = [t.label_ko for t in feature_trends if t.direction == "declining"]

    overall_desc = {"improving": "개선", "declining": "악화"}.get(overall_direction, "큰 변화 없이 유지")
    summary_parts = [f"최근 {len(records)}건의 기록을 분석한 결과, 종합 점수는 {overall_desc} 추세입니다."]
    if improving:
        summary_parts.append(f"{', '.join(improving)} 항목이 개선되고 있어요.")
    if declining:
        summary_parts.append(f"{', '.join(declining)} 항목은 주의가 필요해요.")
    summary_message = " ".join(summary_parts)

    return TrendSeriesResponse(
        user_id=user_id,
        series=points,
        feature_trends=feature_trends,
        overall_direction=overall_direction,
        summary_message=summary_message,
    )


def load_agent_result(record: SkinRecord) -> AgentResult:
    """저장된 JSON을 다시 AgentResult 객체로 복원한다 (상세 조회용).

    save_record()가 호출되는 시점(분석 직후)에는 아직 DB에 커밋되지 않아
    record.id를 알 수 없으므로, 저장되는 result_json 안의 record_id는 항상
    None이다. 여기서 실제 DB row의 id로 채워 넣지 않으면, 이력 상세보기로
    불러온 결과는 record_id가 계속 없는 것으로 취급되어 피드백 제출·공유
    링크 생성처럼 record_id가 필요한 기능이 전부 동작하지 않는다.
    """
    agent_result = AgentResult.model_validate(json.loads(record.result_json))
    return agent_result.model_copy(update={"record_id": record.id})