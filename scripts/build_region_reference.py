# -*- coding: utf-8 -*-
"""
AI Hub "한국인 피부상태 측정 데이터"의 measurement_data.csv에서 부위별
(이마/왼쪽볼/오른쪽볼/턱) 수분·탄력·모공 실측 컬럼을 그대로 사용해,
전체 얼굴 평균이 아닌 "부위별" 백분위를 계산한다.

로드맵 H(부위별 세분화 분석)의 근거 데이터다. 확인 결과, 이 데이터셋에는
코(T존)·미간에 대응하는 장비 실측치가 존재하지 않는다(스마트폰 촬영
라벨의 facepart 2, 7번 슬롯이 모든 피험자에서 equipment=None으로 비어
있음 — 60명 표본 확인). 따라서 "코" 구역은 실측 anchor 없이 Gemini의
시각적 판단만으로 평가한다(기존 "붉은기" 항목과 동일한 처리 방식).

사용법 (PowerShell, venv 활성화 상태):
    python scripts\\build_region_reference.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

MEASUREMENT_CSV = Path(
    r"D:\AI_DB\한국인피부상태측정데이터\1.데이터\Other\메타데이터\measurement_data.csv"
)
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "region_reference.json"

PERCENTILE_POINTS = [5, 25, 50, 75, 95]

# region key -> {지표: CSV 컬럼명}. "nose"는 이 데이터셋에 실측 컬럼이 없어 제외.
REGION_COLUMNS = {
    "forehead": {"moisture": "수분_이마", "elasticity": "탄력_이마_Q0"},
    "cheek_l": {"moisture": "수분_왼쪽볼", "elasticity": "탄력_왼쪽볼_Q0", "pore": "모공개수_왼쪽볼"},
    "cheek_r": {"moisture": "수분_오른쪽볼", "elasticity": "탄력_오른쪽볼_Q0", "pore": "모공개수_오른쪽볼"},
    "chin": {"moisture": "수분_턱", "elasticity": "탄력_턱_Q0"},
}


def main() -> None:
    if not MEASUREMENT_CSV.exists():
        raise SystemExit(f"measurement_data.csv를 찾을 수 없습니다: {MEASUREMENT_CSV}")

    print("measurement_data.csv 로딩 중...")
    df = pd.read_csv(MEASUREMENT_CSV, encoding="utf-8-sig")
    print(f"  - 전체 {len(df)}명")

    regions_output = {}
    for region_key, metric_columns in REGION_COLUMNS.items():
        region_stats = {"count": int(len(df))}
        for metric, column in metric_columns.items():
            series = df[column].dropna()
            region_stats[metric] = {
                f"p{p}": round(float(series.quantile(p / 100)), 2) for p in PERCENTILE_POINTS
            }
        regions_output[region_key] = region_stats
        print(f"  - {region_key}: {list(metric_columns.keys())} 백분위 계산 완료")

    regions_output["nose"] = None
    print("  - nose: 이 데이터셋에 실측 컬럼 없음 (시각 판단 전용으로 표시)")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": (
            "AI Hub 한국인 피부상태 측정 데이터 measurement_data.csv "
            "(전체 1,072명, 전수분석, 부위별 컬럼 그대로 사용)"
        ),
        "note": (
            "코(nose)는 이 데이터셋에 대응하는 장비 실측 컬럼이 없어 "
            "anchor 없이 시각적 판단으로만 평가한다."
        ),
        "regions": regions_output,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n완료: 저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
