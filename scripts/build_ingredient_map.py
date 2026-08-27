"""
AI Hub "스킨케어 성분-효능 추천 데이터"를 전수 분석해, 피부 고민(concern)
카테고리별 추천 성분 순위표를 만든다.

사용법 (PowerShell, venv 활성화 상태):
    python scripts\\build_ingredient_map.py

데이터 구성 (D:\\AI_DB\\스킨케어 성분-효능 추천 데이터\\개방데이터 기준):
- "1.데이터\\Other\\메타데이터\\지식성분데이터.xlsx": 성분별 INCI명·한글명·효능 등
  마스터 정보 (2,465건). 실제 헤더가 1행에 있고 pandas가 0행을 헤더로 오인식하므로
  header=None으로 읽은 뒤 첫 행을 헤더로 직접 지정한다.
- "2.데이터(NIA)\\Training\\02.라벨링데이터\\TL_<고민명>\\<id>\\<id>.jsonl": 고민
  카테고리 8종별로 폴더가 이미 압축 해제되어 있다. 파일 하나당 JSON 레코드 1개.
- "2.데이터(NIA)\\Validation\\02.라벨링데이터\\VL_<고민명>.zip": Validation은 압축
  해제되지 않은 상태이므로 zipfile로 압축을 풀지 않고 바로 읽는다.

각 레코드의 answer/chain_of_thought 텍스트 안에는 "INCI명(한글명)" 형태로 추천
성분이 등장한다(예: "SULFUR(유황)"). 이를 정규식으로 추출해 고민 카테고리별
등장 빈도를 집계하고, 지식성분데이터의 효능 설명을 붙여 저장한다.
"""

import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

DATASET_ROOT = Path(r"D:\AI_DB\스킨케어 성분-효능 추천 데이터\개방데이터")
KNOWLEDGE_XLSX = DATASET_ROOT / "1.데이터" / "Other" / "메타데이터" / "지식성분데이터.xlsx"
TRAINING_LABEL_DIR = DATASET_ROOT / "2.데이터(NIA)" / "Training" / "02.라벨링데이터"
VALIDATION_LABEL_DIR = DATASET_ROOT / "2.데이터(NIA)" / "Validation" / "02.라벨링데이터"

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "concern_ingredient_map.json"

TOP_N_PER_CONCERN = 20
TOP_N_SPECIFICITY = 20
MIN_MENTION_COUNT_FOR_SPECIFICITY = 3  # 언급 1~2건짜리는 lift가 과도하게 튈 수 있어 제외
MIN_RECORD_COUNT_FOR_RELIABLE_SPECIFICITY = 30  # 이보다 레코드가 적은 카테고리는 신뢰도 낮음으로 표시

# 고민 카테고리 폴더명(한글) -> 앱 도메인에서 쓸 영문 key.
# 모공/주름/색소침착/붉은기/탄력은 기존 SkinFeatureScores 항목과 대응시키고,
# 나머지 2종(민감성, 건조/각질)은 이번 데이터셋에만 있는 신규 카테고리다.
CONCERN_KEY_MAP = {
    "모공": "pore",
    "여드름_뾰루지": "acne",
    "주름": "wrinkle",
    "미백(색소침착_기미_칙칙함)": "pigmentation",
    "붉어짐(홍조)": "redness",
    "피부처짐_탄력저하": "elasticity",
    "과각질_악건성": "dryness",
    "민감성(트러블_자극감)": "sensitivity",
}

# 실사용 데이터에서 확인된 두 가지 성분 표기 방식을 모두 인식한다.
# (A) "SULFUR(유황)"처럼 대문자 INCI명 뒤에 괄호로 한글명이 따라오는 방식
# (B) "'알로에신'"처럼 한글명만 작은따옴표로 감싸 표기하는 방식
INGREDIENT_PATTERN_A = re.compile(
    r"([A-Z][A-Z0-9]*(?:[ /\-][A-Z0-9]+)*)\(([^()]*?[가-힣][^()]*?)\)"
)
INGREDIENT_PATTERN_B = re.compile(r"'([가-힣][^']{1,30})'")


