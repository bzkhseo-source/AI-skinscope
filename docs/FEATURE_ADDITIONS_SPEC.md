# 신규 기능 3종 설계 — J. 자외선지수 연동 / K. 퍼스널컬러 추천 / L. 피부지식 챗봇

작성일: 2026-08-30
`docs/PRODUCT_ROADMAP_V2.md`의 A~I에 이어 J/K/L 항목으로 편입 예정.

## 0. 왜 이 3가지인가 (미션 요건 관점)

지금까지 필수 기술요소 5개 카테고리(AI Agent/RAG/멀티모달/자동화워크플로우/Long-term
Memory) 중 멀티모달·RAG·Long-term Memory 3개만 명확히 충족돼 있었다. 이번 3개 기능으로:
- **J(자외선지수)** → 외부 데이터 연동 기반 **자동화 워크플로우** 충족
- **L(챗봇)** → 사용자가 직접 질문하는 **진짜 RAG Q&A**로, 지금까지 "채점 보정용"으로만
  쓰이던 RAG를 미션 예시("문서 기반 Q&A, 지식 베이스 챗봇")에 정확히 맞는 형태로 확장
- **K(퍼스널컬러)** → 기존 Gemini Vision 호출에 얹는 방식이라 비용/공수 대비 데모
  임팩트가 가장 크다

난이도는 K < J < L 순으로 보면 된다. 시간이 부족하면 K→J→L 순으로 잘라도 된다.

---

## J. 자외선 지수 연동 (자동화 워크플로우)

### 설계
- **데이터 소스**: OpenWeatherMap UV Index API(무료 티어, 위경도로 조회) 또는 기상청
  공공데이터포털 자외선지수 API. 이미 `/analyze` 요청에 `latitude`/`longitude`를 선택
  입력받고 있으므로 그 값을 그대로 재사용한다.
- **백엔드**: `app/routers/uv.py` 신규.
  ```python
  @router.get("/uv-index")
  async def get_uv_index(latitude: float, longitude: float) -> UVIndexResult
  ```
  `app/schemas/uv.py`:
  ```python
  class UVIndexResult(BaseModel):
      uv_index: float
      level: str            # "low"/"moderate"/"high"/"very_high"/"extreme"
      level_label_ko: str    # "낮음"/"보통"/"높음"/"매우 높음"/"위험"
      advice: str            # 레벨별 고정 안내 문구 (규칙 기반, Gemini 호출 없음)
  ```
  `advice`는 Gemini를 부르지 않고 레벨별 고정 문구 매핑(딕셔너리)으로 처리 — 비용 없이
  즉시 응답, 실패 지점도 줄어든다.
- **API 키**: `.env`에 `UV_API_KEY=` 추가, `.env.example`에 키 이름만 등록.
- **프론트**: `screen-scan`의 `profile-input-card` 근처에 위치정보가 있을 때만
  자외선 카드 노출. 레벨별 색상(초록→노랑→주황→빨강→보라 5단계) 배지로 표시.
- **에러 처리**: API 실패·위치 미허용 시 카드를 아예 숨긴다(필수 기능이 아니므로
  조용히 실패, 에러 토스트 띄우지 않음).
- **개인정보**: 위치정보는 이미 선택 입력이지만, 이번 기능으로 위치 요청 빈도가
  늘어나므로 최초 요청 시 "왜 필요한지"(병원 검색 + 자외선 지수 조회) 안내 문구를
  한 번 보여주는 걸 권장 — `docs/PLAN.md` DoD의 "개인정보 동의 문구 점검" 항목과
  같이 처리하면 좋다.
- **스트레치(시간 남으면)**: PWA Notification API로 앱을 열 때마다 로컬 알림
  갱신. 진짜 서버 푸시(Web Push, VAPID)는 이번 스코프에서 제외 — 별도 인프라가
  필요해 공수가 크다.

---

## K. 퍼스널컬러(피부톤 어울리는 컬러) 추천

### 설계
- **별도 API 호출 없음** — 이미 찍은 사진 한 장으로 `analyze_skin_image()`가 한 번
  Gemini를 호출할 때 같은 응답에 함께 받는다(응답 스키마만 확장, 호출 횟수는 그대로).
