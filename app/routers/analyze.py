from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.agent import AgentResult
from app.schemas.feedback import FeedbackRequest
from app.schemas.share import ShareCreateRequest, ShareLinkResponse
from app.services.agent_service import run_skin_analysis_agent
from app.services.memory_service import save_feedback, save_record
from app.services.share_service import create_share_link

router = APIRouter(prefix="/analyze", tags=["analyze"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_GENDERS = {"female", "male"}


@router.post("", response_model=AgentResult)
async def analyze_skin(
    file: UploadFile = File(..., description="피부 사진 (jpg/png/webp)"),
    user_id: str = Form(..., description="사용자 식별자 (이력 저장용)"),
    latitude: Optional[float] = Form(default=None, description="사용자 위도 (병원 검색용)"),
    longitude: Optional[float] = Form(default=None, description="사용자 경도 (병원 검색용)"),
    age: Optional[int] = Form(
        default=None, description="사용자 나이 (선택 입력, 동년배 비교/피부나이 산출용)"
    ),
    gender: Optional[str] = Form(
        default=None, description="사용자 성별 'female'/'male' (선택 입력)"
    ),
    db: Session = Depends(get_db),
) -> AgentResult:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 이미지 형식입니다: {file.content_type}",
        )
    if age is not None and not (1 <= age <= 120):
        raise HTTPException(status_code=400, detail="나이는 1~120 사이여야 합니다.")
    if gender is not None and gender not in ALLOWED_GENDERS:
        raise HTTPException(status_code=400, detail="gender는 'female' 또는 'male'만 가능합니다.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    try:
        result = run_skin_analysis_agent(
            image_bytes,
            mime_type=file.content_type,
            latitude=latitude,
            longitude=longitude,
            age=age,
            gender=gender,
        )
    except RuntimeError as exc:
        # Gemini 모든 모델 호출 실패(쿼터 초과 등)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    record = save_record(db, user_id=user_id, agent_result=result)
    return result.model_copy(update={"record_id": record.id})


@router.post("/{record_id}/feedback")
def submit_feedback(
    record_id: int, payload: FeedbackRequest, db: Session = Depends(get_db)
) -> dict:
    record = save_feedback(
        db,
        user_id=payload.user_id,
        record_id=record_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="해당 기록을 찾을 수 없습니다.")
    return {"status": "ok"}


@router.post("/{record_id}/share", response_model=ShareLinkResponse)
def create_share(
    record_id: int, payload: ShareCreateRequest, db: Session = Depends(get_db)
) -> ShareLinkResponse:
    link = create_share_link(db, user_id=payload.user_id, record_id=record_id)
    if link is None:
        raise HTTPException(status_code=404, detail="해당 기록을 찾을 수 없습니다.")
    return ShareLinkResponse(token=link.token, expires_at=link.expires_at)