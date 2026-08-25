from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class HistoryEntry(BaseModel):
    """이력 목록의 개별 항목 (요약본)"""

    id: int
    created_at: datetime
    overall_score: int
    needs_dermatologist: bool

    class Config:
        from_attributes = True


class TrendInfo(BaseModel):
    """가장 최근 두 기록을 비교한 변화 추세"""

    previous_score: int
    latest_score: int
    score_delta: int = Field(..., description="latest_score - previous_score. 양수면 개선")
    coaching_message: str


class HistoryResponse(BaseModel):
    user_id: str
    entries: List[HistoryEntry]
    trend: Optional[TrendInfo] = None