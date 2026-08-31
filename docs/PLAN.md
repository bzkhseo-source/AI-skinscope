# AI-SkinScope 팀 프로젝트 시나리오 (PLAN)

작성일: 2026-08-31
과정: 2026 경남 코디세이(Gyeongnam Codyssey) AI 네이티브 과정 — Final Project(팀미션 3-3)

이 문서는 첨부된 미션 요구사항(「팀미션 3-3) AI 네이티브 Final Project 자율 주제」)을 4인 팀 구성으로 어떻게 충족했는지 정리한 팀 진행 시나리오입니다. 실제 구현·테스트·QA·배포는 이미 완료된 상태이며, 이 문서는 그 산출물을 미션이 요구하는 팀 협업 형태로 재구성한 것입니다.

---

## 1. 팀 구성 및 역할

미션 요건(3~5인, 역할 명확히 분담, 모든 팀원이 실질적으로 기여)에 따라 4인 팀으로 구성합니다.

| 역할 | 담당 업무 | 주요 산출물 |
| --- | --- | --- |
| 팀장 | 기획 총괄, 미션 요구사항 충족 여부 검토, 진행 관리, 최종 결과보고서·발표자료 작성 | `docs/Service기획서.md`, `docs/기능요구명세서.md` 검토·확정, 발표자료 |
| 팀원A (Backend/AI) | 백엔드·AI 파이프라인 전체 구현(비전 분석, RAG ×3, AI Agent, 나이·피부나이, 챗봇), 코드 품질 점검, 배포 | `app/` 전체, `docs/*_SPEC.md`, 배포(Vercel) |
| 팀원B (Frontend) | PWA UI 구현·리디자인, 설치 경험(iOS/Android) 개선, 결과 화면 시각 자산 반영 | `frontend/` 전체 |
| 팀원C (QA/Test) | 실사용자 테스트 운영·정리, 피드백-기능 매핑, 신뢰성 캘리브레이션 검증, 배포 최종 점검 | `docs/user_test_results.csv` 기반 분석, `docs/Result.md` |

4명 모두 코드·문서 커밋을 통해 실질적으로 기여하며, 아래 3장의 시나리오 순서대로 진행합니다.

---

## 2. Final Project 미션 요구사항 충족 매핑

| 미션 요건 | 충족 여부 | 근거 |
| --- | --- | --- |
| 생성형 AI/AI Agent가 핵심 기능 | ✅ | Gemini Vision 기반 분석 자체가 서비스 핵심 기능. `app/services/agent_service.py`가 점수 판단 → 병원 검색 도구 호출을 자율 결정 |
| 실사용자 5명 이상 테스트 | ✅ (21명, 58건 초과 달성) | `docs/user_test_results.csv` |
| 필수 기술 요소 2개 이상 (5종 중) | ✅ (4개 충족, 상회 달성) | 멀티모달(Gemini Vision), RAG(질환 유사사례·인구 실측 프로필·챗봇 지식베이스 3종), AI Agent(병원 검색 도구 호출), Long-term Memory(촬영 이력·동년배 비교) |
| 팀 3~5인, 역할 분담, 전원 기여 | ✅ | 1장 팀 구성표, 4장 담당자별 작업 경계 |
| 문제 정의·서비스 아키텍처 문서화 | ✅ | `docs/Service기획서.md`, `docs/기능요구명세서.md` |
| AI 활용 방식 문서화 | ✅ | `docs/기능요구명세서.md` 4장, `docs/*_SPEC.md` 각 스펙 문서 |
| README.md(개요/팀원역할/기술스택/실행방법/결과) | ✅ | `README.md` |
| Git 버전 관리 기록 | ✅ | GitHub 저장소 커밋 히스토리(5장 워크플로우 참고) |
| 외부 접근 가능한 배포 | ✅ | <https://ai-skinscope.vercel.app> (2026-08-30 접속 확인) |
| 실사용자 피드백 반영 | ✅ | `docs/Result.md` "피드백 → 기능 매핑" 참고 |
| AI 생성 콘텐츠 명시 | ✅ | 결과 화면 상시 고지, 챗봇 `is_ai_generated` 배지 |
| 개인정보 동의·안전 관리 | ✅ | 촬영 전 동의 체크박스, 암호화 저장, 삭제 요청 지원 (`docs/Service기획서.md` 8장) |

---

## 3. 진행 시나리오 (타임라인)

