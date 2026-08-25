from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.agent import AgentResult
from app.schemas.history import HistoryEntry, HistoryResponse
from app.services.memory_service import compute_trend, get_history, get_record, load_agent_result

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/{user_id}", response_model=HistoryResponse)
def read_history(user_id: str, db: Session = Depends(get_db)) -> HistoryResponse:
    records = get_history(db, user_id)
    entries = [HistoryEntry.model_validate(r) for r in records]
    trend = compute_trend(records)

    return HistoryResponse(user_id=user_id, entries=entries, trend=trend)


@router.get("/{user_id}/{record_id}", response_model=AgentResult)
def read_record_detail(user_id: str, record_id: int, db: Session = Depends(get_db)) -> AgentResult:
    record = get_record(db, user_id, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="해당 기록을 찾을 수 없습니다.")
    return load_agent_result(record)