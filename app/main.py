from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.models.database import Base, engine
from app.models import record, share_link  # noqa: F401 - 테이블 등록을 위해 임포트 필요
from app.routers import analyze, history, share

Base.metadata.create_all(bind=engine)


def _migrate_add_missing_columns() -> None:
    """Base.metadata.create_all()은 새 테이블만 만들 뿐, 이미 존재하는 테이블에
    새로 추가된 컬럼(age/gender/skin_age 등)은 반영하지 않는다. Alembic 없이
    가볍게, 없는 컬럼만 ALTER TABLE로 추가한다 (SQLite/PostgreSQL 둘 다 지원)."""
    inspector = inspect(engine)
    existing_columns = {col["name"] for col in inspector.get_columns("skin_records")}

    columns_to_add = {
        "age": "INTEGER",
        "gender": "VARCHAR(10)",
        "skin_age": "INTEGER",
        "skin_age_reliable": "BOOLEAN",
    }

    with engine.begin() as conn:
        for column_name, column_type in columns_to_add.items():
            if column_name not in existing_columns:
                conn.execute(
                    text(f"ALTER TABLE skin_records ADD COLUMN {column_name} {column_type}")
                )


_migrate_add_missing_columns()

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

app.include_router(analyze.router)
app.include_router(history.router)
app.include_router(share.router)

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