| 단계 | 담당 | 내용 |
| --- | --- | --- |
| 1. 기획 | 팀장 + 팀원A | 문제 정의, 페르소나, AI Hub 데이터 검토, 기술 스택 선정 → `docs/Service기획서.md` |
| 2. 핵심 파이프라인 구현 | 팀원A | Gemini Vision 연동, RAG ×2(질환 유사사례/인구 실측), AI Agent(병원 검색 도구 호출), DB 이력 저장 |
| 3. 1차 실사용자 테스트 | 팀원C | 초기 버전으로 테스트 진행, 피드백 수집 시작 → `docs/user_test_results.csv` |
| 4. 피드백 기반 확장 (로드맵 A~I) | 팀원A + 팀원B | 촬영 가이드, 결과 공유, AI 소견 구조화, 나이·동년배·피부나이, 부위별 분석, 성분 추천 — `docs/개선 과정 작업지시서/PRODUCT_ROADMAP_V2.md` |
| 5. 신뢰성 이슈 진단·수정 | 팀원A | 피부나이 과소 산출 버그 발견 → 원인 분석 → 수정 → `docs/개선 과정 작업지시서/SKIN_AGE_RELIABILITY_SPEC.md` |
| 6. 신규 기능 3종 추가 (J/K/L) | 팀원A | 자외선 지수, 퍼스널컬러 추천, 피부지식 챗봇(RAG) → `docs/개선 과정 작업지시서/FEATURE_ADDITIONS_SPEC.md` |
| 7. 점수 재현성 문제 진단·수정 | 팀원A | 반복 촬영 시 점수 편차 피드백 → temperature 고정 등 수정 → `docs/개선 과정 작업지시서/SCORE_CONSISTENCY_SPEC.md`, `docs/개선 과정 작업지시서/SCORE_CONSISTENCY_TEST_LOG.md` |
| 8. PWA 설치 경험 개선 | 팀원B | iOS/Android 홈 화면 설치 대응 → `docs/개선 과정 작업지시서/PWA_INSTALL_SPEC.md` |
| 9. 얼굴 다이어그램 이미지 교체 | 팀원B | 부위별 분석 화면의 손그림 SVG를 실제 일러스트 이미지로 교체 |
| 10. 이력 관리 확장 | 팀원A | 이력 개별 삭제 API, 시계열 변화 분석 API(선형회귀 기반 항목별 추세) 추가 |
| 11. 이력분석 리포트(AI 피드백) | 팀원A | "이력분석" 버튼 클릭 시 6개 항목+종합점수 그래프와 함께, 추세를 근거로 한 Gemini 생성 관리 피드백 제공. 스키마 변경 전 저장된 구버전 기록이 시계열 분석 전체를 실패시키던 결함 발견·수정 |
| 12. 최종 코드 QA | 팀장 + 팀원A | 전체 기능·코드 점검, 실결함 2건 발견·수정(카카오맵 예외처리, 챗봇 XSS) |
| 13. 배포 | 팀원A | Vercel 배포 → <https://ai-skinscope.vercel.app> |
| 14. 최종 문서화 | 팀장 + 팀원C | `README.md`, `docs/Service기획서.md`, `docs/기능요구명세서.md`, `docs/Result.md` 정리 |

---

## 4. 담당자별 작업 경계

| 담당 | 파일/영역 |
| --- | --- |
| 팀장 | `docs/PLAN.md`(본 문서), `docs/Service기획서.md`·`docs/기능요구명세서.md` 검토·확정, 발표자료 |
| 팀원A | `app/` 전체(백엔드·AI), `docs/*_SPEC.md`(스펙 문서), `scripts/`, 배포 설정 |
| 팀원B | `frontend/` 전체(PWA UI, 아이콘/이미지 자산, `manifest.json`, `service-worker.js`) |
| 팀원C | `docs/user_test_results.csv` 기반 분석, `docs/Result.md`, 캘리브레이션·배포 점검 로그 |

---

## 5. Git 협업 워크플로우

```bash
git checkout main && git pull origin main
git checkout -b feature/<담당자>-<작업내용>
# 작업 후
git add <변경 파일>
git commit -m "[역할] <type>: <내용>"   # type: feat/fix/docs/test
git push origin feature/<담당자>-<작업내용>
```

GitHub에서 Pull Request 생성 → 팀장 또는 관련 담당자 리뷰 → Merge. 커밋 메시지 접두사는 역할([팀장]/[팀원A]/[팀원B]/[팀원C])로 통일해 `git log --oneline --graph --all`에서 각자의 기여가 구분되도록 합니다.

---

## 6. 산출물 체크리스트

| 산출물 | 상태 | 위치 |
| --- | --- | --- |
| 기획서 | 완료 | `docs/Service기획서.md` |
| 기능 요구 명세서 | 완료 | `docs/기능요구명세서.md` |
| AI 서비스(구현+실사용자 테스트) | 완료 | `app/`, `frontend/`, `docs/user_test_results.csv` |
| GitHub 저장소(버전 관리) | 진행 | 팀원별 커밋 후 push 필요 (5장 워크플로우 참고) |
| 발표 자료 | 팀장 작성 예정 | `docs/Result.md`를 스크린샷 첨부 후 발표자료로 재구성 |
| 서비스 배포 | 완료 | <https://ai-skinscope.vercel.app> |
