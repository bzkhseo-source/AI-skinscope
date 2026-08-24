from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI-SkinScope",
    description="AI 피부 상태 스크리닝 & 코칭 서비스 (참고용, 의료 진단 아님)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "service": "AI-SkinScope",
        "status": "running",
        "disclaimer": "본 서비스는 AI 참고용 스크리닝이며 의료 진단이 아닙니다.",
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}