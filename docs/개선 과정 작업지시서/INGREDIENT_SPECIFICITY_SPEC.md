# 성분 추천 특이도(Specificity) 스코어링 — Claude Code 작업 지시서

작성: claude.ai 세션 (데이터 분석) | 작성일: 2026-08-27
대상 파일: `scripts/build_ingredient_map.py` (전체 교체 가능한 수준으로 아래에 새 버전 제공)
출력 파일: `app/data/concern_ingredient_map.json` (스키마에 필드 추가, 재실행 필요)

이 문서는 로드맵 항목(성분 추천, docs 문서 기준 G / 루트 문서 기준 I)의 데이터 준비
단계에서 발견된 문제를 고치기 위한 스펙이다. `docs/PRODUCT_ROADMAP_V2.md`와 함께 참고할 것.

---

## 1. 문제 (데이터로 확인됨)

현재 `concern_ingredient_map.json`은 각 고민(concern) 카테고리 안에서 성분을
`mention_count`(원시 언급 빈도) 기준으로만 랭킹한다. 그런데 실제 생성된 파일을
분석해보니:

- **ALOESIN(알로에신), HEXAPEPTIDE-2(헥사펩타이드-2), LONICERA CAERULEA FRUIT
  JUICE(댕댕이나무열매즙)** 세 성분이 **8개 고민 카테고리 전부(8/8)**에서 top-20 안에
  들고, 카테고리별 언급 비율도 평균 18~20%로 거의 동일하다.
- 즉 사용자의 `feature_scores`에서 약점이 모공이든 주름이든 붉은기든, 지금 로직대로
  추천하면 상위 성분이 대부분 이 3종으로 겹쳐서 나온다 — "고민별 차별화 추천"이라는
  기능 목적을 달성하지 못한다.
- 반면 언급 빈도 대신 "이 성분이 이 카테고리에서 유독 많이 언급되는 정도"(specificity/
  lift)로 재정렬해보면 더 그럴듯한 결과가 나온다. 예: redness(붉어짐)에서는 SULFUR,
  SODIUM THIOSULFATE, HEXAPEPTIDE-3/9/11 계열이 lift 1.5~1.8배로 부상(항균/진정 계열이라
  맥락상 합리적).
- 카테고리별 표본 크기 편차도 크다: pore 2,891건 vs sensitivity 7건, elasticity 49건,
  dryness 61건. 표본이 작은 카테고리는 어떤 랭킹 방식이든 신뢰도가 낮으므로 별도 표시가
  필요하다 (참고: sensitivity=7건은 스크립트 버그가 아니라 원본 데이터 자체의 희소성으로
  이미 확인됨).

## 2. 해결 방향

**specificity_score(성분, 카테고리) = 이 카테고리에서의 mention_pct ÷ 전체 코퍼스
기준 이 성분의 global_mention_pct**

- 1.0 = 이 성분은 어느 카테고리에서나 비슷하게 언급됨 (차별화 신호 없음 — 위 3종이 여기
  해당)
- 1.0보다 훨씬 크면 = 이 카테고리에서 유독 많이 언급됨 (차별화 신호로 유의미)

기존 `top_ingredients`(원시 빈도 랭킹)는 하위호환을 위해 그대로 두고, 새 필드
`top_ingredients_by_specificity`를 추가한다. 최종적으로 어느 리스트를 실제 추천에 쓸지는
이번 스크립트 범위 밖(로드맵 G/I 항목, vision_service.py 연동 시점)에서 결정한다.

## 3. 출력 JSON 스키마 변경

`concerns.<key>`에 필드 추가:

```python
reliable_specificity: bool   # record_count가 충분한지 (기준 아래 상수 참고)
top_ingredients: List[...]   # 기존과 동일한 구조 + global_mention_count/global_mention_pct/specificity_score 필드 추가(참고용, 정렬 기준은 그대로 mention_count)
top_ingredients_by_specificity: List[{
    inci_name, name_ko, mention_count, mention_pct,
    global_mention_count, global_mention_pct, specificity_score,
    efficacy, recommended_skin_type,
}]   # specificity_score 내림차순 정렬
```

## 4. 새 상수 (파일 상단, 기존 `TOP_N_PER_CONCERN` 옆에 추가)

```python
TOP_N_SPECIFICITY = 20
MIN_MENTION_COUNT_FOR_SPECIFICITY = 3   # 언급 1~2건짜리는 lift가 과도하게 튈 수 있어 제외
MIN_RECORD_COUNT_FOR_RELIABLE_SPECIFICITY = 30   # 이보다 레코드가 적은 카테고리는 신뢰도 낮음으로 표시
```

## 5. 스크립트 전체 교체안

