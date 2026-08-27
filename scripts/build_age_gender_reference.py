# -*- coding: utf-8 -*-
"""
AI Hub "한국인 피부상태 측정 데이터"의 meta_data.csv(성별·나이)와
measurement_data.csv(실측값)를 subject_no로 조인해, 연령대(10년 단위)
×성별 그룹별 실측 백분위를 계산한다.

기존 vision_service.py의 전체 인구 백분위(POPULATION_REFERENCE)는 1,072명
전체를 하나로 뭉쳐 계산한 것이었는데, 로드맵 G 항목("동년배 비교")을 위해서는
사용자가 나이를 입력했을 때 전체 인구 대신 같은 연령대(또는 연령대+성별)
그룹의 분포를 anchor로 쓸 수 있어야 한다.

사용법 (PowerShell, venv 활성화 상태):
    python scripts\\build_age_gender_reference.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DATASET_ROOT = Path(r"D:\AI_DB\한국인피부상태측정데이터\1.데이터\Other\메타데이터")
META_CSV = DATASET_ROOT / "meta_data.csv"
MEASUREMENT_CSV = DATASET_ROOT / "measurement_data.csv"

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent / "app" / "data" / "age_gender_reference.json"
)

# 그룹 표본이 이보다 적으면 신뢰도가 낮다고 보고 상위 그룹으로 fallback한다.
MIN_GROUP_SIZE = 15

# meta_data.csv의 한글 성별 값 -> API에서 쓰는 영문 키
GENDER_KO_TO_KEY = {"여성": "female", "남성": "male"}

# measurement_data.csv 원본 컬럼 -> 5개 anchor 지표로의 매핑.
# vision_service.py의 기존 5개 전체-인구 anchor(수분/탄력/주름/색소침착/모공)와
# 동일한 산출 방식을 그대로 재사용해, 연령대별 버전을 만든다.
METRIC_COLUMNS = {
    "moisture": ["수분_이마", "수분_오른쪽볼", "수분_왼쪽볼", "수분_턱"],
    "elasticity": ["탄력_이마_Q0", "탄력_오른쪽볼_Q0", "탄력_왼쪽볼_Q0", "탄력_턱_Q0"],
    "wrinkle": ["주름_왼쪽눈가_Ra", "주름_오른쪽눈가_Ra"],
    "pigmentation": ["스팟개수_정면"],
    "pore": ["모공개수_오른쪽볼", "모공개수_왼쪽볼"],
}

PERCENTILE_POINTS = [5, 25, 50, 75, 95]


def _row_metric_value(row: pd.Series, columns: list) -> float:
    values = [row[c] for c in columns if c in row and pd.notna(row[c])]
    return sum(values) / len(values) if values else None


def build_person_table() -> pd.DataFrame:
    meta = pd.read_csv(META_CSV, encoding="utf-8-sig")
    measurement = pd.read_csv(MEASUREMENT_CSV, encoding="utf-8-sig")

    merged = meta.merge(measurement, on="subject_no", how="inner")
    merged["gender_key"] = merged["성별"].map(GENDER_KO_TO_KEY)
    merged["age_band"] = (merged["나이"] // 10 * 10).astype(int)

    for metric, columns in METRIC_COLUMNS.items():
        merged[metric] = merged.apply(lambda row: _row_metric_value(row, columns), axis=1)

    return merged


def _percentiles_for_group(df: pd.DataFrame) -> dict:
    result = {"count": int(len(df))}
    for metric in METRIC_COLUMNS:
        series = df[metric].dropna()
        if series.empty:
            result[metric] = None
            continue
        result[metric] = {
            f"p{p}": round(float(series.quantile(p / 100)), 2) for p in PERCENTILE_POINTS
        }
    return result


def main() -> None:
    if not META_CSV.exists() or not MEASUREMENT_CSV.exists():
        raise SystemExit(f"메타데이터 파일을 찾을 수 없습니다: {DATASET_ROOT}")

    print("meta_data.csv + measurement_data.csv 로딩 및 조인 중...")
    df = build_person_table()
    print(f"  - 전체 {len(df)}명 (원본 meta {len(pd.read_csv(META_CSV, encoding='utf-8-sig'))}명 중 매칭)")

    overall = _percentiles_for_group(df)
    print(f"전체 인구 그룹: {overall['count']}명")

    by_age_band = {}
    for age_band, group in df.groupby("age_band"):
        stats = _percentiles_for_group(group)
        by_age_band[str(int(age_band))] = stats
        reliable = stats["count"] >= MIN_GROUP_SIZE
        print(f"  - {age_band}대: {stats['count']}명 (reliable={reliable})")

    by_age_gender = {}
    for (age_band, gender_key), group in df.groupby(["age_band", "gender_key"]):
        if gender_key is None:
            continue
        stats = _percentiles_for_group(group)
        key = f"{int(age_band)}_{gender_key}"
        by_age_gender[key] = stats
        reliable = stats["count"] >= MIN_GROUP_SIZE
        print(f"  - {age_band}대 {gender_key}: {stats['count']}명 (reliable={reliable})")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": (
            "AI Hub 한국인 피부상태 측정 데이터 meta_data.csv + measurement_data.csv "
            "(전체 1,072명, 전수분석)"
        ),
        "min_group_size": MIN_GROUP_SIZE,
        "overall": overall,
        "by_age_band": by_age_band,
        "by_age_gender": by_age_gender,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n완료: 저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
