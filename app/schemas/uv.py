from pydantic import BaseModel, Field


class UVIndexResult(BaseModel):
    """OpenWeatherMap UV Index 조회 결과"""

    uv_index: float = Field(..., description="자외선 지수 실측값")
    level: str = Field(
        ..., description="레벨 키: 'low' | 'moderate' | 'high' | 'very_high' | 'extreme'"
    )
    level_label_ko: str = Field(..., description="레벨 한글 라벨 (낮음/보통/높음/매우 높음/위험)")
    advice: str = Field(..., description="레벨별 고정 안내 문구 (규칙 기반, Gemini 호출 없음)")
