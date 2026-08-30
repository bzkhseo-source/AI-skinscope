# -*- coding: utf-8 -*-
"""
동일한 사진 파일로 analyze_skin_image()를 N회 연속 호출해, feature_scores
6개 항목과 overall_score의 최댓값-최솟값 편차를 측정한다 (같은 바이트의
파일이므로 촬영 조건 변수는 완전히 제거된 상태에서, Gemini 호출 자체의
재현성만 검증한다).

사용법 (PowerShell, venv 활성화 상태):
    python scripts\\test_score_reproducibility.py <이미지_경로> [반복횟수(기본5)]
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.services.vision_service import analyze_skin_image  # noqa: E402

FIELDS = ["pore", "elasticity", "moisture", "wrinkle", "pigmentation", "redness"]


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python scripts\\test_score_reproducibility.py <이미지_경로> [반복횟수]")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(f"파일을 찾을 수 없습니다: {image_path}")
        sys.exit(1)

    repeat = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    image_bytes = image_path.read_bytes()

    results = []
    for i in range(repeat):
        print(f"[{i + 1}/{repeat}] 분석 중...")
        result = analyze_skin_image(image_bytes, mime_type=mime_type)
        if not result.image_quality_ok:
            print(f"  경고: image_quality_ok=False ({result.quality_note}) — 편차 계산에서 제외")
            continue
        results.append(result)
        print(f"  overall_score={result.overall_score}, feature_scores={result.feature_scores.model_dump()}")

    if len(results) < 2:
        print("\n유효한(image_quality_ok=True) 결과가 2개 미만이라 편차를 계산할 수 없습니다.")
        print("실제 얼굴 사진으로 다시 시도해주세요.")
        return

    print(f"\n=== 편차 (최댓값-최솟값), 유효 결과 {len(results)}/{repeat}건 ===")
    for field in FIELDS:
        values = [getattr(r.feature_scores, field) for r in results]
        print(f"{field}: {values} -> 편차 {max(values) - min(values)}")

    overall_values = [r.overall_score for r in results]
    print(f"overall_score: {overall_values} -> 편차 {max(overall_values) - min(overall_values)}")


if __name__ == "__main__":
    main()
