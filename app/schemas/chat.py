from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="사용자 식별자 (기록 소유권 확인용)")
    question: str = Field(..., min_length=1, max_length=300, description="사용자 질문")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="AI가 생성한 참고용 답변")
    is_ai_generated: bool = Field(
        default=True, description="프론트에서 'AI 생성 답변' 배지를 표시하기 위한 상수 플래그"
    )