기존 `build_concern_report()` 하나로 되어 있던 "순회+집계" 와 "top_ingredients로 자르기"를
분리한다. 이유: specificity 계산에는 **전체 코퍼스 대비 이 성분의 글로벌 등장 비율**이
필요한데, 기존 구조는 카테고리별로 순회를 끝내자마자 top 20으로 잘라버려서 다른
카테고리와 비교할 전역 카운터를 만들 수 없다. 그래서 1차로 8개 카테고리를 모두 순회해
`global_counter`를 완성한 뒤, 2차로 카테고리별 랭킹(raw + specificity)을 만드는 2-pass
구조로 바꾼다.

`import` 문 아래, 기존 `build_concern_report()` 함수를 아래 세 함수로 교체하고
`main()`도 교체한다 (그 외 `load_knowledge_map`, `_iter_jsonl_texts_from_dir`,
`_iter_jsonl_texts_from_zip`, `_extract_ingredients_from_record`, 상단 정규식/상수는
변경 없이 그대로 유지):

```python
def collect_concern_counts(concern_ko: str, knowledge_by_ko: dict) -> Optional[dict]:
    """해당 고민 카테고리의 레코드를 전수 순회해 성분 언급 Counter를 만든다.

    기존 build_concern_report()의 순회/집계 부분만 분리한 것 — top_ingredients로
    자르는 로직은 여기서 하지 않고 main()에서 raw/specificity 두 방식으로 각각
    수행한다 (specificity 계산에 전체 코퍼스 기준 global_counter가 필요하기 때문).
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
    """성분 하나에 대해 raw/specificity 랭킹 양쪽에서 공용으로 쓰는 출력 엔트리를 만든다."""
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
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n완료: 총 {global_total_records}건 레코드 분석, {len(concerns_output)}개 고민 카테고리")
    print(f"저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

파일 상단의 docstring, import, `DATASET_ROOT`/`KNOWLEDGE_XLSX`/`TRAINING_LABEL_DIR`/
`VALIDATION_LABEL_DIR`/`OUTPUT_PATH`, `TOP_N_PER_CONCERN`, `CONCERN_KEY_MAP`,
`INGREDIENT_PATTERN_A`/`_B`, `_normalize_inci`/`_normalize_ko`/`_cell`,
`load_knowledge_map`, `_iter_jsonl_texts_from_dir`, `_iter_jsonl_texts_from_zip`,
`_extract_ingredients_from_record`는 기존 그대로 두고, 위 3번 항목의 새 상수만 추가한다.
`build_concern_report()` 함수는 삭제하고 위 `collect_concern_counts()` +
`_format_ingredient_entry()` + 새 `main()`으로 교체한다.

## 6. 검증 체크리스트

재실행(`python scripts\build_ingredient_map.py`) 후 아래를 확인:

1. `total_records_analyzed`가 기존과 동일하게 9,000이 나오는지 (집계 방식만 바뀌고
   순회 대상은 그대로이므로 총 레코드 수는 변하지 않아야 함).
2. `concerns.redness.top_ingredients_by_specificity` 상위권에 SULFUR, SODIUM
   THIOSULFATE, HEXAPEPTIDE-9/11/3 계열이 올라오고, ALOESIN/HEXAPEPTIDE-2/LONICERA
   CAERULEA FRUIT JUICE는 순위가 크게 낮아지는지 (본 세션 근사 계산에서 이미 확인된
   패턴과 일치해야 함).
3. 8개 카테고리의 `top_ingredients_by_specificity` 상위 5개씩을 서로 비교했을 때,
   `top_ingredients`(raw) 기준으로 비교했을 때보다 카테고리 간 겹치는 성분 수가
   확연히 줄어드는지 (차별화 여부의 정량적 확인).
4. `reliable_specificity: false`로 표시되는 카테고리 목록 확인 — record_count가
   30 미만인 카테고리(예상: sensitivity=7, elasticity=49 근처, dryness=61 근처 중
   기준값에 따라)가 정확히 표시되는지.
5. `pore` 카테고리처럼 표본이 큰(2,891건) 카테고리에서 `top_ingredients`(raw)와
   `top_ingredients_by_specificity`가 여전히 유의미하게 다른 리스트인지 (specificity가
   raw와 똑같이 나온다면 계산 로직에 버그가 있다는 뜻).

## 7. 이번 변경 범위 밖 (다음 단계)

- `vision_service.py`/`SkinAnalysisResult`에 `recommended_ingredients` 필드를
  연동하는 것은 이번 스크립트 변경에 포함하지 않는다 (로드맵 G/I 항목, 별도 작업).
- `reliable_specificity: false`인 카테고리에 대해 실제 서비스에서 어떤 폴백을 쓸지
  (예: 전체 데이터 기준 top_ingredients로 대체, 또는 "데이터 부족" 안내와 함께 노출
  안 함)는 그 연동 시점에 별도로 설계한다.
