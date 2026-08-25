# AI-SkinScope

AI 피부 상태 스크리닝 & 코칭 서비스 — **참고용 스크리닝이며 의료 진단이 아닙니다.**

스마트폰 카메라로 피부 트러블 부위를 촬영하면 Gemini Vision이 상태를 분석해 건강 점수와 참고용 가이드를 제공하고, 촬영 이력을 저장해 시간에 따른 변화를 추적해주는 개인 피부 코칭 서비스입니다.

## 프로젝트 소개

- 코디세이(Gyeongnam Codyssey) AI 네이티브 과정 — 팀미션 3-3 Final Project
- 문제 정의, 페르소나, AI 활용 방식, 일정 등 전체 기획은 [`docs/PLANNING.md`](docs/PLANNING.md) 참고

## 팀원 및 역할

| 이름 | 역할 | 담당 업무 |
|---|---|---|
| 서경환 | PM / Backend / AI | 프로젝트 총괄, FastAPI 백엔드, AI Agent·Vision 로직 설계 및 구현 |
| 조민경 | 팀장 | 팀 진행 관리, 발표 자료 총괄 |
| 오주연 | Frontend / 스타일링 | UI 스타일링, 사용자 경험 개선 |
| 강하연 | 테스트 / 배포 | 실사용자 테스트 진행, 배포 검증 |

## 기술 스택

- **AI**: Google Gemini Vision (`google-genai` SDK, `gemini-3.6-flash` / `gemini-3.5-flash-lite` fallback)
- **Backend**: FastAPI, SQLAlchemy, SQLite/PostgreSQL
- **Frontend**: Vanilla JS, HTML/CSS, PWA (Service Worker)
- **외부 API**: 카카오맵 Local API (근처 피부과 검색)
- **Infra**: Render(백엔드+DB), Vercel(프론트엔드), GitHub

## 핵심 AI 활용

### 1. 멀티모달 AI (Gemini Vision)
피부 사진에서 모공·탄력·수분·주름·색소침착·붉은기 등 특징을 추출합니다. AI Hub 데이터셋에서 추출한 질환 정의와 국내 인구통계(n=1,072) 실측 분포를 프롬프트에 근거로 주입해 판단 기준을 보정합니다. 자세한 설계 근거는 `docs/PLANNING.md`의 8-2절 참고.

### 2. AI Agent
분석 결과를 바탕으로 건강 점수를 산출하고, 심각도가 높으면 카카오맵 병원 검색 도구를 호출합니다. Gemini의 판단에 더해 점수 임계값 기반 규칙형 안전장치를 이중으로 적용합니다.

### 3. Long-term Memory
사용자별 촬영 이력을 DB에 저장하고, 최근 두 기록을 비교해 "지난 기록 대비 개선/악화" 코칭 메시지를 생성합니다.

## 실행 방법

### 요구사항
- Python 3.10+
- Gemini API 키 ([Google AI Studio](https://aistudio.google.com/apikey)에서 발급)
- 카카오 REST API 키 ([Kakao Developers](https://developers.kakao.com)에서 발급)

### 백엔드 설치 및 실행

```powershell
cd "AI-SkinScope"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`.env.example`을 참고해 `.env` 파일을 만들고 API 키를 입력합니다.

```powershell
python -m uvicorn app.main:app --reload
```

`http://127.0.0.1:8000/docs`에서 API 문서를 확인할 수 있습니다.

### 프론트엔드 실행

```powershell
cd frontend
python -m http.server 5500
```

`http://127.0.0.1:5500` 접속

## API 엔드포인트

| Method | 경로 | 설명 |
|---|---|---|
| POST | `/analyze` | 피부 사진 업로드 → AI 분석 + Agent 판단 + 이력 저장 |
| GET | `/history/{user_id}` | 사용자 이력 목록 + 변화 추세 |
| GET | `/history/{user_id}/{record_id}` | 특정 기록 상세 조회 |

## 결과 확인

- 배포 URL: (추후 업데이트)
- 발표 자료: (추후 업데이트)

## 보안 및 개인정보 처리

- API 키는 `.env`로 관리하며 Git에 커밋되지 않습니다 (`.gitignore` 참고)
- 피부 사진 및 건강 정보는 사용자 동의 후에만 수집합니다
- 모든 분석 결과는 "AI 참고용 스크리닝이며 의료 진단이 아니다"라는 고지를 상시 노출합니다