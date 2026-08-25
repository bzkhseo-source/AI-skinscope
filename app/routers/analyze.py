from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.agent import AgentResult
from app.services.agent_service import run_skin_analysis_agent
from app.services.memory_service import save_record

router = APIRouter(prefix="/analyze", tags=["analyze"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("", response_model=AgentResult)
async def analyze_skin(
    file: UploadFile = File(..., description="피부 사진 (jpg/png/webp)"),
    user_id: str = Form(..., description="사용자 식별자 (이력 저장용)"),
    latitude: Optional[float] = Form(default=None, description="사용자 위도 (병원 검색용)"),
    longitude: Optional[float] = Form(default=None, description="사용자 경도 (병원 검색용)"),
    db: Session = Depends(get_db),
) -> AgentResult:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 이미지 형식입니다: {file.content_type}",
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    try:
        result = run_skin_analysis_agent(
            image_bytes,
            mime_type=file.content_type,
            latitude=latitude,
            longitude=longitude,
        )
    except RuntimeError as exc:
        # Gemini 모든 모델 호출 실패(쿼터 초과 등)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    save_record(db, user_id=user_id, agent_result=result)
    return result