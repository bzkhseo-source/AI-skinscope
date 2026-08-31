# 반복 촬영 시 점수 편차 문제 — 진단 및 수정 설계

작성일: 2026-08-30
증상: 테스터가 같은 사람이 연속으로 다시 촬영했을 때 점수(모공/탄력/수분/주름/
색소침착/붉은기, overall_score)가 눈에 띄게 달라진다는 의견.

---

## 1. 원인 진단 (근거 우선순위 순)

### 1순위 — Gemini 호출에 `temperature`가 설정되어 있지 않음 (가장 유력, 가장 쉬운 수정)

`app/services/vision_service.py` 599~613행 `_call_gemini()`:

```python
def _call_gemini(
    client: genai.Client, model: str, image_bytes: bytes, mime_type: str, system_prompt: str
) -> str:
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            system_prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SkinAnalysisResult,
        ),
    )
    return response.text
```

`GenerateContentConfig`에 `temperature`가 없어 모델 기본 샘플링 온도(보통 1.0
근처)로 매 호출마다 생성된다. 0~100 점수를 매기는 것처럼 **일관성이 핵심인
작업에 샘플링 온도가 높게 걸려 있는 상태** — 같은 사진을 그대로 다시 넣어도
점수가 흔들릴 수 있는 가장 직접적인 원인이다.

### 2순위 — 반복 촬영마다 사진 자체가 조금씩 다름

"다시 찍기"를 누르면 거리·각도·조명이 매번 미세하게 바뀐다. 이게 두 곳에
영향을 준다.
- `_embed_image()`로 만든 임베딩이 매번 달라져 `_retrieve_similar_cases()`/
  `_retrieve_similar_measurements()`가 뽑는 RAG top-5 자체가 바뀐다(302~311행
  `_build_rag_evidence_text`, 493~533행 `_build_measurement_evidence_text` 참고 —
  이 근거 텍스트가 프롬프트에 "강한 참고 근거로 사용하라"고 명시돼 있어 점수에
  실제로 영향을 준다).
- Gemini가 시각적으로 관찰하는 내용 자체도 조명/각도에 따라 달라진다.

`docs/user_test_results.csv`의 테스터 코멘트(58행)에도 "정면·좌우 측면 등 권장
촬영 방법과 예시 이미지가 있으면 좋겠다"는 피드백이 이미 있어, 촬영 조건
불일치가 실제 불만으로 이어졌다는 근거가 있다.

### 3순위 — `overall_score` 산출 방식 자체가 원래 변동성이 큰 설계

`SYSTEM_PROMPT_TEMPLATE`(145~146행 지침)에 "overall_score는 6개 항목의 가중
평균이 아니라... 종합적으로 판단한 점수"라고 명시돼 있어, 항목별 점수보다도
더 주관적 판단에 의존한다. 1순위(temperature)가 고쳐지면 이 변동성도 함께
줄어들 것으로 예상되지만, 구조적으로 원래 변동 여지가 있는 필드라는 점은
인지하고 있어야 한다.

### 4순위 — 촬영가이드(로드맵 B)가 정적 오버레이일 뿐 실시간 검증이 없음

화면의 점선 타원 가이드는 "이 안에 얼굴을 맞추라"는 시각적 안내이지, 실제
거리·밝기가 적절한지 자동으로 판단해주지는 않는다. 그래서 사용자가 매번
다른 조건으로 찍어도 그대로 제출된다.

---

## 2. 수정 설계

### 2.1 temperature 고정 (필수, 최우선)

`vision_service.py` 21~29행 근처 상수 정의부(`EMBEDDING_MODEL`, `EMBEDDING_DIM`,
`RAG_TOP_K` 옆)에 추가:

```python
GEMINI_TEMPERATURE = 0.3
```

완전히 0으로 고정하지 않는 이유: 점수 항목은 안정시키되, `ai_summary`/`ai_focus`/
`ai_detail` 같은 자유 문장까지 기계적으로 똑같이 반복되면 부자연스럽다. 0.3
정도가 "숫자는 안정적, 문장은 자연스러움"의 균형점이다. 배포 후 편차가 여전히
크면 0.1~0.2까지 낮추는 걸 재검토한다.

`_call_gemini()` 608~611행 수정:

```python
config=types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=SkinAnalysisResult,
    temperature=GEMINI_TEMPERATURE,
),
```

### 2.2 촬영 조건 실시간 안내 강화 (권장, 프론트엔드)

> ⚠️ 이 부분은 현재 `frontend/app.js`의 카메라 캡처 로직(`capturePhotoFromVideo()`
> 등)을 이번 세션에서 직접 열어보지 않아, 정확한 함수 위치·기존 얼굴 감지 구현
> 방식까지는 확인하지 못했다. Claude Code가 기존 코드 구조를 보고 아래 방향으로
> 적용해야 한다.

