# 피부나이(skin_age) 신뢰성 문제 — 정정된 진단 및 수정 설계 (v2)

작성일: 2026-08-27
관련 로드맵 항목: G (나이·성별 입력 + 동년배 비교 + 피부나이) — `docs/PRODUCT_ROADMAP_V2.md`상 "완료"로 표시됨

## 0. v1 문서 정정

이전 버전(v1)은 "G 항목이 백엔드에 구현되어 있지 않다"는 전제로 작성됐다. 이는 검토 당시
스테이징된 코드 스냅샷이 오래된 버전이었기 때문에 발생한 오판이었다. 실제로는
`compute_skin_age()`, `build_peer_comparison_note()`, `_build_dynamic_population_text()`가
모두 `app/services/vision_service.py`에 구현되어 있고, `AgentResult`/`SkinRecord`에도
`age`/`gender`/`skin_age` 필드·컬럼이 이미 존재한다. 최신 코드를 다시 받아 확인한 결과,
**표본 부족이 원인이 아니라 두 함수 간의 "점수 스케일 불일치"가 원인**으로 특정됐다.
(`docs/PRODUCT_ROADMAP_V2.md` 121~132행: 12개 연령대×성별 그룹 모두 최소 51명 확보,
fallback 없이 전부 사용 가능 — 표본 크기는 문제가 아님이 문서상으로도 확인됨.)

## 1. 특정된 버그: 점수 스케일 불일치

**핵심 문제**: `feature_scores`(0~100)가 두 가지 서로 다른 기준으로 계산될 수 있는데,
`compute_skin_age()`와 `build_peer_comparison_note()`는 항상 "전체 인구 기준" 하나만
가정하고 있다.

- 사용자가 나이를 입력하면, `analyze_skin_image()`(651행)가
  `_build_dynamic_population_text(age, gender)`를 호출해 Gemini에게 **"50점 = 이 연령대
  그룹 자체의 중앙값"**이라는 기준으로 점수를 매기라고 지시한다(270~298행,
  `_build_dynamic_population_text` 내부 291~294행: "점수 50 = 이 그룹 중앙값 수준").
  즉 60대 사용자가 자기 나이 또래 대비 평범한 피부라면 feature_scores는 (60대 기준으로)
  50점 근처로 나온다.
- 그런데 `compute_skin_age()`(321행)가 유클리드 거리 비교 대상으로 쓰는
  `_age_band_score_profile()`(301행)은 각 연령대 그룹의 중앙값을 **항상 전체 인구
  백분위(`MOISTURE_PERCENTILES` 등 39~43행, 전 연령 통합)로 환산**한다. 피부 상태는
  나이가 들수록 전체 인구 기준 점수가 단조 감소하는 경향이 있으므로(젊을수록 전체
  인구 대비 고득점, 나이 들수록 저득점), 이 프로파일에서 "50점"에 해당하는 연령대는
  **표본 전체의 중심 연령대 단 하나**뿐이다.
- 결과: 나이를 입력한 사용자의 feature_scores는 "자기 나이 대비 평범하면 항상 50점
  근처"로 나오는데, `compute_skin_age()`는 이 50점을 "전체 인구 기준 50점"으로 잘못
  해석해 표본의 중심 연령대(예: 30~40대 어딘가)로 매칭시켜 버린다. **즉, 자기 나이
  대비 지극히 평범한 피부를 가진 사용자라도, 표본 중심 연령대보다 나이가 많으면
  거의 예외 없이 피부나이가 실제 나이보다 낮게 나오는 구조적 편향이다.** 테스터
  연령대가 표본 중심보다 높을수록(예: 4050세대) 체감하는 편차가 커진다.
- `build_peer_comparison_note()`(352행)도 동일한 가정 오류를 갖고 있다: 사용자의
  feature_scores(나이 입력 시 자기 연령대 상대 점수)를 `_interp_score(stats['p50'], ...)`
  (전체 인구 기준 환산)와 직접 비교(374행 `user_score - group_score`)하므로, 나이가
  표본 중심보다 많은 사용자는 "동년배보다 낮음"으로, 적은 사용자는 "동년배보다 우수함"으로
  구조적으로 편향될 가능성이 있다.