- `app/schemas/vision.py`에 추가:
  ```python
  class ColorSwatch(BaseModel):
      label_ko: str          # "코랄 립", "웜톤 브라운" 등
      hex: str                # "#RRGGBB"
      category: str           # "립/블러셔" | "의상" | "헤어컬러"

  class PersonalColorResult(BaseModel):
      undertone: str                          # "warm" | "cool" | "neutral"
      season_label_ko: str                    # "봄 웜톤" 등 (모르면 "웜톤"/"쿨톤"만)
      recommended_colors: List[ColorSwatch]
      colors_to_avoid: List[ColorSwatch] = []
      note: str                               # 판단 근거 1문장 + 참고용 명시
  ```
  `SkinAnalysisResult`에 `personal_color: Optional[PersonalColorResult] = None` 추가.
- **프롬프트 추가**(`SYSTEM_PROMPT_TEMPLATE`에 이어붙일 지침):
  ```
  image_quality_ok가 true인 경우, personal_color도 함께 판단하라. 사진에서 관찰되는
  피부 언더톤(웜톤/쿨톤/뉴트럴)을 근거로, 어울리는 립·블러셔 컬러 3~4개와 의상/헤어
  컬러 2~3개를 hex 코드로 제시하라. 반대로 피하면 좋은 컬러 1~2개도 제시하라.
  note에는 "사진 조명에 따라 오차가 있을 수 있는 참고용 결과"임을 반드시 명시하라.
  이 항목은 피부 건강 점수와 무관한 재미/참고용 기능임을 유지하고, 과도하게 단정적인
  표현(예: "무조건 이 컬러만")은 피하라.
  ```
- **신뢰성 캐벗**: 사진 조명·화이트밸런스에 따라 언더톤 판단이 크게 흔들릴 수 있다.
  다른 점수들처럼 인구 실측 데이터로 anchor할 방법이 없는 순수 주관적 판단이므로,
  "참고용/재미 요소"로 톤을 낮춰 제시하는 게 중요하다(과신 방지).
- **프론트**: 결과 화면에 "나에게 어울리는 컬러" 섹션 신규 추가. 원형 컬러칩을
  카테고리별로 나열, 칩 클릭 시 hex 코드 표시. 피할 컬러는 칩에 살짝 빗금/투명도로
  구분. 기존 성분 추천 섹션의 박스 스타일(카드+구분선) 재사용.

---

## L. 피부지식 챗봇 (RAG 기반 Q&A)

### 설계
- **지식베이스 구축** (`scripts/build_knowledge_base.py` 신규, 기존
  `build_ingredient_map.py` 패턴 재사용):
  1. `concern_ingredient_map.json`의 성분별 효능 설명을 문서 단위로 변환
  2. 스킨케어 상식 FAQ 20~30개를 직접 작성(`app/data/skincare_faq.json`) — 예:
     "레티놀은 무엇에 좋나요?", "각질 관리는 얼마나 자주 해야 하나요?" 등
  3. 두 소스를 합쳐 `gemini-embedding-2`(기존 인프라와 동일 모델)로 임베딩 →
     `app/data/knowledge_base_embeddings.json` 생성
- **백엔드**: `app/routers/chat.py` 신규.
  ```python
  @router.post("/analyze/{record_id}/chat")
  async def chat_about_result(record_id: int, payload: ChatRequest, db) -> ChatResponse
  ```
  `app/schemas/chat.py`:
  ```python
  class ChatRequest(BaseModel):
      user_id: str
      question: str

  class ChatResponse(BaseModel):
      answer: str
      is_ai_generated: bool = True   # 프론트에서 "AI 생성 답변" 배지 표시용
  ```
  처리 흐름(`app/services/chat_service.py`):
  1. `question`을 임베딩 → `knowledge_base_embeddings.json`과 코사인 유사도 top-3 검색
     (기존 `_cosine_similarity` 로직 재사용)
  2. `record_id`로 해당 사용자의 `SkinAnalysisResult` 조회(`memory_service.get_record`)
     → feature_scores·suspected_patterns·product_recommendations를 컨텍스트 텍스트로
     구성
  3. 아래 시스템 프롬프트로 텍스트 전용 Gemini 호출(이미지 없음 → 더 저렴/빠름):
     ```
     당신은 스킨케어 지식을 참고용으로 안내하는 AI 어시스턴트다. 아래 [사용자 분석
     결과]와 [참고 자료]에 근거해서만 답변하라. 근거에 없는 내용은 추측하지 말고
     "정확한 답변을 위해서는 추가 정보가 필요합니다"라고 답하라.

     의료 진단·처방에 해당하는 질문(예: "이거 무슨 병이에요?", "약 뭐 발라야 해요?")
     은 절대 단정적으로 답하지 말고, "이 부분은 전문의 상담이 필요해요"로 안내하라.

     답변은 3~4문장 이내로 간결하게, 참고용임을 자연스럽게 포함하라.

     [사용자 분석 결과]
     {user_context}

     [참고 자료]
     {rag_context}
     ```
  4. 답변 반환. 대화 히스토리는 저장하지 않는 **단발성 Q&A**로 시작(멀티턴 기억은
     스트레치 — Long-term Memory에 축적하면 좋지만 이번 스코프에서는 제외).
