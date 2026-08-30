# -*- coding: utf-8 -*-
"""
피부지식 챗봇(로드맵 L)의 RAG 참고 인덱스를 만든다.

두 소스를 문서 단위로 변환해 gemini-embedding-2(기존 인프라와 동일 모델)로
임베딩한다:
1. `app/data/concern_ingredient_map.json` — 성분별 효능 설명. 여러 고민
   카테고리의 top_ingredients(_by_specificity)에 중복으로 등장하는 성분은
   하나의 문서로 합친다(동일 성분 임베딩 중복 방지).
2. `app/data/skincare_faq.json` — 직접 작성한 스킨케어 FAQ 20~30개.

사용법 (PowerShell, venv 활성화 상태):
    python scripts\\build_knowledge_base.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from google import genai
from google.genai import types

from app.core.config import settings

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
INGREDIENT_MAP_PATH = DATA_DIR / "concern_ingredient_map.json"
FAQ_PATH = DATA_DIR / "skincare_faq.json"
OUTPUT_PATH = DATA_DIR / "knowledge_base_embeddings.json"

EMBEDDING_MODEL = "gemini-embedding-2"
OUTPUT_DIM = 768


def _collect_ingredient_documents() -> list:
    """concern_ingredient_map.json에서 고유 성분별 문서를 만든다."""
    if not INGREDIENT_MAP_PATH.exists():
        print(f"경고: {INGREDIENT_MAP_PATH} 없음, 성분 문서 생략")
        return []

    data = json.loads(INGREDIENT_MAP_PATH.read_text(encoding="utf-8"))
    seen = {}  # inci_name -> {"name_ko":..., "efficacy":..., "concerns": set()}

    for concern_key, concern in data.get("concerns", {}).items():
        label_ko = concern.get("label_ko", concern_key)
        for list_key in ("top_ingredients", "top_ingredients_by_specificity"):
            for item in concern.get(list_key, []):
                inci = item.get("inci_name")
                if not inci or not item.get("efficacy"):
                    continue
                entry = seen.setdefault(
                    inci, {"name_ko": item.get("name_ko", inci), "efficacy": item["efficacy"], "concerns": set()}
                )
                entry["concerns"].add(label_ko)

    documents = []
    for inci, info in seen.items():
        concerns_text = ", ".join(sorted(info["concerns"]))
        text = f"{info['name_ko']}({inci}) 성분 효능: {info['efficacy']} (관련 고민: {concerns_text})"
        documents.append({"source": "ingredient", "id": inci, "text": text})
    return documents


def _collect_faq_documents() -> list:
    if not FAQ_PATH.exists():
        print(f"경고: {FAQ_PATH} 없음, FAQ 문서 생략")
        return []

    faq = json.loads(FAQ_PATH.read_text(encoding="utf-8"))
    documents = []
    for i, item in enumerate(faq):
        text = f"Q: {item['question']}\nA: {item['answer']}"
        documents.append({"source": "faq", "id": f"faq_{i}", "text": text, "question": item["question"]})
    return documents


def _embed_text(client: genai.Client, text: str) -> list:
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=[text],
        config=types.EmbedContentConfig(output_dimensionality=OUTPUT_DIM),
    )
    return [round(v, 5) for v in result.embeddings[0].values]


def main() -> None:
    client = genai.Client(api_key=settings.gemini_api_key)

    ingredient_docs = _collect_ingredient_documents()
    faq_docs = _collect_faq_documents()
    all_docs = ingredient_docs + faq_docs
    print(f"성분 문서 {len(ingredient_docs)}개, FAQ 문서 {len(faq_docs)}개, 총 {len(all_docs)}개")

    records = []
    if OUTPUT_PATH.exists():
        print(f"기존 결과 파일 발견, 이어서 진행합니다: {OUTPUT_PATH}")
        records = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    done_ids = {r["id"] for r in records}

    for i, doc in enumerate(all_docs):
        if doc["id"] in done_ids:
            continue
        try:
            embedding = _embed_text(client, doc["text"])
            record = {"id": doc["id"], "source": doc["source"], "text": doc["text"], "embedding": embedding}
            if "question" in doc:
                record["question"] = doc["question"]
            records.append(record)
            done_ids.add(doc["id"])
        except Exception as exc:  # noqa: BLE001
            print(f"  실패: {doc['id']} - {exc}")

        if (i + 1) % 10 == 0:
            print(f"  진행: {i + 1}/{len(all_docs)}")
            OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

        time.sleep(0.2)

    OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n완료: 총 {len(records)}건 저장 -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