def _normalize_inci(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().upper()


def _normalize_ko(name: str) -> str:
    return re.sub(r"\s+", "", name).strip()


def _cell(row, col: str) -> str:
    """엑셀 셀 값을 안전하게 문자열로 정리한다. 빈 셀(NaN)은 빈 문자열로 취급한다."""
    value = row.get(col)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def load_knowledge_map() -> tuple:
    """지식성분데이터.xlsx를 로드해 (INCI -> 정보, 한글명 -> INCI) 두 매핑을 만든다.

    시트 0행은 빈 타이틀 행이고 실제 컬럼명은 1행(0-indexed)에 있어 header=None으로
    읽은 뒤 직접 지정한다. 컬럼명에 트레일링 공백(예: '한글명 ')이 섞여 있어
    strip()으로 정규화한다.
    """
    raw = pd.read_excel(KNOWLEDGE_XLSX, header=None)
    header = [str(c).strip() for c in raw.iloc[1]]
    data = raw.iloc[2:].copy()
    data.columns = header

    knowledge_by_inci = {}
    knowledge_by_ko = {}
    for _, row in data.iterrows():
        inci = _cell(row, "성분명(INCI)")
        name_ko = _cell(row, "한글명")
        if not inci:
            continue
        inci_key = _normalize_inci(inci)
        knowledge_by_inci[inci_key] = {
            "name_ko": name_ko,
            "efficacy": _cell(row, "효능"),
            "skin_type": _cell(row, "권장피부타입"),
        }
        if name_ko:
            knowledge_by_ko.setdefault(_normalize_ko(name_ko), inci_key)
    return knowledge_by_inci, knowledge_by_ko


def _iter_jsonl_texts_from_dir(folder: Path):
    """이미 압축 해제된 폴더(Training) 아래 모든 *.jsonl 파일의 레코드를 순회한다."""
    if not folder.exists():
        return
    for jsonl_path in folder.rglob("*.jsonl"):
        text = jsonl_path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            line = line.strip()
            if line:
                yield line


def _iter_jsonl_texts_from_zip(zip_path: Path):
    """압축 해제되지 않은 Validation zip 안의 *.jsonl 파일 레코드를 그대로 읽는다."""
    if not zip_path.exists():
        return
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not info.filename.endswith(".jsonl"):
                continue
            text = zf.read(info).decode("utf-8", errors="ignore")
            for line in text.splitlines():
                line = line.strip()
                if line:
                    yield line


def _extract_ingredients_from_record(raw_line: str, knowledge_by_ko: dict) -> set:
    """레코드 텍스트에서 (INCI키, 한글명) 쌍의 집합을 추출한다.

    형식 A("SULFUR(유황)")는 그대로 사용하고, 형식 B("'알로에신'")는 지식성분데이터의
    한글명 목록과 대조되는 경우에만 성분으로 인정한다(따옴표로 감싼 문구가 전부
    성분명은 아니므로, 알려진 성분명과 일치할 때만 채택해 오탐을 막는다).
    """
    try:
        record = json.loads(raw_line)
    except json.JSONDecodeError:
        return set()

    texts = []
    info = record.get("info", {})
    if isinstance(info.get("answer"), str):
        texts.append(info["answer"])
    for step in record.get("chain_of_thought", []) or []:
        if isinstance(step.get("content"), str):
            texts.append(step["content"])

    found = set()
    for text in texts:
        for inci_raw, name_ko in INGREDIENT_PATTERN_A.findall(text):
            found.add((_normalize_inci(inci_raw), name_ko.strip()))
        for name_ko in INGREDIENT_PATTERN_B.findall(text):
            inci_key = knowledge_by_ko.get(_normalize_ko(name_ko))
            if inci_key:
                found.add((inci_key, name_ko.strip()))
    return found


def collect_concern_counts(concern_ko: str, knowledge_by_ko: dict) -> Optional[dict]:
    """해당 고민 카테고리의 레코드를 전수 순회해 성분 언급 Counter를 만든다.

    top_ingredients로 자르는 로직은 여기서 하지 않고 main()에서 raw/specificity 두
    방식으로 각각 수행한다 (specificity 계산에 전체 코퍼스 기준 global_counter가
    필요하기 때문에, 먼저 전체 카테고리를 순회해 집계부터 끝내야 한다).
    """
    training_dir = TRAINING_LABEL_DIR / f"TL_{concern_ko}"
    validation_zip = VALIDATION_LABEL_DIR / f"VL_{concern_ko}.zip"

    counter: Counter = Counter()
    text_fallback: dict = {}
    record_count = 0

    for raw_line in _iter_jsonl_texts_from_dir(training_dir):
        record_count += 1
        for inci_key, name_ko in _extract_ingredients_from_record(raw_line, knowledge_by_ko):
            counter[inci_key] += 1
            text_fallback.setdefault(inci_key, name_ko)

    for raw_line in _iter_jsonl_texts_from_zip(validation_zip):
        record_count += 1
        for inci_key, name_ko in _extract_ingredients_from_record(raw_line, knowledge_by_ko):
            counter[inci_key] += 1
            text_fallback.setdefault(inci_key, name_ko)

    print(f"  - {concern_ko}: 레코드 {record_count}건, 고유 성분 {len(counter)}종 추출")

    if record_count == 0:
        return None

    return {"counter": counter, "text_fallback": text_fallback, "record_count": record_count}


def _format_ingredient_entry(
    inci_key: str,
    mention_count: int,
    record_count: int,
    knowledge_by_inci: dict,
    text_fallback: dict,
    global_counter: Counter,
    global_total_records: int,
) -> dict:
    """성분 하나에 대해 raw/specificity 랭킹 양쪽에서 공용으로 쓰는 출력 엔트리를 만든다.

    specificity_score = 이 카테고리에서의 mention_pct ÷ 전체 코퍼스 기준
    이 성분의 global_mention_pct. 1.0이면 어느 카테고리에서나 비슷하게
    언급된다는 뜻(차별화 신호 없음), 1.0보다 훨씬 크면 이 카테고리에서
    유독 많이 언급된다는 뜻(차별화 신호로 유의미).
    """
    info = knowledge_by_inci.get(inci_key, {})
    global_count = global_counter.get(inci_key, 0)
    global_pct = (
        round(global_count / global_total_records * 100, 2) if global_total_records else 0.0
    )
    mention_pct = round(mention_count / record_count * 100, 1)
    specificity_score = round(mention_pct / global_pct, 2) if global_pct > 0 else 0.0
    return {
        "inci_name": inci_key,
        "name_ko": info.get("name_ko") or text_fallback.get(inci_key, ""),
        "mention_count": mention_count,
        "mention_pct": mention_pct,
        "global_mention_count": global_count,
        "global_mention_pct": global_pct,
        "specificity_score": specificity_score,
        "efficacy": info.get("efficacy") or None,
        "recommended_skin_type": info.get("skin_type") or None,
    }


def main() -> None:
    if not KNOWLEDGE_XLSX.exists():
        raise SystemExit(f"지식성분데이터 파일을 찾을 수 없습니다: {KNOWLEDGE_XLSX}")

    print("지식성분데이터.xlsx 로딩 중...")
    knowledge_by_inci, knowledge_by_ko = load_knowledge_map()
    print(f"  - 성분 마스터 {len(knowledge_by_inci)}건 로드 완료")

    print("고민 카테고리별 전수 분석 중 (1차: 카운트 수집)...")
    concern_data: dict = {}
    global_counter: Counter = Counter()
    global_total_records = 0
    for concern_ko, concern_key in CONCERN_KEY_MAP.items():
        collected = collect_concern_counts(concern_ko, knowledge_by_ko)
        if collected is None:
            print(f"  - {concern_ko}: 데이터 없음, 건너뜀")
            continue
        concern_data[concern_key] = {"label_ko": concern_ko, **collected}
        global_counter.update(collected["counter"])
        global_total_records += collected["record_count"]

    print(f"전체 코퍼스: {global_total_records}건, 고유 성분 {len(global_counter)}종")
    print("카테고리별 랭킹 생성 중 (raw 빈도 + specificity)...")

    concerns_output = {}
    for concern_key, data in concern_data.items():
        counter = data["counter"]
        text_fallback = data["text_fallback"]
        record_count = data["record_count"]

        top_raw = [
            _format_ingredient_entry(
                inci_key, count, record_count, knowledge_by_inci, text_fallback,
                global_counter, global_total_records,
            )
            for inci_key, count in counter.most_common(TOP_N_PER_CONCERN)
        ]

        specificity_candidates = [
            _format_ingredient_entry(
                inci_key, count, record_count, knowledge_by_inci, text_fallback,
                global_counter, global_total_records,
            )
            for inci_key, count in counter.items()
            if count >= MIN_MENTION_COUNT_FOR_SPECIFICITY
        ]
        specificity_candidates.sort(
            key=lambda e: (e["specificity_score"], e["mention_count"]), reverse=True
        )
        top_specificity = specificity_candidates[:TOP_N_SPECIFICITY]

        concerns_output[concern_key] = {
            "label_ko": data["label_ko"],
            "record_count": record_count,
            "reliable_specificity": record_count >= MIN_RECORD_COUNT_FOR_RELIABLE_SPECIFICITY,
            "top_ingredients": top_raw,
            "top_ingredients_by_specificity": top_specificity,
        }

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": (
            "AI Hub 스킨케어 성분-효능 추천 데이터 "
            "(Training 전체 + Validation 전체, 전수분석, 샘플링 없음)"
        ),
        "total_records_analyzed": global_total_records,
        "concerns": concerns_output,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n완료: 총 {global_total_records}건 레코드 분석, {len(concerns_output)}개 고민 카테고리")
    print(f"저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
