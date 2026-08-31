from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.agent import AgentResult
from app.schemas.history import (
    HistoryEntry,
    HistoryResponse,
    TrendAnalysisResponse,
    TrendSeriesResponse,
)
from app.services.memory_service import (
    build_trend_series,
    compute_trend,
    delete_record,
    get_history,
    get_record,
    load_agent_result,
)
from app.services.trend_analysis_service import build_trend_analysis

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/{user_id}", response_model=HistoryResponse)
def read_history(user_id: str, db: Session = Depends(get_db)) -> HistoryResponse:
    records = get_history(db, user_id)
    entries = [HistoryEntry.model_validate(r) for r in records]
    trend = compute_trend(records)

    return HistoryResponse(user_id=user_id, entries=entries, trend=trend)


# 주의: "/{user_id}/{record_id}"(record_id: int)보다 먼저 등록해야 한다.
# "/history/철수/trend" 요청이 int 변환에 실패해 다음 라우트로 넘어가는
# 동작에 기대지 않고, 고정 세그먼트를 명시적으로 먼저 매칭시키기 위함이다.
@router.get("/{user_id}/trend", response_model=TrendSeriesResponse)
def read_trend_series(user_id: str, db: Session = Depends(get_db)) -> TrendSeriesResponse:
    """이력 전체를 시계열로 분석해 항목별 변화 추세를 제공한다 (FR-09 확장)."""
    trend = build_trend_series(db, user_id)
    if trend is None:
        raise HTTPException(
            status_code=404,
            detail="시계열 분석을 위한 기록이 2건 이상 필요합니다.",
        )
    return trend


@router.get("/{user_id}/trend-analysis", response_model=TrendAnalysisResponse)
def read_trend_analysis(user_id: str, db: Session = Depends(get_db)) -> TrendAnalysisResponse:
    """"이력분석" 버튼용: 항목별 시계열 그래프 데이터 + Gemini가 생성한 관리
    피드백을 함께 제공한다. /trend와 달리 Gemini를 호출하므로, 자동 로드가
    아닌 사용자가 명시적으로 버튼을 눌렀을 때만 호출되어야 한다."""
    analysis = build_trend_analysis(db, user_id)
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="이력분석을 위한 기록이 2건 이상 필요합니다.",
        )
    return analysis


@router.get("/{user_id}/{record_id}", response_model=AgentResult)
def read_record_detail(user_id: str, record_id: int, db: Session = Depends(get_db)) -> AgentResult:
    record = get_record(db, user_id, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="해당 기록을 찾을 수 없습니다.")
    return load_agent_result(record)


@router.delete("/{user_id}/{record_id}", status_code=204)
def delete_history_record(user_id: str, record_id: int, db: Session = Depends(get_db)) -> None:
    """이력 화면에서 개별 기록을 삭제한다 (FR-12: 사용자가 본인 데이터 삭제 요청 가능)."""
    deleted = delete_record(db, user_id, record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="해당 기록을 찾을 수 없습니다.")