이것은 표본 크기·클램핑 부재의 문제가 아니라 **두 함수가 서로 다른 좌표계를 같은
좌표계로 착각하고 비교하는 설계 결함**이다. 표본이 아무리 많아도, 클램핑을 걸어도
근본 원인은 해결되지 않는다.

## 2. 수정 방향 (권장)

가장 단순하고 안전한 수정은 **feature_scores의 기준을 하나로 통일**하는 것이다. 즉,
Gemini에게 보내는 anchor 텍스트를 나이 입력 여부와 무관하게 **항상 전체 인구
`POPULATION_REFERENCE`로 고정**하고, "동년배 비교"는 이미 올바르게 구현되어 있는
`compute_skin_age()` / `build_peer_comparison_note()`의 사후 계산 로직에만 맡긴다.

### 2.1 핵심 수정 (1줄 수준)
`analyze_skin_image()` 651행:
```python
# 변경 전
population_reference = _build_dynamic_population_text(age, gender) or POPULATION_REFERENCE
# 변경 후
population_reference = POPULATION_REFERENCE
```
`_build_dynamic_population_text()`와 이를 호출하는 코드 경로는 더 이상 anchor 텍스트를
바꾸는 용도로 쓰지 않는다(완전히 제거하거나, 필요하면 "참고용 추가 정보"로만 프롬프트에
덧붙이되 "50점 = 이 그룹 중앙값" 같은 anchor 재정의 문구는 제거해야 한다).

### 2.3 이 수정의 부작용 (반드시 인지하고 있어야 함)

**이 수정은 skin_age뿐 아니라, 나이를 입력한 사용자가 보는 feature_scores(모공/탄력/
수분/주름/색소침착) 자체도 함께 바꾼다.** 두 값이 같은 좌표계를 쓰도록 고치는 것이
핵심이므로, 좌표계를 어느 쪽으로 통일하느냐에 따라 사용자가 보는 1차 점수도 달라지는
것은 필연적인 결과다.

- **현재(버그 있는 상태)**: 나이를 입력하면 "50점 = 내 또래 그룹의 중앙값"으로 채점되므로,
  나이와 무관하게 "내 또래 대비 평범"하면 항상 50점 근처가 나온다. 즉 지금은 고령
  사용자의 점수가 실제보다 관대하게(더 높게) 나오고 있었을 가능성이 크다.
- **수정 후**: "50점 = 전체 인구(전 연령 통합) 중앙값"으로 통일되므로, 표본 중심
  연령대보다 나이가 많은 사용자는 feature_scores가 **지금보다 낮아질 가능성이 높고**,
  표본 중심보다 어린 사용자는 **지금보다 높아질 가능성이 높다.** 나이 미입력 사용자는
  원래부터 전체 인구 anchor를 썼으므로 영향 없음.
- 점수가 낮아지면 `overall_score`가 `OVERALL_SCORE_SAFETY_THRESHOLD`(40, `agent_service.py`)
  아래로 떨어져 병원 방문 권장으로 전환되거나, 프론트의 4단계 배지(`featureScoreTier`:
  매우양호≥80/양호≥60/주의≥40/관리필요<40)가 한 단계 낮게 표시되는 사용자가 생길 수 있다.
- 다만 이는 새로운 문제를 만드는 게 아니라 **원래 기획 의도(`PLANNING.md` "점수화 근거":
  "인구 상위/하위 몇 % 수준"으로 판단)로 되돌리는 것**이다. "동년배 비교"라는 맥락은
  `peer_comparison_note`/`skin_age`가 별도로 담당하도록 설계돼 있었는데, 점수 자체까지
  또래 기준으로 다시 매겨버린 것이 이번 버그의 원인이었다.