- **안전장치**:
  - 프롬프트에 의료 진단성 질문 회피 지침을 명시적으로 포함(위 프롬프트 3번째 문단)
  - 모든 답변에 `is_ai_generated: true`를 응답에 포함, 프론트에서 "AI가 생성한
    참고용 답변입니다" 배지를 채팅 말풍선마다 표시 — 미션 6번 "AI 생성 콘텐츠임을
    사용자에게 명시" 요건과 직결
  - Gemini 호출 실패 시 "지금은 답변이 어려워요, 잠시 후 다시 시도해주세요" 고정
    메시지로 대체(다른 서비스 전체에 영향 주지 않도록 격리)
- **프론트**: 결과 화면 하단에 "AI에게 물어보기" 섹션. 말풍선 리스트 + 입력창 +
  전송 버튼. 로딩 중엔 기존 스캔 대기 스피너 스타일 재사용. 질문 예시 3~4개를
  칩 형태로 미리 보여주면(예: "이 성분이 왜 좋아요?", "왜 모공 점수가 낮게
  나왔어요?") 첫 사용 진입장벽이 낮아진다.

---

## 공통 — `docs/PRODUCT_ROADMAP_V2.md` 반영

섹션 3 작업순서 표에 아래 행 추가:

| 순서 | 작업 | 비고 |
|---|---|---|
| 6 | K — 퍼스널컬러 추천 | 기존 Gemini 호출에 필드만 추가, 난이도 낮음 |
| 7 | J — 자외선지수 연동 | 신규 외부 API 연동, 위치정보 재사용 |
| 8 | L — 피부지식 챗봇(RAG) | 지식베이스 임베딩 구축 필요, 난이도 가장 높음 |

---

## Claude Code 실행 문구

> 아래 순서로 진행해줘 (K → J → L 순서 추천, 난이도 낮은 것부터).
>
> **K(퍼스널컬러)**: `app/schemas/vision.py`에 `ColorSwatch`/`PersonalColorResult`
> 추가하고 `SkinAnalysisResult.personal_color` 필드로 연결해줘. `vision_service.py`의
> `SYSTEM_PROMPT_TEMPLATE`에 위 §K 프롬프트 지침을 추가하고, 프론트 결과 화면에
> "나에게 어울리는 컬러" 섹션(컬러칩 UI)을 추가해줘.
>
> **J(자외선지수)**: `app/routers/uv.py`와 `app/schemas/uv.py`를 §J 설계대로 만들고,
> OpenWeatherMap UV Index API 연동해줘. `.env.example`에 `UV_API_KEY=` 추가하고,
> 프론트 스캔 화면에 위치정보 있을 때만 자외선 카드를 보여줘(실패 시 조용히 숨김).
>
> **L(챗봇)**: `scripts/build_knowledge_base.py`로 `concern_ingredient_map.json` +
> 신규 작성할 `app/data/skincare_faq.json`(스킨케어 FAQ 20~30개, 이건 네가 초안
> 작성해줘)을 `gemini-embedding-2`로 임베딩해서 `app/data/knowledge_base_embeddings.json`
> 만들어줘. `app/routers/chat.py`, `app/schemas/chat.py`, `app/services/chat_service.py`를
> §L 설계대로 구현하고, 의료진단성 질문 회피 지침과 "AI 생성 답변" 배지를 꼭
> 반영해줘. 프론트에 "AI에게 물어보기" 채팅 UI 섹션 추가해줘.
>
> 셋 다 완료되면 `docs/PRODUCT_ROADMAP_V2.md` 섹션 3 표에 J/K/L 완료 표시로
> 업데이트해줘.
