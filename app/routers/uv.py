from fastapi import APIRouter, HTTPException

from app.schemas.uv import UVIndexResult
from app.services.uv_service import get_uv_index

router = APIRouter(prefix="/uv-index", tags=["uv"])


@router.get("", response_model=UVIndexResult)
async def read_uv_index(latitude: float, longitude: float) -> UVIndexResult:
    result = get_uv_index(latitude, longitude)
    if result is None:
        # 키 미설정·조회 실패 시에도 500이 아닌 404로 응답해, 프론트가
        # "선택 기능이 그냥 비어있다"로 자연스럽게 처리하도록 한다.
        raise HTTPException(status_code=404, detail="자외선 지수를 조회할 수 없습니다.")
    return result
