"""
skin_records 테이블 전체를 CSV로 추출한다.
실사용자 테스트 결과를 최종 보고서에 정리할 때 사용한다.

사용법 (로컬 SQLite 기준, venv 활성화 상태):
    python scripts\\export_feedback.py

Render(PostgreSQL) 데이터를 뽑고 싶다면 실행 전 아래처럼 환경변수를 바꿔주면 된다.
    $env:DATABASE_URL = "<Render External Database URL>"
    python scripts\\export_feedback.py
"""

import sys
import csv
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.models.database import SessionLocal
from app.models.record import SkinRecord

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "user_test_results.csv"


def main() -> None:
    db = SessionLocal()
    try:
        records = db.query(SkinRecord).order_by(SkinRecord.created_at.asc()).all()
    finally:
        db.close()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "user_id",
                "created_at",
                "overall_score",
                "needs_dermatologist",
                "satisfaction_rating",
                "feedback_comment",
            ]
        )
        for r in records:
            writer.writerow(
                [
                    r.id,
                    r.user_id,
                    r.created_at,
                    r.overall_score,
                    r.needs_dermatologist,
                    r.satisfaction_rating if r.satisfaction_rating is not None else "",
                    (r.feedback_comment or "").replace("\n", " "),
                ]
            )

    print(f"총 {len(records)}건 추출 완료 -> {OUTPUT_PATH}")

    # 간단 통계
    rated = [r for r in records if r.satisfaction_rating is not None]
    unique_users = {r.user_id for r in records}
    print(f"참여 사용자 수(고유 user_id): {len(unique_users)}명")
    print(f"피드백 제출 건수: {len(rated)}건")
    if rated:
        avg_rating = sum(r.satisfaction_rating for r in rated) / len(rated)
        print(f"평균 만족도: {avg_rating:.2f} / 5")


if __name__ == "__main__":
    main()