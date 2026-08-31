# AI Skin Scope 기술적용 매뉴얼

> 본 문서는 AI-SkinScope의 시스템 기술 구조를 설명하는 내부 기술 자료입니다. 폴더/프로그램 단위의 역할과 기능, 그리고 AI Hub 공개 데이터셋을 통계적으로 가공해 이미지 분석 정확도를 높이는 방식을 중심으로 정리했습니다.
>
> 서비스 기획·요구사항은 [`docs/Service기획서.md`](docs/Service기획서.md), 팀 진행 계획은 [`docs/PLAN.md`](docs/PLAN.md), 기능 요구 명세는 [`docs/기능요구명세서.md`](docs/기능요구명세서.md)를 함께 참고하세요.

- 배포 주소: <https://ai-skinscope.vercel.app> (프론트) / <https://ai-skinscope.onrender.com> (백엔드 API)
- 기술 스택: FastAPI + SQLAlchemy(백엔드), Vanilla JS/HTML/CSS PWA(프론트, 프레임워크 없음), Google Gemini Vision/Embedding(AI)

---

## 목차

1. [시스템 아키텍처 개관](#1-시스템-아키텍처-개관)
2. [전체 폴더 트리](#2-전체-폴더-트리)
3. [백엔드(app/) 상세](#3-백엔드app-상세)
4. [프론트엔드(frontend/) 상세](#4-프론트엔드frontend-상세)
5. [참고 데이터 빌드 스크립트(scripts/) 상세](#5-참고-데이터-빌드-스크립트scripts-상세)
6. [문서·기획 자료](#6-문서기획-자료)
7. [이미지 분석 파이프라인 심층 해설 — AI Hub 데이터셋 통계 분석 기반](#7-이미지-분석-파이프라인-심층-해설--ai-hub-데이터셋-통계-분석-기반)
8. [배포 아키텍처](#8-배포-아키텍처)
9. [오류처리 및 예외처리](#9-오류처리-및-예외처리)

---

## 1. 시스템 아키텍처 개관

```
[브라우저/PWA]                [FastAPI 백엔드]                 [외부 서비스]
 frontend/index.html   ──HTTP──▶  app/routers/*        ──▶  Google Gemini
 (카메라 촬영·업로드)              │                          (Vision / Embedding)
                                  ▼
                          app/services/*  ──────────▶  카카오맵 로컬검색 API
                          (분석·전처리·RAG·               (병원 검색)
                           에이전트 판단 로직)      ──────────▶  OpenWeatherMap API
                                  │                          (자외선 지수)
                                  ▼
                          app/models + SQLite/PostgreSQL
                          (이력·공유링크 영속 저장)
                                  ▲
                          app/data/*.json
                          (AI Hub 데이터셋을 오프라인에서
                           통계 처리해 만든 참고 인덱스)
```

핵심 설계 원칙은 세 가지입니다.

1. **Gemini Vision 자체를 재학습(파인튜닝)하지 않는다.** 대신 AI Hub 공개 데이터셋을 오프라인에서 통계적으로 분석해 만든 "참고 근거(anchor, RAG 인덱스)"를 매 요청마다 프롬프트에 주입해 판단 기준을 보정한다.
2. **Agent가 최종 의사결정에 안전장치를 더한다.** Gemini의 판단을 그대로 신뢰하지 않고, `overall_score` 임계값 같은 규칙 기반 이중 확인을 거쳐 병원 방문 권장 여부를 결정한다.
3. **모든 외부 연동(병원 검색, UV 지수, RAG 임베딩)은 실패해도 전체 분석을 막지 않는다.** 각 서비스 모듈이 예외를 잡아 빈 값/폴백으로 degrade하도록 일관되게 설계되어 있다.

---

## 2. 전체 폴더 트리

```text
AI-SkinScope/
├── app/                                  # FastAPI 백엔드
│   ├── main.py                           # 앱 진입점, 라우터 등록, 경량 DB 마이그레이션
│   ├── core/
│   │   └── config.py                     # 환경변수 기반 설정(Settings)
│   ├── models/                           # SQLAlchemy ORM 모델 (DB 테이블 정의)
│   │   ├── database.py                   # 엔진/세션/Base, get_db() 의존성
│   │   ├── record.py                     # skin_records 테이블
│   │   └── share_link.py                 # share_links 테이블
│   ├── schemas/                          # Pydantic 스키마 (요청/응답 검증)
│   │   ├── vision.py                     # Gemini Vision 응답 스키마 (구조화 출력 계약)
│   │   ├── agent.py                      # Agent 최종 응답 스키마
│   │   ├── history.py                    # 이력·시계열·이력분석 리포트 스키마
│   │   ├── chat.py / feedback.py / share.py / uv.py
│   ├── routers/                          # API 엔드포인트
│   │   ├── analyze.py                    # POST /analyze (분석), 피드백/공유 발급
│   │   ├── history.py                    # 이력 조회/삭제, 시계열/이력분석 리포트
│   │   ├── share.py                      # 공유 링크 공개 조회
│   │   ├── uv.py                         # 자외선 지수 조회
│   │   └── chat.py                       # 결과 기반 챗봇 질의응답
│   ├── services/                         # 핵심 비즈니스 로직
│   │   ├── vision_service.py             # ★ Gemini Vision 분석 + 전처리 + RAG (7장 심층 설명)
│   │   ├── image_preprocessing.py        # ★ 화이트밸런스 보정/질감 강조/품질 사전평가 (신규)
│   │   ├── agent_service.py              # Agent: 병원 방문 판단, 도구 호출 오케스트레이션
│   │   ├── ingredient_service.py         # 성분 추천 (AI Hub 성분 데이터 기반)
│   │   ├── kakao_service.py              # 병원 검색 도구
│   │   ├── uv_service.py                 # 자외선 지수 조회/등급 분류
│   │   ├── chat_service.py               # 피부지식 챗봇 (RAG)
│   │   ├── memory_service.py             # 이력 CRUD, 시계열 통계 계산 (Long-term Memory)
│   │   ├── trend_analysis_service.py     # 이력분석 리포트용 AI 코칭 피드백 생성
│   │   └── share_service.py              # 공유 링크 발급/조회
│   └── data/                             # AI Hub 데이터를 전수분석해 만든 참고 인덱스(JSON)
│       ├── reference_embeddings.json     # 질환 이미지 임베딩 RAG 인덱스 (3.6MB)
│       ├── reference_measurements.json   # 실측 인물 임베딩 RAG 인덱스 (2.2MB)
│       ├── age_gender_reference.json     # 연령대×성별 백분위 참고 데이터
│       ├── region_reference.json         # 부위별(이마/볼/턱) 백분위 참고 데이터
│       ├── concern_ingredient_map.json   # 고민별 추천 성분 랭킹 (148KB)
│       ├── knowledge_base_embeddings.json# 챗봇 지식베이스 RAG 인덱스
│       └── skincare_faq.json             # 챗봇용 FAQ 원문
├── frontend/                             # PWA (프레임워크·번들러 없는 Vanilla JS)
│   ├── index.html                        # 메인 앱 화면 (촬영/결과/이력/챗봇 등 전체 UI)
│   ├── app.js                            # 전체 프론트 로직 (68개 함수, 1,600여 줄)
│   ├── styles.css                        # 전체 스타일
│   ├── share.html / share.js             # 공유 링크 전용 읽기 전용 뷰어 (독립 페이지)
│   ├── manifest.json                     # PWA 매니페스트
│   ├── service-worker.js                 # 오프라인 캐싱 (네트워크 우선 전략)
│   └── icons/                            # PWA 아이콘, 얼굴 다이어그램 이미지
├── scripts/                              # AI Hub 데이터 가공 스크립트 + 로컬 개발 도구
│   ├── build_reference_embeddings.py     # 질환 이미지 임베딩 RAG 인덱스 생성
│   ├── build_measurement_reference.py    # 실측 인물 임베딩 RAG 인덱스 생성
│   ├── build_age_gender_reference.py     # 연령대×성별 백분위 산출
│   ├── build_region_reference.py         # 부위별 백분위 산출
│   ├── build_ingredient_map.py           # 성분-효능 데이터 전수분석 → 추천 랭킹
│   ├── build_knowledge_base.py           # 챗봇 지식베이스 RAG 인덱스 생성
│   ├── crop_final_icons.py               # PWA 아이콘 크롭 유틸리티
│   ├── export_feedback.py                # DB → CSV 추출 (실사용자 테스트 집계용)
│   ├── serve_https.py                    # 로컬 HTTPS 테스트 서버 (모바일 카메라 테스트용)
│   ├── test_vision_local.py              # analyze_skin_image() 단발 로컬 테스트
│   └── test_score_reproducibility.py     # 동일 사진 반복 호출 재현성 측정
├── docs/                                 # 기획·스펙·테스트 로그
│   ├── PLAN.md, 기능요구명세서.md, Service기획서.md, Result.md
│   ├── user_test_results.csv             # 실사용자 테스트 원본 데이터
│   └── 개선 과정 작업지시서/              # 기능별 상세 설계 스펙 모음
├── README.md
├── requirements.txt
├── .env.example
└── AI Skin Scope 기술적용 매뉴얼.md       # 본 문서
```

---

## 3. 백엔드(app/) 상세

### 3.1 `app/main.py`

FastAPI 앱 진입점. `Base.metadata.create_all()`로 테이블을 생성하고, `_migrate_add_missing_columns()`가 Alembic 없이 SQLite/PostgreSQL 양쪽에 `ALTER TABLE`로 신규 컬럼(나이/성별/피부나이 등)을 추가하는 경량 마이그레이션을 수행합니다. `analyze`, `history`, `share`, `uv`, `chat` 5개 라우터를 등록하고 CORS를 전체 허용합니다.

### 3.2 `app/core/config.py`

`pydantic-settings`의 `Settings` 클래스로 `.env` 파일을 로드합니다. `gemini_api_key`(필수), `kakao_map_api_key`/`uv_api_key`(선택, 없으면 해당 기능만 조용히 비활성화), `database_url`, `gemini_primary_model`/`gemini_fallback_model`(모델 쿼터 초과 시 자동 전환용) 등을 관리합니다.

### 3.3 `app/models/` — SQLAlchemy ORM

| 파일 | 테이블 | 역할 |
| --- | --- | --- |
| `database.py` | — | 엔진/세션 팩토리, `get_db()` FastAPI 의존성 |
| `record.py` | `skin_records` | 분석 결과 전체를 `result_json`에 저장 + 조회용 컬럼(overall_score, age, skin_age, 만족도 등) |
| `share_link.py` | `share_links` | 공유 링크 토큰(`secrets.token_urlsafe`)과 만료시각 |

### 3.4 `app/schemas/` — Pydantic 스키마

| 파일 | 핵심 모델 | 역할 |
| --- | --- | --- |
| `vision.py` | `SkinAnalysisResult`, `SkinFeatureScores`, `RegionalScores`, `PersonalColorResult` | **Gemini 구조화 출력의 계약(response_schema)** — 이 스키마와 정확히 일치하는 JSON만 유효한 응답으로 허용 |
| `agent.py` | `AgentResult`, `HospitalInfo`, `IngredientRecommendation` | Agent가 최종적으로 프론트에 반환하는 전체 응답 |
| `history.py` | `HistoryResponse`, `TrendSeriesResponse`, `TrendAnalysisResponse` | 이력 목록, 전체 기간 시계열 분석, AI 코칭 리포트 |
| `chat.py` / `feedback.py` / `share.py` / `uv.py` | — | 각 기능별 요청/응답 검증 |

### 3.5 `app/routers/` — API 엔드포인트

| 파일 | 엔드포인트 | 설명 |
| --- | --- | --- |
| `analyze.py` | `POST /analyze` | 사진 업로드 → 분석 → 이력 저장. `feedback`/`share` 하위 엔드포인트 포함 |
| `history.py` | `GET /history/{user_id}`, `GET .../trend`, `GET .../trend-analysis`, `GET .../{record_id}`, `DELETE .../{record_id}` | 이력 목록/삭제/시계열/AI 리포트. `/trend`(무료)와 `/trend-analysis`(Gemini 호출, 유료 성격)를 분리해 자동 로드 시 비용이 발생하지 않도록 설계 |
| `share.py` | `GET /share/{token}` | 인증 없는 공개 조회. 사진·병원·성분 추천 등 민감 정보는 응답에서 제외 |
| `uv.py` | `GET /uv-index` | 위경도 기반 자외선 지수 조회 |
| `chat.py` | `POST /analyze/{record_id}/chat` | 분석 결과 맥락 + RAG 기반 챗봇 응답 |

### 3.6 `app/services/` — 핵심 로직

이미지 분석의 두 축(`vision_service.py`, `image_preprocessing.py`)은 내용이 방대해 **7장에서 별도로 심층 설명**합니다. 나머지 서비스는 다음과 같습니다.

| 파일 | 역할 |
| --- | --- |
| `agent_service.py` | Vision 분석 결과를 받아 `_decide_needs_dermatologist()`로 최종 판단(Gemini 판단 + `overall_score ≤ 40` 규칙의 이중 안전장치), 필요 시 병원 검색 도구를 호출하는 **Agent 오케스트레이션** |
| `ingredient_service.py` | 가장 취약한 항목(+여드름 의심 패턴)을 골라 `concern_ingredient_map.json`(AI Hub 성분 데이터 전수분석 결과)에서 상위 5개 성분을 매칭. 표본이 충분한 카테고리는 특이도(specificity/lift) 랭킹을, 부족한 카테고리는 원시 빈도 랭킹을 사용 |
| `kakao_service.py` | 카카오맵 로컬 검색 API로 반경 3km 내 피부과 검색 (Agent의 "도구") |
| `uv_service.py` | OpenWeatherMap UV Index 조회, WHO/EPA 5단계 기준으로 분류. 안내 문구는 Gemini 호출 없이 고정 테이블 사용(비용/실패 지점 최소화) |
| `chat_service.py` | 사용자 분석 결과 + `knowledge_base_embeddings.json`(성분 설명 + FAQ) RAG 검색 결과를 근거로 Gemini가 답변 생성. 의료 진단성 질문은 전문의 상담 안내로 전환 |
| `memory_service.py` | 이력 CRUD(`save_record`/`get_history`/`delete_record`), 최근 2건 비교(`compute_trend`), 전체 기간 선형회귀 추세(`build_trend_series`) — **Long-term Memory**의 핵심 |
| `trend_analysis_service.py` | `build_trend_series()`의 통계 결과를 근거로 Gemini에게 관리 코칭 피드백을 생성시킴 (자동 로드가 아닌 "이력분석" 버튼 클릭 시에만 호출) |
| `share_service.py` | 공유 토큰 발급/검증, 만료시간(`share_link_expiry_days`) 관리 |

### 3.7 `app/data/` — 참고 인덱스 (7장에서 상세 설명)

AI Hub 원본 데이터는 저장소에 포함하지 않고(재배포 금지 정책 준수), **오프라인에서 통계 처리한 결과물(백분위 수치, 임베딩 벡터, 랭킹 테이블)만** 이 폴더에 JSON으로 보관합니다.

---

## 4. 프론트엔드(frontend/) 상세

프레임워크·번들러 없이 순수 JS/HTML/CSS로 작성된 PWA입니다. `app.js`는 아래와 같이 68개 함수, 24개 섹션으로 구성되어 있습니다.

| 섹션 | 담당 기능 |
| --- | --- |
| 사용자 식별자 | localStorage 기반 익명 사용자 ID 관리 |
| 화면 전환 / 탭 전환 | SPA 방식 화면 전환 공통 헬퍼 |
| 카메라 | `getUserMedia`로 스트림 시작, `canvas.toBlob()`으로 JPEG(품질 0.9) 캡처 |
| 얼굴 자동 감지 + 자동 촬영 | 브라우저 내장 `FaceDetector` 우선 시도 → 미지원 시 MediaPipe Tasks Vision(CDN)으로 폴백. 가이드 타원 대비 얼굴 박스 비율/중심 거리로 정위치 판정, 1초 유지 시 자동 촬영 |
| 촬영 조건 실시간 안내 | 프레임을 40×30으로 초소형 리사이즈해 평균 밝기 계산(참고용 안내, 촬영을 막지 않음) |
| 나이/성별, 위치, 자외선 지수 | 선택 입력값 로컬 기억, 위치 기반 UV 카드 |
| 분석 요청 / 결과 렌더링 | `POST /analyze` 호출, 6개 항목 점수·부위별 분석·유사 패턴 등 렌더링 |
| 퍼스널컬러 | 참고용 컬러 팔레트 표시 |
| 결과 공유 | Web Share API/클립보드, 민감 정보 제외 |
| 이력 화면 / 상세보기 / 개별 삭제 | `GET/DELETE /history/*` 연동 |
| 변화 추이(시계열) / 이력분석 리포트 | `/history/{user}/trend`, `/trend-analysis` 연동, SVG로 직접 그래프 렌더링 |
| PWA 설치 배너 | `beforeinstallprompt` 이벤트 처리 |
| 피드백 | 만족도 1~5점 + 자유의견 제출 |
| AI에게 물어보기(챗봇) | 결과 화면에서 자유 질문 |
| 사용 방법 안내 팝업 | 최초 사용자 온보딩 |

`share.html`/`share.js`는 앱 본체와 완전히 분리된 **읽기 전용 공유 뷰어**로, 로그인·촬영·이력 등 앱 전용 로직 없이 공유 토큰으로 결과 요약만 표시합니다. `service-worker.js`는 네트워크 우선(network-first) 전략으로 오프라인 캐싱하되, `/analyze`·`/history`·`/share/`·`/uv-index`는 항상 네트워크로 보내 캐시 오염(다른 사용자 결과 노출 등)을 방지합니다.

---

## 5. 참고 데이터 빌드 스크립트(scripts/) 상세

AI Hub 원본 데이터셋(로컬 `D:\AI_DB\` 경로)을 읽어 `app/data/*.json` 참고 인덱스를 생성하는 **일회성 오프라인 배치 스크립트**들입니다. 개발자 PC에서 1회 실행 후 결과 JSON만 저장소에 커밋하며, 실행 로직의 통계적 방법론은 7장에서 상세히 설명합니다.

| 스크립트 | 입력 | 출력 |
| --- | --- | --- |
| `build_reference_embeddings.py` | 안면부 피부질환 이미지 합성 데이터 | `reference_embeddings.json` |
| `build_measurement_reference.py` | 한국인 피부상태 측정 데이터 (스마트폰 사진+실측값) | `reference_measurements.json` |
| `build_age_gender_reference.py` | 한국인 피부상태 측정 데이터 (meta+measurement 조인) | `age_gender_reference.json` |
| `build_region_reference.py` | 한국인 피부상태 측정 데이터 (부위별 실측 컬럼) | `region_reference.json` |
| `build_ingredient_map.py` | 스킨케어 성분-효능 추천 데이터 | `concern_ingredient_map.json` |
| `build_knowledge_base.py` | `concern_ingredient_map.json` + 자체 작성 FAQ | `knowledge_base_embeddings.json` |

그 외 `crop_final_icons.py`(아이콘 크롭), `export_feedback.py`(DB→CSV 추출), `serve_https.py`(모바일 카메라 테스트용 로컬 HTTPS 서버), `test_vision_local.py`/`test_score_reproducibility.py`(로컬 검증·재현성 측정 스크립트)는 개발/QA 보조 도구입니다.

---

## 6. 문서·기획 자료

`docs/` 폴더에는 서비스 기획서, 기능 요구 명세서, 팀 진행 계획(PLAN.md), 최종 결과 보고서(Result.md), 실사용자 테스트 원본(`user_test_results.csv`)이 있으며, `개선 과정 작업지시서/` 하위에는 기능별 상세 설계 스펙(UI 리뉴얼, 점수 재현성, 피부나이 신뢰도, PWA 설치, 성분 특이도 산출 등)이 정리되어 있습니다.

---

## 7. 이미지 분석 파이프라인 심층 해설 — AI Hub 데이터셋 통계 분석 기반

### 7.1 왜 "파인튜닝"이 아니라 "통계적 근거 주입"인가

AI-SkinScope는 Gemini Vision 모델 자체를 재학습하지 않습니다. 학생 프로젝트 규모에서 파인튜닝은 데이터 규모·비용·시간 대비 비효율적이며, 무엇보다 AI Hub 데이터셋 대부분이 **원본 재배포 금지** 정책을 갖고 있어 원본을 학습 파이프라인에 그대로 흘려보내는 방식 자체가 불가능합니다. 대신 다음 전략을 택했습니다.

> **AI Hub 데이터셋을 오프라인에서 전수 통계 분석 → 통계량(백분위, 랭킹, 임베딩 벡터)만 추출 → 매 분석 요청마다 프롬프트/RAG 근거로 주입해 Gemini의 판단을 실측 데이터 분포에 맞게 보정(anchor)한다.**

이 방식은 AI Hub의 "원본 미반출" 정책을 지키면서도, Gemini의 주관적 채점을 실제 한국인 피부 측정 통계에 정합시킬 수 있다는 장점이 있습니다.

### 7.2 활용한 AI Hub 데이터셋 3종

| 데이터셋 | dataSetSn | 활용 방식 |
| --- | --- | --- |
| 안면부 피부질환 이미지 합성 데이터 | 71863 | 질환 정의 원문 few-shot 기준 + 임베딩 유사도 RAG |
| 한국인 피부상태 측정 데이터 | 71645 | 전신/부위별/연령대별 백분위 anchor + 임베딩 유사도 RAG |
| 스킨케어 성분-효능 추천 데이터 | — (7.17GB, 텍스트+이미지) | 고민 카테고리별 성분 추천 랭킹(특이도 분석) |

의료 이미지 데이터(dataSetSn=34105, 오프라인 안심존 전용)는 학생 개인이 프로젝트 일정 내 접근 요건(IRB 통지서, 소속 증빙, 지정 물리 공간)을 충족할 수 없어 사용하지 않았습니다(`docs/Service기획서.md` 참고).

### 7.3 통계 처리 방법론

#### (1) 백분위 5구간 선형보간 스코어링

`한국인 피부상태 측정 데이터`의 `measurement_data.csv`(n=1,072)를 pandas로 전수 로드해, 항목별(수분/탄력/주름/색소침착/모공) 백분위 5개 지점(하위5%, 하위25%, 중앙값, 상위25%, 상위5%)을 계산합니다. Gemini는 사진만으로 장비 실측을 할 수 없으므로, 이 5개 지점을 `vision_service.py`의 `_interp_score()`가 **구간 선형보간(piecewise linear interpolation)**으로 0~100점에 매핑하는 anchor 텍스트를 프롬프트에 주입합니다.

```
점수 50 = 중앙값 수준, 점수 90 이상 = 상위 5% 우수 수준, 점수 10 이하 = 하위 5% 열악 수준
```

동일한 방법론을 **부위별**(이마/양볼/턱, `build_region_reference.py`)과 **연령대×성별 그룹별**(10년 단위 구간, `build_age_gender_reference.py`)로도 반복 적용해 `region_reference.json`/`age_gender_reference.json`을 생성합니다. 연령대×성별 그룹은 표본이 `MIN_GROUP_SIZE`(15명) 미만이면 연령대 단독 → 전체 인구 순으로 자동 fallback해 소표본 신뢰도 문제를 방지합니다.

코(T존)는 이 데이터셋에 대응하는 장비 실측 슬롯이 전 피험자에서 비어 있음을 60명 표본으로 직접 확인해, anchor 없이 시각적 판단만 쓰도록 명시했습니다 — "데이터가 없으면 있는 척하지 않는다"는 원칙을 코드 주석에도 남겨두었습니다.

#### (2) 임베딩 코사인 유사도 기반 RAG

두 데이터셋(질환 이미지, 실측 인물 사진)을 `gemini-embedding-2`(768차원)로 사전 임베딩해 `reference_embeddings.json`/`reference_measurements.json`을 만듭니다. 분석 요청이 들어오면:

1. 사용자 사진을 동일 모델로 1회 임베딩
2. 참고 인덱스 전체와 **코사인 유사도**를 계산 (`_cosine_similarity()`, 외부 벡터DB 없이 순수 계산 — 표본 규모가 수백 건 수준이라 충분히 실시간 처리 가능)
3. 상위 5건(`RAG_TOP_K`)을 추출해:
   - 질환 데이터셋 → 라벨 분포(예: "여드름 3/5건, 지루피부염 2/5건")를 `suspected_patterns` 판단 근거로 제공
   - 실측 인물 데이터셋 → 실제 실측 평균값을 (1)의 백분위 함수로 환산해 "닮은 사람들의 실측 결과"로 제공

원본 얼굴 사진은 로컬에만 남기고 **임베딩 벡터와 집계 통계만** 저장소에 포함해, 실제 인물 사진 재배포 문제를 원천 차단했습니다.

#### (3) 성분 추천 특이도(Specificity/Lift) 분석

`스킨케어 성분-효능 추천 데이터`(Training+Validation 전수, 샘플링 없음)의 `answer`/`chain_of_thought` 텍스트에서 정규식으로 "INCI명(한글명)" 패턴을 추출해 고민 카테고리(8종)별 언급 빈도를 집계합니다. 단순 빈도 1위 성분은 모든 카테고리에서 겹치는 경향이 있어, **해당 카테고리에서 유독 많이 언급되는 정도(specificity/lift)**로 재랭킹합니다. 언급 3건 미만은 제외(`MIN_MENTION_COUNT_FOR_SPECIFICITY`), 레코드 30건 미만 카테고리는 `reliable_specificity=false`로 표시해 서비스단에서 원시 빈도 랭킹으로 자동 대체됩니다 — 통계적으로 불안정한 소표본 랭킹을 사용자에게 신뢰도 높은 결과처럼 보여주지 않기 위한 안전장치입니다.

#### (4) 시계열 추세: 최소자승 선형회귀

이력 화면의 "변화 추이"는 저장된 모든 기록의 `feature_scores`를 시점 인덱스(0..n-1) 대비 **최소자승법(least squares)**으로 기울기를 계산합니다(`memory_service._linear_slope()`). 최근 2건만 비교하던 기존 `compute_trend()`와 달리 전체 기록을 반영해 사진 한 장의 우연한 편차에 덜 흔들리며, 기울기 절대값이 `TREND_SLOPE_EPSILON`(0.5) 이하면 "변화 없음(stable)"으로 분류합니다.

### 7.4 이미지 전처리 파이프라인 (신규, `image_preprocessing.py`)

통계적 anchor 보정만으로는 **촬영 환경(조명색 편차)에 따른 입력 자체의 편차**를 줄일 수 없어, Gemini 호출 직전에 3단계 전처리를 추가했습니다. 전체 흐름은 다음과 같습니다.

```
업로드 이미지
   │
   ▼
① 사전 품질 평가 (assess_image_quality)
   블러(라플라시안 분산) / 평균밝기 / 암부·명부 비율 계산
   │
   ├─ 암부·명부 97% 이상(극단적 실패) → Gemini 호출 없이 즉시 재촬영 안내 반환
   │
   ▼ (정상 범위)
② 화이트밸런스 보정 (correct_white_balance)
   gray-world 보정을 40%만 부분 적용 + 채널별 보정폭 ±15% 제한
   │
   ▼
③ 질감 강조본 생성 (enhance_texture)
   HSV의 밝기(V) 채널에만 언샤프마스킹, 색상(H/S)은 원본 유지
   │
   ▼
Gemini Vision에 원본 임베딩(RAG용, 미보정) + 보정본 + 질감강조본 2장을 함께 전달
```

**왜 완전한 gray-world 보정을 쓰지 않는가**: gray-world 가정은 "장면 평균색은 무채색"이라는 전제인데, 얼굴 클로즈업 사진의 평균색은 원래 살구빛입니다. 완전 적용하면 redness/pigmentation 판단에 필요한 자연스러운 피부 붉은기까지 지워버려 오히려 정확도를 해칩니다. 그래서 보정 강도를 40%로 댐핑하고 채널별 보정 계수를 0.85~1.15로 clamp해, "명백한 조명색 편차만 완화하고 피부 톤 자체는 보존"하도록 설계했습니다. 자체 유닛테스트로 "색 편차는 줄이되 R>G>B(따뜻한 피부톤) 순서는 유지된다"를 직접 검증했습니다.

**왜 그레이스케일이 아닌 HSV V채널 강조인가**: `redness`, `pigmentation` 두 점수 항목과 4종 질환 패턴(건선/아토피/지루피부염/주사) 판정이 모두 색상 정보에 의존합니다. 그레이스케일 변환은 이 근거를 통째로 제거하므로, 색상(H/S)은 그대로 두고 밝기(V) 채널에만 언샤프마스킹+오토컨트라스트를 적용해 모공·주름 등 질감만 강조하는 방식을 택했습니다. Gemini에는 이 보조 이미지를 "질감 확인 전용, 색상 판단에는 쓰지 말 것"이라는 명시적 지시와 함께 전달합니다.

**RAG 임베딩은 원본을 그대로 사용**: 참고 인덱스(`reference_embeddings.json` 등)가 AI Hub 원본 이미지를 무보정 상태로 임베딩해 만들어졌기 때문에, 질의 이미지도 무보정 원본으로 임베딩해야 벡터 공간의 정합성이 유지됩니다. 전처리된 이미지로 임베딩하면 오히려 RAG 유사도 검색 품질이 떨어질 수 있어, 임베딩 단계만 원본 바이트를 그대로 사용하도록 분리했습니다.

**장애 허용(graceful degradation)**: 전처리 자체가 실패해도(손상된 파일 등) 예외를 잡아 원본 이미지 1장으로 기존 방식대로 폴백합니다 — 신규 기능 추가로 전체 분석 파이프라인이 죽는 일이 없도록 설계했습니다.

### 7.5 스코어링 로직 요약

- **feature_scores anchor는 항상 전체 인구 기준으로 고정**: 나이를 입력해도 anchor 자체는 바꾸지 않습니다. anchor를 연령대별로 바꾸면 `compute_skin_age()`/`build_peer_comparison_note()`가 서로 다른 좌표계를 같은 좌표계로 착각해 "나이를 입력하면 피부나이가 비정상적으로 낮게 나오는" 버그가 발생했던 이력이 있어(`docs/개선 과정 작업지시서/SKIN_AGE_RELIABILITY_SPEC.md`), "동년배 비교"는 별도 함수가 전담하도록 관심사를 분리했습니다.
- **Gemini 판단 + Agent 규칙의 이중 안전장치**: `agent_service._decide_needs_dermatologist()`는 Gemini가 `needs_dermatologist=false`를 반환해도 `overall_score ≤ 40`이면 강제로 병원 방문 권장으로 상향 조정합니다.
- **image_quality_ok 판정은 "관대하게"가 원칙**: 프롬프트가 명시적으로 관대한 판정을 지시하며, 신규 사전 품질 필터도 동일 원칙(극단적 경우만 차단)을 따릅니다 — 모호한 사진까지 알고리즘이 걸러내면 정상 사진을 오탐할 위험이 더 크다고 판단했기 때문입니다.

---

## 8. 배포 아키텍처

| 구성요소 | 플랫폼 | 비고 |
| --- | --- | --- |
| 프론트엔드(PWA) | Vercel | 정적 파일 배포, `index.html`/`share.html` 진입점 |
| 백엔드(FastAPI) | Render | `gemini_primary_model` 쿼터 초과 시 `gemini_fallback_model`로 자동 전환 |
| 데이터베이스 | SQLite(로컬 개발) / PostgreSQL(Render, `DATABASE_URL` 환경변수로 전환) | |
| 외부 API | Google Gemini, 카카오맵 로컬검색, OpenWeatherMap | 카카오맵/UV는 키 미설정 시 해당 기능만 조용히 비활성화 |

---

## 9. 오류처리 및 예외처리

이 프로젝트는 "AI 응답 실패", "외부 API 오류", "참고 데이터 누락"이 전체 서비스를 멈추지 않도록 각 계층에서 예외를 잡아 안전한 값으로 대체(degrade)하는 방식을 일관되게 적용했습니다. 아래는 실제 코드에 반영된 예외처리 설계와, 개발 과정에서 발견되어 수정된 대표 버그를 정리한 것입니다.

### 9.1 외부 API 연동 실패 대응 (Graceful Degradation)

서비스 핵심 기능(사진 분석)에 영향을 주지 않는 부가 기능은, 연동 API가 실패해도 예외를 잡아 "빈 값/숨김 처리"로 조용히 대체합니다.

| 연동 대상 | 실패 상황 | 처리 방식 |
| --- | --- | --- |
| 카카오맵 병원 검색 (`kakao_service.py`) | 네트워크/HTTP 오류(`httpx.HTTPError`) 또는 200 응답이지만 예상과 다른 JSON 구조(`KeyError`/`ValueError`/`TypeError`/`AttributeError`) | 예외를 잡아 빈 병원 목록(`[]`) 반환 — Agent는 "병원 정보를 찾지 못함"으로만 처리하고 분석 결과 자체는 정상 반환 |
| OpenWeatherMap 자외선 지수 (`uv_service.py`) | API 키 미설정, HTTP 오류, 응답 파싱 실패 | `None` 반환 → 프론트가 UV 카드를 렌더링하지 않고 그냥 숨김 (필수 기능이 아니므로 사용자에게 오류를 노출하지 않음) |
| Gemini 이미지/질문 임베딩 (`vision_service.py`, `chat_service.py`) | 임베딩 API 호출 실패 | 예외를 잡아 `user_embedding=None`으로 두고, 이후 RAG 조회 함수들이 `None`을 감지해 빈 근거로 진행 (분석 자체는 anchor 텍스트만으로 계속 진행) |

이 계층의 공통 원칙은 **"부가 기능의 실패가 핵심 기능(피부 분석 결과 반환)을 막지 않는다"**입니다. 예외를 상위로 전파하지 않고, 각 서비스 함수 경계에서 잡아 안전한 기본값으로 변환합니다.

### 9.2 참고 데이터(AI Hub 인덱스) 누락 대응

`app/data/*.json`(AI Hub 데이터를 전수분석해 만든 참고 인덱스)이 배포 환경에 없는 경우에도 서버가 죽지 않도록, 각 로더 함수가 파일 존재 여부를 먼저 확인합니다.

- 파일이 없으면 `logger.warning()`으로 경고만 남기고 빈 리스트/빈 딕셔너리를 캐싱해, 이후 호출에서 매번 디스크를 다시 확인하지 않도록 처리
- RAG 조회 함수(`_retrieve_similar_cases`, `_retrieve_similar_measurements` 등)는 참고 인덱스가 비어 있으면 즉시 빈 결과를 반환해, Gemini 프롬프트에는 해당 근거 문단만 빠진 채로 정상 진행
- 연령대×성별 백분위(`age_gender_reference.json`)가 없거나 표본이 부족하면 전체 인구 anchor로 자동 대체

개발 과정에서는 이 경로와 관련해 **오탐 사례**도 있었습니다 — 참고 인덱스 파일이 실제로는 존재하는데, 작업 환경에 해당 파일이 아직 동기화되지 않은 상태에서 "파일이 없다"고 잘못 판단한 경우입니다. 코드 자체는 정상 동작했지만, 이 사례는 참고 데이터 존재 여부를 점검할 때 반드시 실제 배포/실행 환경에서 직접 확인해야 한다는 교훈을 남겼습니다.

### 9.3 이미지 전처리 파이프라인의 예외처리 (`image_preprocessing.py`)

7.4절에서 설명한 신규 전처리 파이프라인은 3단계 모두 독립적으로 실패에 대비합니다.

- **전처리 진입 단계 자체 실패** (손상된 이미지 파일, 지원하지 않는 포맷 등으로 `PIL.Image.open()`이 실패하는 경우): `vision_service.analyze_skin_image()`가 `preprocess_for_analysis()` 호출 전체를 `try/except`로 감싸, 실패 시 전처리 이전의 기존 방식(원본 이미지 1장을 그대로 Gemini에 전달)으로 완전히 폴백합니다.
- **화이트밸런스 보정 단계 실패**: `correct_white_balance()` 호출이 예외를 던지면, 보정본 대신 원본 이미지를 그대로 사용해 다음 단계(질감 강조)로 넘어갑니다.
- **질감 강조 단계 실패**: `enhance_texture()` 호출이 예외를 던지면, 질감 강조본 대신 화이트밸런스 보정본(또는 원본)을 그대로 사용합니다.
- **사전 품질평가에 의한 조기 종료**: 위 실패들과는 성격이 다른, **의도된 조기 반환**입니다. 암부·명부 비율이 극단적으로 높은(97% 이상) 사진은 애초에 Gemini가 분석해도 `image_quality_ok=false`가 나올 것이 확실하므로, `assess_image_quality()` 결과만으로 Gemini/임베딩 호출 자체를 생략하고 재촬영 안내 응답을 즉시 반환합니다. 이는 불필요한 API 비용과 응답 지연을 줄이는 최적화이자, "판정 실패"가 아닌 "명백한 케이스의 조기 처리"라는 점에서 위 3가지 실패 대응과 구분됩니다.

세 단계 모두 개별적으로 실패해도 최종적으로는 항상 유효한 이미지가 Gemini에 전달되도록 설계되어, 신규 기능 추가로 인해 기존 분석 파이프라인의 가용성이 낮아지지 않도록 했습니다.

### 9.4 실제 발견되어 수정된 버그

개발 과정에서 실제로 발생했던 버그와 수정 내역입니다.

| # | 문제 | 원인 | 조치 |
| --- | --- | --- | --- |
| 1 | 나이를 입력하면 피부나이가 비정상적으로 낮게 계산됨 | `feature_scores`의 채점 anchor를 연령대별로 바꾸는 실험 중, `compute_skin_age()`/`build_peer_comparison_note()`가 서로 다른 좌표계(전체 인구 기준 vs 연령대 기준)를 같은 좌표계로 착각해 비교 | anchor는 항상 전체 인구 기준으로 고정하고, "동년배 비교"는 `build_peer_comparison_note()`가 별도로 전담하도록 관심사를 분리 (`docs/개선 과정 작업지시서/SKIN_AGE_RELIABILITY_SPEC.md`) |
| 2 | 얼굴 인식기의 일시적 오류 한 번으로 자동 촬영 기능이 그 세션 내내 영구 중단됨 | MediaPipe/브라우저 내장 `FaceDetector`가 특정 프레임에서만 일시적으로 에러를 던지는 경우가 실제로 흔한데(타임스탬프 제약, 일부 안드로이드 기기 이슈 등), 최초 발생 시 감지 루프를 즉시 종료하도록 되어 있었음 | 연속 실패 횟수(`AUTO_CAPTURE_MAX_CONSECUTIVE_ERRORS`, 8회)를 임계값으로 두어, 일시적 오류는 무시하고 근본적으로 감지기가 동작하지 않을 때만 자동 촬영을 중단하도록 수정 |
| 3 | 이력에서 불러온 결과에 피드백 제출·공유 링크 생성이 동작하지 않음 | `save_record()` 호출 시점(분석 직후, DB 커밋 전)에는 `record.id`를 알 수 없어 저장되는 `result_json` 안의 `record_id`가 항상 `None`으로 저장됨 | `load_agent_result()`가 저장된 JSON을 복원할 때 실제 DB row의 `id`를 다시 채워 넣도록 수정 (`model_copy(update={"record_id": record.id})`) |
| 5 | 챗봇 AI 답변을 `innerHTML`로 렌더링해 XSS(스크립트 삽입) 위험이 있음 | `appendChatMessage()`/`sendChatMessage()`가 AI 응답 텍스트를 `innerHTML`에 그대로 대입 | `renderAiMessage()` 헬퍼를 추가해 `textContent`/`createTextNode` 기반 안전한 DOM 삽입으로 교체 (이번 세션 코드 QA에서 발견 및 수정) |
| 6 | 동일한 사진을 반복 분석해도 점수가 매번 흔들림 (재현성 낮음) | Gemini 호출의 `temperature`가 다소 높게 설정되어 있어, 같은 입력에도 출력 편차 발생 | `temperature`를 0.3 → 0.15로 낮춰 재현성을 측정했으나 항목별 개선/악화가 엇갈리고 `overall_score` 편차는 거의 그대로였음(`docs/개선 과정 작업지시서/SCORE_CONSISTENCY_TEST_LOG.md`) — temperature가 지배적 변수가 아니라고 판단해 0.2로 절충. `ai_summary` 등 자유 문장까지 기계적으로 완전히 고정되면 부자연스럽다는 점도 고려 |

### 9.5 프론트엔드 방어 코드

- **얼굴 자동 감지 기능의 단계적 폴백(progressive enhancement)**: 브라우저 내장 `FaceDetector` API를 우선 시도하고, 미지원 브라우저에서는 MediaPipe Tasks Vision(CDN 로드)으로 대체하며, 이마저 초기화에 실패하면 조용히 수동 셔터 촬영 모드로 전환합니다. 자동 촬영은 "있으면 좋은 기능"일 뿐 핵심 경로가 아니므로, 어떤 단계에서 실패하든 사용자는 최소한 수동 촬영으로 서비스를 계속 이용할 수 있습니다.
- **밝기 측정용 `getImageData()` 실패 대응**: 일부 브라우저/보안 정책 조합에서 캔버스 픽셀 읽기가 드물게 실패할 수 있는데, 이 경우도 예외를 잡아 조용히 건너뛰고(밝기 안내를 표시하지 않음) 촬영 자체는 막지 않습니다.
- **Service Worker 캐싱 전략**: 초기에는 캐시 우선(cache-first) 전략이었으나, 개발 중 파일이 자주 바뀌는 특성상 오래된 캐시가 계속 서빙되는 문제가 있어 네트워크 우선(network-first)으로 전환하고 `CACHE_NAME`을 올려 구버전 캐시를 강제 폐기하도록 수정했습니다. 또한 `/analyze`·`/history`·`/share/`·`/uv-index` 등 사용자별로 응답이 달라지는 API 경로는 애초에 캐싱 대상에서 제외해, 오프라인 폴백 시 다른 사용자의 결과가 잘못 노출되는 상황을 방지합니다.
