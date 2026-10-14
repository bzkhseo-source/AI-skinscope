# 유사 실측사례 투명성 코멘트 설계 (방향 3)

작성일: 2026-10-14

## 0. 배경 — 왜 처음 계획(방향 1)을 버렸는가

분석에 쓰이는 인구 실측 프로필 RAG(`reference_measurements.json`)는 원래 Gemini
채점에 "참고 근거"를 주입하는 용도로만 쓰였다. 여기서 더 나아가, 이 유사 사례들의
실측 평균으로 Gemini의 `feature_scores`를 직접 보정(override)할 수 있을지 검토했다
(방향 1: 하이브리드 — 임베딩 유사도 기반 k-NN 추정값과 Gemini 채점이 크게 다르고
"신뢰도"가 높을 때만 결정론적으로 덮어쓰는 설계).

이 설계를 실제 코드에 반영하기 전에, leave-one-out(LOO) 백테스트로 먼저 검증했다.

## 1. Leave-one-out 백테스트 방법론

참조 풀의 각 사람을 한 명씩 "사용자"로 간주해, 자기 자신을 제외한 나머지 중
임베딩 코사인 유사도 top-5를 찾고, 그 top-5의 실측값 평균을 "예측값"으로 삼아
`_interp_score()`로 0~100점 점수로 변환한 뒤, 그 사람의 실제 점수와 비교해 오차를
측정했다.

## 2. 검증 결과

| 참조 풀 크기 | 평균 절대 오차(0~100점 척도) | 비고 |
| --- | --- | --- |
| 300명 | 약 11~22점 | 최초 설계 검토 시점의 참조 풀 |
| 965명 (3.2배 확장) | 약 12~21점 | `wrinkle_ra`만 소폭 개선, `elasticity`/`pore_count`는 소폭 악화, `moisture`/`pigmentation`은 변화 없음 |

주요 발견:

- `gemini-embedding-2`로 만든 얼굴 사진 임베딩들의 코사인 유사도는 0.92~0.98 범위에
  좁게 몰려 있어, 절대 유사도 값으로 "얼마나 닮았는지"를 구분하기 어렵다.
- "이웃 표준편차 / 전체 모집단 표준편차" 비율을 신뢰도 신호로 쓰려 했으나, 신호가
  약했고 `elasticity`에서는 오히려 역전(이웃끼리 값이 비슷할수록 오차가 더 큼)되어
  신뢰할 수 없었다.
- 참조 풀을 300명 → 965명으로 3.2배 늘려도 오차가 줄지 않았다. 즉 데이터 양이
  아니라 얼굴 사진 임베딩이라는 표현 방식 자체의 해상도 한계로 판단했다.

## 3. 의사결정 — 방향 3 채택

위 결과로 "DB 실측 데이터 기반 k-NN 추정으로 Gemini 점수를 보정"하는 방향은
신뢰도가 부족해 폐기했다. 대신 다음 방향으로 전환했다:

- Gemini가 산출한 `feature_scores`/`overall_score`는 전혀 수정하지 않는다.
- 분석 시 이미 조회한 인구 실측 프로필 RAG top-k 결과를 재사용해, 사용자 점수와
  그 유사 사례들의 실측 평균을 비교한 투명성 코멘트(`similar_case_note`)만
  결과에 추가로 노출한다.
- 코멘트는 점수를 바로잡는 근거가 아니라, "이 판단이 어떤 참고 데이터를 바탕에
  뒀는지"를 투명하게 보여주기 위한 추적성(traceability) 정보로 자리매김한다.

## 4. 구현 요약

- `app/services/vision_service.py`
  - `analyze_skin_image_with_evidence()`: 기존 `analyze_skin_image()`의 실제
    구현을 이 함수로 옮기고, `(SkinAnalysisResult, similar_measurements)` 튜플을
    반환하도록 확장. `analyze_skin_image()`는 하위 호환을 위해 `SkinAnalysisResult`만
    반환하는 얇은 래퍼로 유지.
  - `build_similar_case_note(feature_scores, similar_profiles)`: 기존
    `build_peer_comparison_note()`와 동일한 구조(가장 크게 벌어진 항목이
    ±8점 이상이면 해당 항목을 언급, 아니면 "전반적으로 비슷한 수준입니다")로
    유사 실측사례 그룹과 비교하는 한 줄 코멘트를 생성.
  - `redness`(붉은기)는 대응하는 실측 레퍼런스가 없어 비교 대상에서 제외.
- `app/schemas/agent.py`: `AgentResult.similar_case_note: Optional[str]` 필드 추가.
- `app/services/agent_service.py`: `analyze_skin_image_with_evidence()` 호출로
  전환하고, `build_similar_case_note()` 결과를 `AgentResult`에 연결.
- `frontend/index.html` / `app.js` / `styles.css`: 기존 동년배 비교 코멘트
  바로 아래에 같은 스타일로 노출, 두 코멘트가 함께 뜰 때 구분선이 중복되지
  않도록 처리.
- `scripts/build_measurement_reference.py`: 참조 풀을 300명 → 965명으로 확장
  (`TARGET_COUNT`). 이 확장은 채점 근거 주입 품질과 무관하게 유지되는 변경이며,
  위 LOO 백테스트 결과 재검증에도 이 확장된 풀을 사용했다.

## 5. 알려진 한계

- 유사 사례 비교는 `redness`를 제외한 5개 항목(모공·탄력·수분·주름·색소침착)에만
  적용된다.
- 참조 풀 확장이 점수 보정 정확도를 개선하지 못했다는 결론은 현재 임베딩
  모델(`gemini-embedding-2`) 기준이며, 다른 임베딩/피처 추출 방식으로는
  재검증하지 않았다.
