from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import answer_question
from app.services.memory_service import get_record

router = APIRouter(prefix="/analyze", tags=["chat"])


@router.post("/{record_id}/chat", response_model=ChatResponse)
def chat_about_result(
    record_id: int, payload: ChatRequest, db: Session = Depends(get_db)
) -> ChatResponse:
    record = get_record(db, payload.user_id, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="해당 기록을 찾을 수 없습니다.")

    answer = answer_question(db, payload.user_id, record_id, payload.question)
    return ChatResponse(answer=answer)
