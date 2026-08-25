from typing import Optional
from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    user_id: str = Field(..., description="기록 소유자 확인용 사용자 식별자")
    rating: int = Field(..., ge=1, le=5, description="만족도 1~5점")
    comment: Optional[str] = Field(default=None, max_length=1000, description="자유 의견 (선택)")