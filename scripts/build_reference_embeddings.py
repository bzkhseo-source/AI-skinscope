"""
AI Hub 안면부 피부질환 이미지 합성데이터의 근접샷(측면 폴더) 이미지를
gemini-embedding-2로 임베딩하여 RAG 참고 인덱스를 생성한다.

원본 이미지는 로컬에만 남고, 이 스크립트의 결과물(임베딩 숫자 벡터)만
프로젝트에 포함된다. AI Hub의 "원본 재배포 금지" 정책을 지키기 위함이다.

실행 전 준비:
- .env에 GEMINI_API_KEY 설정 확인
- D:\\AI_DB 아래 데이터셋이 다운로드되어 있어야 함

사용법 (PowerShell, venv 활성화 상태):
    python scripts\\build_reference_embeddings.py

중간에 중단되어도 다시 실행하면 이미 처리한 이미지는 건너뛰고 이어서 진행한다.
"""

import sys
import json
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from google import genai
from google.genai import types

from app.core.config import settings

# ===== 설정 =====
DATASET_ROOT = Path(r"D:\AI_DB\안면부 피부질환 이미지 합성데이터\Training\01.원천데이터")
IMAGES_PER_DISEASE = 100
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "reference_embeddings.json"
EMBEDDING_MODEL = "gemini-embedding-2"
OUTPUT_DIM = 768

# 폴더명(AI Hub 원본) -> 서비스에서 사용하는 표시명
DISEASE_FOLDERS = {
    "건선": "건선",
    "아토피": "아토피피부염",
    "여드름": "여드름",
    "지루": "지루피부염",
    "주사": "주사",
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

    done_ids = {r["source_id"] for r in records}

    for folder_key, display_name in DISEASE_FOLDERS.items():
        folder = DATASET_ROOT / f"TS_{folder_key}_측면"
        if not folder.exists():
            print(f"경고: 폴더 없음, 건너뜀 -> {folder}")
            continue

        image_files = sorted(
            [p for p in folder.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
        )[:IMAGES_PER_DISEASE]

        print(f"[{display_name}] {len(image_files)}장 처리 시작")

        for i, img_path in enumerate(image_files, start=1):
            source_id = img_path.name
            if source_id in done_ids:
                continue

            try:
                embedding = embed_image(client, img_path)
                records.append(
                    {
                        "disease": display_name,
                        "source_id": source_id,
                        "embedding": [round(v, 5) for v in embedding],
                    }
                )
                done_ids.add(source_id)
            except Exception as exc:  # noqa: BLE001
                print(f"  실패: {source_id} - {exc}")

            if i % 10 == 0:
                print(f"  {display_name}: {i}/{len(image_files)} 완료")
                OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

            time.sleep(0.3)

        OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        print(f"[{display_name}] 완료, 누적 {len(records)}건 저장")

    print(f"\n전체 완료: 총 {len(records)}건 저장 -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()