- **밝기 체크**: 캡처용 `<canvas>`에서 프레임 픽셀 데이터를 샘플링해 평균
  밝기(luminance)를 계산, 일정 임계값 미만이면 촬영 버튼 위에 "조금 더 밝은
  곳에서 찍어주세요" 안내를 실시간으로 띄운다. 촬영을 막지는 말고(강제 차단은
  사용자 이탈 유발) 경고만 준다.
- **거리 체크**: 로드맵 C(얼굴 자동 감지)에서 이미 얼굴 위치/크기를 계산하고
  있을 것이므로, 그 바운딩박스 크기 대비 프레임 비율로 "너무 가깝다/멀다"를
  판단해 같은 방식으로 안내한다. 새로 얼굴 인식 로직을 만들 필요는 없고, 기존
  C 구현의 출력값을 재사용한다.
- 두 안내 모두 촬영 자체를 막지 않는 **소프트 가이드**로 구현한다 — 목적은
  "매번 비슷한 조건으로 찍게 유도"이지, 촬영을 어렵게 만드는 게 아니다.

### 2.3 RAG top-k 안정화 (선택, 여유 있으면)

현재 `RAG_TOP_K = 5`로 top-5 단순 평균을 쓰는데, 사진이 조금만 달라져도 top-5
구성원이 바뀌면서 평균이 흔들릴 수 있다. 시간이 되면 top-8~10으로 넓히고
유사도 기반 가중평균(유사도가 낮은 항목은 가중치를 낮춤)으로 바꾸면 조금 더
안정적이다. 이번 배포에서는 필수는 아니다 — 2.1이 더 큰 효과를 낼 가능성이
높으므로 후순위로 둔다.

---

## 3. 검증 절차 (수정 효과 확인)

`docs/PLAN.md`의 강하연 담당 STEP(테스트 정리)에 아래 테스트를 추가한다.

1. 동일한 사진 파일 1장을 골라 `/analyze`에 **3~5회 그대로 재요청**한다(같은
   바이트의 파일이므로 촬영 조건 변수는 완전히 제거된 상태).
2. 수정 전(temperature 미설정 버전)과 수정 후(temperature=0.3) 각각에 대해
   feature_scores 6개 항목과 overall_score의 최댓값-최솟값 편차를 기록한다.
3. 수정 후 편차가 눈에 띄게 줄었는지 확인한다. 이 결과를
   `docs/SCORE_CONSISTENCY_TEST_LOG.md`로 정리한다.
4. 추가로, 실제 테스터 1~2명에게 짧은 시간 내 재촬영을 요청해 "같은 사람,
   다른 사진"일 때의 편차도 별도로 기록하면(2순위 원인 검증), 촬영가이드
   강화(§2.2)의 필요성을 데이터로 뒷받침할 수 있다.

---

## 4. Claude Code 실행 문구 (작업지시서)

> **1) [필수] temperature 고정**
> `app/services/vision_service.py`의 상수 정의부(21~29행 근처, `RAG_TOP_K = 5`
> 옆)에 `GEMINI_TEMPERATURE = 0.3`을 추가해줘. `_call_gemini()` 함수(599~613행)의
> `GenerateContentConfig(...)`에 `temperature=GEMINI_TEMPERATURE`를 추가해줘.
> 다른 로직은 건드리지 마.
>
> **2) [필수] 재현성 테스트**
> 같은 이미지 파일로 `/analyze`를 3~5회 연속 호출해서 feature_scores/overall_score
> 편차를 측정하는 간단한 스크립트나 테스트를 만들어줘(pytest든 수동 스크립트든
> 무방). 수정 전/후 편차를 비교해서 `docs/SCORE_CONSISTENCY_TEST_LOG.md`에
> 기록해줘.
>
> **3) [권장] 촬영 조건 실시간 안내**
> `frontend/app.js`의 카메라 캡처 로직을 확인해서, 캡처용 canvas의 평균 밝기가
> 낮으면 "조금 더 밝은 곳에서 찍어주세요" 안내를, 기존 얼굴 자동 감지(로드맵 C)
> 결과의 바운딩박스 크기가 너무 작거나 크면 "조금 더 가까이/멀리서 찍어주세요"
> 안내를 촬영 버튼 위에 실시간으로 띄워줘. 촬영 자체를 막지는 말고 안내만 줘.
>
> **4) [선택] RAG top-k 안정화**
> 시간 남으면 `RAG_TOP_K`를 8~10으로 늘리고, `_build_measurement_evidence_text()`
> 를 단순 평균 대신 유사도 가중평균으로 바꿔줘. 이번 배포 필수는 아니야.
>
> 완료되면 `docs/PRODUCT_ROADMAP_V2.md`에 이 수정 내역을 별도 항목(예: "M. 점수
> 재현성 개선")으로 추가해줘.
