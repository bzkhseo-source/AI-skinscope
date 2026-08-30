# 점수 재현성 테스트 로그

작성일: 2026-08-30
관련 문서: [`SCORE_CONSISTENCY_SPEC.md`](SCORE_CONSISTENCY_SPEC.md)

## 적용한 수정

`app/services/vision_service.py`에 `GEMINI_TEMPERATURE = 0.3`을 추가하고,
`_call_gemini()`의 `GenerateContentConfig`에 `temperature=GEMINI_TEMPERATURE`를
반영했다 (기존에는 temperature 미설정으로 모델 기본값(약 1.0 근처)이
적용되고 있었다).

## 재현성 테스트 스크립트

`scripts/test_score_reproducibility.py`를 새로 작성했다. 동일한 이미지
파일로 `analyze_skin_image()`를 N회(기본 5회) 연속 호출해 `feature_scores`
6개 항목과 `overall_score`의 최댓값-최솟값 편차를 출력한다.

```powershell
python scripts\test_score_reproducibility.py <이미지_경로> [반복횟수]
```

## 실행 결과

`frontend/icons/icon-192.png`(얼굴 사진이 아닌 아이콘 그래픽)로 스크립트
자체의 동작만 기계적으로 검증했다 — 예상대로 매번 `image_quality_ok=False`
로 판정되어 편차 계산에서 제외되는 것까지 정상 동작을 확인했다.

이 세션에는 실제 얼굴 사진 파일이 없어 직접 실행하지 못했으나, 사용자가
본인 증명사진으로 temperature=0.3 적용 **후** 상태를 5회 반복 실행해
결과를 제공했다 (2026-08-30).

## 실행 결과 (temperature=0.3, 동일 사진 5회 연속 요청)

| 항목 | 값(5회) | 편차(최댓값-최솟값) |
|---|---|---|
| pore | 64, 64, 64, 62, 65 | 3 |
| elasticity | 48, 50, 48, 58, 55 | 10 |
| moisture | 68, 68, 68, 66, 68 | 2 |
| wrinkle | 82, 80, 82, 74, 78 | 8 |
| pigmentation | 83, 82, 82, 78, 80 | 5 |
| redness | 70, 62, 70, 65, 65 | 8 |
| **overall_score** | 72, 70, 72, 70, 73 | **3** |

### 분석

- 사용자에게 가장 크게 노출되는 `overall_score`는 편차 3점으로 상당히
  안정적이다. temperature 미설정(기본값 약 1.0) 대비 개선 효과가 있을
  것으로 보이나, 수정 전 상태의 실측 데이터는 없어 정량적 "개선폭"까지는
  확인하지 못했다(수정 전/후 비교가 아닌, 수정 후 단독 측정치).
- 항목별로는 `elasticity`(10), `wrinkle`(8), `redness`(8)의 편차가 여전히
  눈에 띈다. `moisture`(2), `pore`(3)는 매우 안정적이다.
- **결과 화면의 4단계 상태 태그(80+ 매우양호/60+ 양호/40+ 주의/미만 관리
  필요) 기준으로 보면**: `elasticity`(48~58)는 5회 모두 "주의" 구간에
  머물러 태그 자체는 안 바뀌었다. 반면 `wrinkle`(74~82)과
  `pigmentation`(78~83)은 각각 한 번씩 79→80 경계를 넘나들어, 같은
  사진인데도 재촬영 시 "양호"↔"매우양호" 라벨이 바뀔 수 있는 사례가
  실측으로 확인됐다.

## 후속 조치: temperature 0.3 → 0.15, 재측정 (2026-08-30)

위 실측 결과(태그 경계를 넘는 사례 확인)를 근거로 사용자와 상의 후
`GEMINI_TEMPERATURE`를 0.15로 낮추고, 동일 사진·동일 방식으로 5회 재측정했다.

| 항목 | temp=0.3 편차 | temp=0.15 편차 | 변화 |
|---|---|---|---|
| pore | 3 | 3 | 동일 |
| elasticity | 10 | 12 | 악화 |
| moisture | 2 | 2 | 동일 |
| wrinkle | 8 | 6 | 개선 |
| pigmentation | 5 | 4 | 개선 |
| redness | 8 | 12 | 악화 |
| **overall_score** | **3** | **4** | 거의 동일(오차범위) |

### 결론: temperature를 더 낮추는 방향은 보류

0.3→0.15로 낮췄지만 개선/악화가 항목별로 엇갈렸고 `overall_score`도
사실상 변화가 없다. n=5의 작은 표본에서는 이 정도 흔들림 자체가
표본오차일 가능성이 높아, **temperature 자체가 지배적인 변수가 아니라는
뜻으로 해석한다.** 특히 `elasticity`·`redness`는 두 설정 모두에서
공통적으로 편차가 크게 나오는데, 이는 스펙 3순위가 짚었듯 애초에
2D 정지 이미지 한 장에서 탄력·붉은기를 판단하는 것 자체가 구조적으로
더 주관적이고 어려운 항목이기 때문일 가능성이 있다 — temperature를
0.05나 0으로 더 낮춰도 큰 개선을 기대하기 어렵고, 자유 문장(ai_summary
등)의 자연스러움만 해칠 위험이 크다.

**결정(2026-08-30, 최종)**: 0.3과 0.15 중 어느 쪽도 확실한 우위가 없다는
결과(둘 다 overall_score 편차 3~4점)에 따라, 자유 문장(ai_summary 등)의
자연스러움까지 고려해 `GEMINI_TEMPERATURE=0.2`로 절충해 최종 반영했다
(코드: `app/services/vision_service.py` 상수 정의부 주석 참고). temperature
추가 조정은 중단한다. 대신 스펙 2순위 원인(촬영 조건 자체의 편차)에
대응하는 실시간 촬영 가이드(밝기·거리 안내, 이미 구현 완료)가 실사용
환경에서는 더 실질적인 효과를 낼 가능성이 높다 — 동일 사진 재요청 테스트는
촬영 조건 변수를 원천 제거한 "모델 자체의 편차"만 보여주므로, 실사용
시나리오(매번 다른 조건으로 촬영)에서의 개선 여부는 이 가이드가 더 좌우할
것으로 판단된다.

스펙 2.2절(촬영 조건 실시간 안내: 밝기·거리 체크)은 이미 별도로 구현
완료했다 (`docs/PRODUCT_ROADMAP_V2.md` M 항목 참고).
