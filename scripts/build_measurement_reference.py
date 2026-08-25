"""
한국인 피부상태 측정 데이터의 스마트폰 정면 사진 + 실측값(JSON)을
gemini-embedding-2로 임베딩하여, 사용자 사진과 가장 닮은 실제 인물의
실측 수치를 근거로 활용하는 RAG 참고 인덱스를 생성한다.

원본 사진은 로컬에만 남고, 임베딩(숫자 벡터)과 실측 집계값만 저장한다.
실제 인물의 얼굴 사진이므로 원본은 절대 커밋/노출하지 않는다.

사용법 (PowerShell, venv 활성화 상태):
    python scripts\\build_measurement_reference.py

중간에 중단되어도 다시 실행하면 이미 처리한 인물은 건너뛰고 이어서 진행한다.
"""

import sys
import json
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from google import genai
from google.genai import types

from app.core.config import settings

DATASET_ROOT = Path(r"D:\AI_DB\한국인피부상태측정데이터\1.데이터")
# Training은 TS(원천)/TL(라벨), Validation은 VS(원천)/VL(라벨)로 접두어가 다르다.
SPLIT_PREFIXES = {
    "Training": {"photo": "TS", "label": "TL"},
    "Validation": {"photo": "VS", "label": "VL"},
}
SMARTPHONE_SUBDIR = "3. 스마트폰"  # 마침표 뒤 공백 포함 (실제 폴더명 그대로)
TARGET_COUNT = 300
EMBEDDING_MODEL = "gemini-embedding-2"
OUTPUT_DIM = 768
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "reference_measurements.json"


def _avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def load_person_profile(label_dir: Path, person_id: str) -> dict:
    """facepart 0~6 JSON 7개를 읽어 한 사람의 실측 집계값을 만든다."""
    moisture_vals, elasticity_vals, wrinkle_vals, pore_vals = [], [], [], []
    pigmentation_count = None

    for part in range(7):
        json_path = label_dir / f"{person_id}_03_F_{part:02d}.json"
        if not json_path.exists():
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue

        equipment = data.get("equipment") or {}

        if part == 0:
            pigmentation_count = equipment.get("pigmentation_count")

        for key, value in equipment.items():
            if "moisture" in key:
                moisture_vals.append(value)
            elif key.endswith("elasticity_Q0"):
                elasticity_vals.append(value)
            elif "wrinkle_Ra" in key:
                wrinkle_vals.append(value)
            elif key.endswith("_pore"):
                pore_vals.append(value)

    return {
        "moisture": _avg(moisture_vals),
        "elasticity": _avg(elasticity_vals),
        "wrinkle_ra": _avg(wrinkle_vals),
        "pore_count": _avg(pore_vals),
        "pigmentation_count": pigmentation_count,
    }


def embed_image(client: genai.Client, image_path: Path) -> list:
    image_bytes = image_path.read_bytes()
    mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type)],
        config=types.EmbedContentConfig(output_dimensionality=OUTPUT_DIM),
    )
    return result.embeddings[0].values


def main() -> None:
    client = genai.Client(api_key=settings.gemini_api_key)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    records = []
    if OUTPUT_PATH.exists():
        print(f"기존 결과 파일 발견, 이어서 진행합니다: {OUTPUT_PATH}")
        records = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    done_ids = {r["id"] for r in records}
    processed = len(records)

    for split, prefixes in SPLIT_PREFIXES.items():
        if processed >= TARGET_COUNT:
            break

        photo_root = DATASET_ROOT / split / "01.원천데이터" / prefixes["photo"] / SMARTPHONE_SUBDIR
        label_root = DATASET_ROOT / split / "02.라벨링데이터" / prefixes["label"] / SMARTPHONE_SUBDIR

        if not photo_root.exists():
            print(f"경고: 폴더 없음, 건너뜀 -> {photo_root}")
            continue

        person_dirs = sorted([p for p in photo_root.iterdir() if p.is_dir()])
        print(f"[{split}] 대상 인물 {len(person_dirs)}명 발견")

        for person_dir in person_dirs:
            if processed >= TARGET_COUNT:
                break

            person_id = person_dir.name
            if person_id in done_ids:
                continue

            photo_path = person_dir / f"{person_id}_03_F.jpg"
            label_dir = label_root / person_id

            if not photo_path.exists() or not label_dir.exists():
                continue

            profile = load_person_profile(label_dir, person_id)
            if profile["moisture"] is None and profile["elasticity"] is None:
                continue  # 유효한 실측값이 없으면 건너뜀

            try:
                embedding = embed_image(client, photo_path)
                records.append(
                    {
                        "id": person_id,
                        "embedding": [round(v, 5) for v in embedding],
                        "raw": profile,
                    }
                )
                done_ids.add(person_id)
                processed += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  실패: {person_id} - {exc}")

            if processed % 10 == 0:
                print(f"  진행: {processed}/{TARGET_COUNT}")
                OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

            time.sleep(0.3)

    OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    print(f"\n전체 완료: 총 {len(records)}건 저장 -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()