- **권장**: 배포 전에 고령 테스터 몇 명의 점수가 수정 전후로 얼마나 달라지는지 확인하고,
  하락 폭이 체감상 크다면 "이 점수는 전체 연령 대비 기준이며, 동년배 대비는 아래 문구를
  참고하세요" 같은 안내 문구를 결과 화면에 추가하는 것을 고려한다.

이렇게 하면:
- `feature_scores`는 나이 입력 여부와 무관하게 항상 전체 인구 기준으로 일관되게 계산됨
- `compute_skin_age()`가 비교하는 `_age_band_score_profile()`과 동일한 좌표계를 쓰게 되어
  구조적 편향이 사라짐
- `build_peer_comparison_note()`의 `user_score - group_score` 비교도 올바르게 작동함
- "동년배 비교"라는 사용자 경험 자체는 그대로 유지됨 (peer_comparison_note가 이미 그
  역할을 함) — 오히려 이중으로 편향을 주던 부분만 제거되는 것

### 2.2 보조 안전장치 (수정 후에도 권장)
1. **연령대 상한 처리**: `_select_age_gender_group()`의 `age_band = min(max((age//10)*10,
   10), 60)` 및 `compute_skin_age()`가 순회하는 `by_age_band`의 최대 구간이 "60대"까지만
   있다면, 61세 이상 입력 시 피부나이가 구조적으로 65세를 넘을 수 없다. `age_gender_reference.json`에
   실제 몇 개 연령대 구간이 있는지 확인하고, 최고 연령대 구간과 입력 나이가 크게
   벌어지는 경우(예: 입력 나이가 최고 구간 대표값보다 10세 이상 많음) `skin_age_reliable:
   false` 플래그를 반환해 프론트에서 "참고용" 문구로 대체한다.
2. **극단치 클램핑**: `skin_age`와 입력 `age`의 차이가 비정상적으로 크면(예: ±20세 초과)
   `skin_age_reliable=false`로 표시한다. 2.1 수정 후에는 이런 극단치가 크게 줄어들
   것으로 예상되지만, 회귀 방지용 안전장치로 남겨두는 것을 권장한다.
3. **캘리브레이션 검증**: 수정 배포 후, 실제 나이를 아는 테스터 10명 이상으로
   "입력 나이 vs 산출된 피부나이"를 다시 수집해 편향이 해소됐는지 확인한다(자기 나이
   대비 평범한 스킨 상태의 테스터가 실제 나이 근처의 피부나이를 받는지 확인).

## 3. Claude Code 실행 문구

> `vision_service.py`의 `analyze_skin_image()` 651행에서
> `population_reference = _build_dynamic_population_text(age, gender) or POPULATION_REFERENCE`를
> `population_reference = POPULATION_REFERENCE`로 바꿔서, 나이 입력 여부와 무관하게 Gemini
> feature_scores 채점 anchor를 항상 전체 인구 기준으로 고정해줘. (원인: `compute_skin_age()`와
> `build_peer_comparison_note()`가 feature_scores를 항상 전체 인구 기준으로 가정하고
> `_age_band_score_profile()`/population percentile과 비교하는데, 나이 입력 시에는 Gemini가
> 그 연령대 자체 중앙값을 50점으로 채점해버려 두 함수의 좌표계가 어긋나는 게 "피부나이가
> 낮게 나온다"는 신뢰성 문제의 원인이었어.) `_build_dynamic_population_text()`와 그 호출부는
> 정리하거나 주석 처리해줘 — 더 이상 anchor 재정의 용도로 쓰지 않을 거야. 수정 후
> `age_gender_reference.json`의 연령대 구간이 몇 살까지 있는지 확인해서, 최고 연령대를
> 초과하는 입력에 대해 `skin_age_reliable=false` 플래그와 ±20세 초과 시 클램핑 처리를
> `compute_skin_age()`에 추가해줘. 마지막으로 실제 나이를 아는 테스터 데이터로 수정 전후
> 비교를 해서 편향이 줄었는지 확인해줘.
