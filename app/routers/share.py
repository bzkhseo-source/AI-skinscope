from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.schemas.share import SharedResultView
from app.services.share_service import get_shared_result

router = APIRouter(prefix="/share", tags=["share"])


@router.get("/{token}", response_model=SharedResultView)
def read_shared_result(token: str, db: Session = Depends(get_db)) -> SharedResultView:
    """인증 없이 접근 가능한 공개 조회 엔드포인트. 추측 불가능한 토큰과
    만료시간으로만 보호되므로, 개인정보·사진·병원/성분 추천 등은 절대
    포함하지 않고 핵심 결과 요약만 반환한다."""
    result = get_shared_result(db, token)
    if result is None:
        raise HTTPException(status_code=404, detail="링크가 만료되었거나 존재하지 않습니다.")
    return result
