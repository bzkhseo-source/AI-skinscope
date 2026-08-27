# UI/UX 리디자인 — Claude Code 작업 지시서 (Modern Organic & Skincare)

작성: claude.ai 세션 | 작성일: 2026-08-27
대상: `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`
근거: 사용자가 첨부한 레퍼런스 이미지("Modern Organic & Skincare" 컨셉 목업) + 실제 앱 스크린샷 2장

이 문서는 실제 코드(`frontend/*`)를 직접 열어 라인 단위로 확인한 뒤 작성했다. 각 항목은
사용자가 준 원래 번호(1~13)를 그대로 따른다. **제가 임의로 해석한 부분은 "⚠판단"으로
표시**했으니, 결과를 보고 의도와 다르면 해당 부분만 알려주시면 됩니다.

---

## 0. 디자인 토큰 — 팔레트/라운딩/그림자 (styles.css `:root`, 5~29행)

"Warm Beige / Muted Coral / Warm Soft White / Cream" 컨셉에 맞춰 기존 teal 액센트
팔레트를 코랄 계열로 교체하고, 라운딩/그림자를 더 부드럽게 키운다. **모든 색상은
`var(--color-*)` 토큰으로만 참조되고 있으므로(하드코딩된 hex 없음), 아래 `:root`
블록 교체 한 번으로 전체 화면에 일괄 적용된다.**

```css
:root {
  /* Color — Modern Organic & Skincare */
  --color-bg: #FBF3EA;           /* Warm Soft White (기존 #FBF6F3) */
  --color-surface: #FFFFFF;       /* 카드 배경, 유지 */
  --color-surface-warm: #FDF1E7;  /* Warm Beige — feature/ingredient 카드용 신규 토큰 */
  --color-ink: #3A2B22;           /* 웜톤 다크 (기존 #2A2321, 차가운 톤) */
  --color-ink-soft: #8C7C71;      /* 웜톤 muted taupe (기존 #6B615D) */
  --color-line: #EFE0D2;          /* Warm Beige 보더 (기존 #E6DDD7) */
  --color-accent: #C97A5D;        /* Muted Coral — 기존 teal #1F5C56 대체 */
  --color-accent-soft: #F7E4D9;   /* soft coral tint (기존 #E4EEEC) */
  --color-rose: #E3B7A8;
  --color-amber: #D3903F;         /* 주의 */
  --color-brick: #B75B44;         /* 관리 필요 / 경고 */
  --color-sage: #7C9A72;          /* 양호 */
  --color-excellent: #4F7A55;     /* 매우 양호 — 신규 토큰(4단계 상태 태그용, 1번 항목) */

  /* Type — 변경 없음 */
  --font-display: 'Fraunces', Georgia, serif;
  --font-body: 'Inter', -apple-system, sans-serif;
  --font-mono: 'IBM Plex Mono', 'Courier New', monospace;

  /* Layout — 더 부드러운 라운딩 + 그림자 */
  --radius-card: 26px;            /* 기존 18px → Large Border Radius */
  --radius-card-sm: 16px;         /* 신규: feature-item/ingredient-item 등 작은 카드용 */
  --radius-pill: 999px;
  --shadow-card: 0 18px 40px -22px rgba(58, 43, 30, 0.18); /* 기존보다 옅고 웜톤(Soft Shadows) */
  --max-width: 480px;
}
```

부가 변경:
- `index.html` 10행 `<meta name="theme-color" content="#1F5C56" />` → `content="#C97A5D"`
  (브라우저 크롬 색상도 코랄로 통일)
- `styles.css`의 하드코딩된 12px/14px 라운딩(`.feature-item`, `.ingredient-item`,
  `.history-entry`, `.result-thumb` 등)을 `var(--radius-card-sm)`로 교체해 "각진
  라운딩을 더 부드럽게"를 세부 요소까지 일관되게 적용.

**상태 태그(양호/주의 등) — UI 특징 2번째 요구사항**: 현재 `feature-grid`(모공·탄력·
수분·주름·색소침착·붉은기 6개 카드)에는 숫자만 있고 상태 태그가 없다(부위별 분석
`.region-item`에는 `regionScoreTier()`로 이미 3단계 배지가 있음). 레퍼런스 이미지처럼
"매우 양호/양호/주의" 컬러 태그를 feature-grid에도 추가한다.

`app.js` 451~455행 `regionScoreTier()` 아래에 신규 함수 추가:

```js
// feature-grid(모공/탄력/수분/주름/색소침착/붉은기)용 4단계 상태 태그.
// regionScoreTier()(부위별 분석, 3단계)와는 별도 — 레퍼런스 목업이 "매우 양호"
// 단계를 명시적으로 요구해 4단계로 구현했다. 두 체계가 다른 게 어색하면
// 나중에 3단계로 통일해도 됨(⚠판단 — 필요시 알려주시면 통일하겠습니다).
function featureScoreTier(score) {
  if (score >= 80) return { cls: "excellent", label: "매우 양호" };
  if (score >= 60) return { cls: "ok", label: "양호" };
  if (score >= 40) return { cls: "caution", label: "주의" };
  return { cls: "warn", label: "관리 필요" };
}
```

`app.js` 513~524행 featureGrid 렌더링 부분 교체:

```js
const grid = document.getElementById("featureGrid");
grid.innerHTML = "";
Object.entries(vision.feature_scores).forEach(([key, value]) => {
  const tier = featureScoreTier(value);
  const item = document.createElement("div");
  item.className = "feature-item";
  item.innerHTML = `
    <span class="label">${FEATURE_LABELS[key] || key}</span>
    <span class="num">${value}</span>
    <span class="badge ${tier.cls}">${tier.label}</span>
    <div class="bar-track"><div class="bar-fill" style="width:${value}%"></div></div>
  `;
  grid.appendChild(item);
});
```

`styles.css`에 `.badge.excellent` 규칙 추가 (587~589행 근처):

```css
.badge.excellent { background: rgba(79, 122, 85, 0.15); color: var(--color-excellent); }
```

---

## 2 + 3. 결과 화면 뒤로가기 버튼 — 우측 상단 + 헤더와 함께 고정

두 항목은 사실 하나로 합쳐서 구현하는 게 가장 깔끔하다: **뒤로 버튼을 상단 헤더
(`.app-header`) 안으로 옮기고, 헤더를 sticky로 만들면 자연히 우측 상단에 고정된
뒤로가기 버튼이 된다.**

⚠판단: `#resultBackBtn`은 "새로 스캔 후 결과 화면"과 "이력 상세보기" 양쪽에서 공유되는
동일한 버튼입니다. 요청하신 문구는 "이력 확인시"였지만, 같은 버튼이라 두 경우를 다르게
만들려면 별도 분기가 필요합니다 — 일관성을 위해 두 경우 모두 우측 상단 고정으로
적용했습니다. 이력 상세에서만 원하시면 알려주세요.

**index.html**: 91행 `<button class="back-btn" id="resultBackBtn">← 뒤로</button>`을
`<section id="screen-result">` 밖으로 빼서 18~23행 `.app-header` 안으로 이동:

```html
<header class="app-header">
  <div>
    <div class="logo">AI-<span>SkinScope</span></div>
    <div class="tagline">Reference Screening, Not Diagnosis</div>
  </div>
  <button class="back-btn" id="resultBackBtn">← 뒤로</button>
</header>
```

`<section id="screen-result">` 시작 부분(기존 91행)에서는 버튼 태그를 제거한다.

**app.js**: `showScreen()` (37~44행)에서 결과 화면일 때만 헤더에 뒤로 버튼이 보이도록
클래스 토글 추가:

```js
function showScreen(targetId) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.getElementById(targetId).classList.add("active");

  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.target === targetId);
  });

  document.querySelector(".app-header").classList.toggle("show-back", targetId === "screen-result");
}
```

기존 `resultBackBtn`의 클릭 이벤트 리스너(895행 근처)는 id가 그대로이므로 수정 불필요.

**styles.css**: `.app-header`(59~65행)를 sticky로, `.back-btn`(371~381행)을
헤더 우측 정렬 + 기본 숨김으로 변경:

```css
.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--color-bg);
  padding: 20px 20px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-line);
}

.back-btn {
  display: none;
  background: none;
  border: none;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-ink-soft);
  cursor: pointer;
  padding: 0;
}

.app-header.show-back .back-btn { display: block; }
```

**참고**: `.tab-bar`(하단 탭)는 이미 `position: sticky; bottom: 0;`으로 고정되어 있어
동일한 패턴을 상단 헤더에도 적용하는 것뿐이라 리스크가 낮다.

---

## 4. 결과 화면 상단 점수 중복 제거 (2번째 스크린샷: SCAN RESULT 텍스트 + 원형 게이지 중복)

`.result-summary-card`(index.html 93~100행, "Scan Result" 텍스트 + 점수 + 배지)와
`.gauge-card`(108~115행, 원형 게이지 + 점수 + 배지)가 같은 점수를 두 번 보여준다.
`.gauge-card`를 메인으로 남기고 `.result-summary-card`의 점수/배지 표시를 제거한다.

⚠판단: `.result-summary-card`에는 촬영한 사진(`#resultThumb`)도 함께 있습니다.
텍스트만 삭제하고 사진은 남기는 게 나을 것 같아 **사진은 `.gauge-card` 안으로
옮기는 방식**으로 처리했습니다(완전히 삭제하면 결과 화면에서 내가 찍은 사진을 다시
볼 수 없게 됨). 사진까지 완전히 없애길 원하시면 `resultThumb` 관련 마크업/코드를
통째로 지우면 되고, 그 경우 `app.js` 465~471행(`resultThumb.src = ...` 부분)도 같이
제거해야 앱이 깨지지 않습니다.

**index.html**: 93~100행 `.result-summary-card` 블록을 삭제하고, 108~115행
`.gauge-card`를 아래처럼 교체(사진 썸네일을 게이지 카드 좌상단에 작은 원형으로 배치):

```html
<div class="gauge-card">
  <img id="resultThumb" class="result-thumb-mini" alt="분석한 사진" />
  <div class="gauge" id="scoreGauge" style="--pct:0">
    <div class="value"><span id="scoreValue">0</span><small>/100</small></div>
  </div>
  <span class="badge ok" id="statusBadge">양호</span>
</div>
```
(5번 항목에서 다루는 `.disclaimer-compact` 줄은 여기서 이미 제거된 상태로 반영함)

**app.js**: `#summaryScoreValue`, `#summaryStatusBadge`를 참조하는 부분(478~481,
494, 504~507행)은 더 이상 해당 엘리먼트가 없으므로 제거하거나, `#scoreValue`/
`#statusBadge`만 갱신하도록 정리한다. `resultThumb.src = thumbUrl` 로직(465~471행)은
그대로 유지(엘리먼트를 옮긴 것뿐이라 id 기준 조회는 계속 동작함).

**styles.css**: `.result-summary-card`, `.result-thumb`, `.result-summary-text`,
`.result-summary-score` 규칙(384~411행)은 이제 안 쓰이므로 삭제하고, 대신 추가:

```css
.result-thumb-mini {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--color-surface);
  box-shadow: var(--shadow-card);
  align-self: flex-start;
}
```

---

## 5. "AI 참고용~" 문구 삭제 (gauge-card 내부)

index.html 114행 `<div class="disclaimer-compact">AI 참고용 스크리닝 · 의료 진단
아님</div>` 삭제 (4번 항목 코드에 이미 반영됨).

**검증 필요**: NFR-05("모든 결과 화면에 AI 참고용 고지 상시 노출")는 이 배지가
사라져도 12번 항목에서 다루는 "이 결과는 어떻게 만들어졌나요?" 섹션이 페이지 안에
항상 표시되어 있어(접이식이 아니라 상시 노출 상태) 계속 충족된다. 만약 나중에 그
섹션을 진짜 접이식(접혀있는 기본 상태)으로 바꾸게 되면, 상단 고지를 다시 살려야
NFR-05가 깨지지 않는다는 점을 기억해두면 좋겠습니다.

---

## 6. "참고 패턴 안내" → "SKIN 패턴 분석"

index.html 135행: `<h3>참고 패턴 안내</h3>` → `<h3>SKIN 패턴 분석</h3>`

---

## 7. 패턴 섹션 부제 문구 변경

index.html 136~138행:
```html
<p style="font-size:12px; color:var(--color-ink-soft); margin:0 0 10px;">
  아래는 사진에서 관찰된 시각적 특징과 유사한 참고 패턴입니다.
</p>
```
→
```html
<p style="font-size:12px; color:var(--color-ink-soft); margin:0 0 10px;">
  SKIN 이미지 분석에서 관찰된 패턴 결과입니다.
</p>
```

---

## 8. "AI 소견" → "스캐닝 소견"

index.html 143행: `<h3>AI 소견</h3>` → `<h3>스캐닝 소견</h3>`

---

## 9. 추천 성분 섹션 안내 문구 변경

index.html 156~160행:
```html
<p style="font-size:12px; color:var(--color-ink-soft); margin:0 0 10px;">
  AI Hub 스킨케어 성분-효능 데이터를 근거로 한 참고용 추천이며,
  특정 제품을 판매하거나 연동하지 않습니다. 구매 전 전성분표와
  본인의 피부 반응을 꼭 확인하세요.
</p>
```
→ (요청하신 문구 그대로 적용)
```html
<p style="font-size:12px; color:var(--color-ink-soft); margin:0 0 10px;">
  스킨케어 성분-효능 데이터를 근거로 한 추천 성분으로 본인 피부 반응을 꼭 확인하세요.
</p>
```

---

## 10. 성분 추천 — 고민 카테고리별 박스 구분

지금은 `.ingredient-group`끼리 위쪽 테두리 선(border-top) 하나로만 구분되어 있다
(styles.css 722~726행). 각 그룹을 독립된 카드(박스)로 감싼다.

**styles.css** 722~732행 교체:

```css
.ingredient-group {
  border: 1px solid var(--color-line);
  border-radius: var(--radius-card-sm);
  background: var(--color-surface-warm);
  padding: 14px;
}

.ingredient-group + .ingredient-group {
  margin-top: 12px;
}

.ingredient-group-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
```

⚠참고(선택 사항, 이번 요청 범위 밖): `group.concern_label_ko`(app.js 625행)가
`concern_ingredient_map.json`의 원본 폴더명을 그대로 쓰고 있어서, 카테고리에 따라
"피부처짐_탄력저하 관리에 도움이 되는 성분", "여드름_뾰루지 관리에 도움이 되는
성분"처럼 언더스코어가 그대로 노출됩니다. 박스로 감싸면 더 눈에 띌 수 있어서 참고로
남깁니다 — 원하시면 `app.js`에 표시용 라벨 매핑(`{"피부처짐_탄력저하": "탄력",
"여드름_뾰루지": "여드름", ...}`)을 하나 추가해 깔끔하게 정리해드릴 수 있습니다.

---

## 11. 성분 설명 개조식 요약 (5줄 이내)

지금은 `ing.efficacy` 원문(AI Hub 지식성분데이터.xlsx의 효능 설명, 2~4문장 서술형
텍스트)을 그대로 한 문단으로 보여준다(app.js 639행). 이를 프론트에서 문장 단위로
쪼개 불릿 리스트로 렌더링하고 최대 5개로 제한한다.

⚠판단: "요약"을 의미상 재작성(LLM 호출)으로 할지, 원문을 문장 단위로 쪼개 개조식으로
보여주기만 할지 두 가지 방법이 있습니다. 이번엔 **추가 비용/API 호출 없이 프론트에서
문장 분리만 하는 방식**으로 짰습니다 — 원문 자체가 이미 짧은 서술형이라 문장 분리만
해도 개조식처럼 보입니다. 실제로 봤을 때 부자연스러우면(문장이 아니라 진짜 의미
요약이 필요하면) `build_ingredient_map.py` 쪽에서 성분별로 한 번만 LLM 요약을 만들어
캐싱하는 방식으로 바꿀 수 있습니다.

**app.js** 628~641행 교체:

```js
group.ingredients.forEach((ing) => {
  const item = document.createElement("a");
  item.className = "ingredient-item";
  item.href = ing.search_url;
  item.target = "_blank";
  item.rel = "noopener noreferrer";

  const bullets = splitEfficacyToBullets(ing.efficacy, 5);
  const bulletsHtml = bullets.length
    ? `<ul class="ingredient-efficacy-list">${bullets.map((b) => `<li>${b}</li>`).join("")}</ul>`
    : "";

  item.innerHTML = `
    <div class="ingredient-name-row">
      <span class="ingredient-name">${ing.name_ko}</span>
      <span class="ingredient-search">검색 →</span>
    </div>
    ${bulletsHtml}
  `;
  groupDiv.appendChild(item);
});
```

같은 파일에 헬퍼 함수 추가(예: `FEATURE_LABELS` 선언부 근처):

```js
// 성분 효능 원문(서술형 문장)을 개조식 불릿으로 쪼갠다. 문장 끝(마침표/물음표/
// 느낌표 뒤 공백, 개행)을 기준으로 나누고 빈 조각은 버린 뒤 최대 maxLines개로 자른다.
function splitEfficacyToBullets(text, maxLines) {
  if (!text) return [];
  return text
    .split(/(?<=[.!?다요])\s+|\n+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, maxLines);
}
```

**styles.css**: `.ingredient-efficacy`(765~770행) 규칙을 아래로 교체:

```css
.ingredient-efficacy-list {
  margin: 6px 0 0;
  padding-left: 16px;
  font-size: 12px;
  color: var(--color-ink-soft);
  line-height: 1.5;
}

.ingredient-efficacy-list li { margin-bottom: 2px; }
```

---

## 12. "이 결과는 어떻게 만들어졌나요?" 본문 교체

index.html 172~178행:
```html
<h3>이 결과는 어떻게 만들어졌나요?</h3>
<p style="font-size:12px; line-height:1.6; color:var(--color-ink-soft); margin:0;">
  본 결과는 AI Hub 공인 데이터셋(안면부 피부질환 이미지 12,000장 +
  한국인 피부상태 실측 데이터 1,072명)을 근거로 Gemini Vision이
  분석한 <strong>참고용 스크리닝</strong>이며, 의료 진단이 아닙니다.
  정확한 진단은 피부과 전문의와 상담하세요.
</p>
```

⚠**수치 확인 요청**: 요청하신 교체 문구에 "안면부 질환 이미지 **12만 장**"이라고
되어 있는데, 코드(위 원문)와 `PLANNING.md` 8-1절 모두 "**12,000장**"으로 일관되게
기록돼 있습니다. 오타로 보여 아래 적용 문구는 12,000장 그대로 넣었습니다 — 실제로
12만 장이 맞다면(제가 모르는 데이터셋 업데이트가 있었다면) 알려주시면 바로
고치겠습니다.

→ 교체 (Gemini Vision 언급은 이 섹션에서는 요청하신 문구에 그대로 포함되어 있어
유지했습니다 — 13번 항목의 "Gemini 언급 삭제"는 소개 탭에 한정된 요청으로 해석):

```html
<h3>이 결과는 어떻게 만들어졌나요?</h3>
<p style="font-size:12px; line-height:1.6; color:var(--color-ink-soft); margin:0;">
  본 분석 결과는 AI Hub의 공인 피부 데이터셋(안면부 질환 이미지 12,000장 및
  한국인 실측 데이터)을 바탕으로 Gemini Vision이 도출한 참고용 스크리닝
  자료입니다. 정확한 의학적 진단은 반드시 피부과 전문의와 상담하시기 바랍니다.
</p>
```

---

## 13. 소개 탭 개편 — Gemini 언급 제거(AI로 통일) + 3단계 분석/성분 데이터 서사 추가

index.html 217~264행(`#screen-about`) 중 "SkinScope의 분석 방식", "기반 데이터",
"분석 3단계" 세 카드를 교체한다("꼭 알아주세요" 카드는 Gemini 언급이 없어 그대로 둠).

⚠판단: "분석 3단계"를 실제 파이프라인(이미지 분석 → 실측 데이터 보정 → 성분 매칭)에
맞춰 다시 썼습니다. 기존 3단계에는 성분 추천이 아예 빠져 있었는데(그땐 아직 구현 전),
요청하신 "스킨 효능 효과 데이터를 분석하여 최적화된 솔루션 제공" 내용을 3단계 중
마지막 단계에 자연스럽게 녹였습니다.

```html
<div class="about-card">
  <h3>SkinScope의 분석 방식</h3>
  <p>
    AI-SkinScope는 AI의 멀티모달 이미지 분석과</br>
    AI Hub 공인 데이터셋을 결합한 스크리닝 로직으로 동작합니다.
  </p>
</div>

<div class="about-card">
  <h3>기반 데이터</h3>
  <p>
    <strong>12,000장</strong>의 안면부 피부질환 이미지와 </br>
    <strong>13,936명</strong>의 한국인 피부상태 실측 데이터를</br>
    AI Hub 공인 데이터를 기반으로 분석 로직을 설계했습니다.
  </p>
  <ul>
    <li>이 중 <strong>800건</strong>(질환 사례 500 + 실측 인물 300)을
      임베딩하여 실시간 근접 사례 검색(RAG)에 활용</li>
    <li><strong>1,072명 전수 실측 데이터</strong>를 분석해 산출한 인구 백분위를
      점수화 기준값으로 활용</li>
    <li><strong>스킨케어 성분-효능 데이터 9,000건</strong>을 전수분석해 고민
      유형별 맞춤 성분 추천의 근거로 활용</li>
  </ul>
</div>

<div class="about-card">
  <h3>분석 3단계</h3>
  <ol>
    <li><strong>이미지 분석</strong> — AI가 사진에서 모공·탄력·수분·주름·
      색소침착·붉은기 등 시각적 특징을 다각도로 분석합니다.</li>
    <li><strong>실측 데이터 보정</strong> — 분석 결과와 가장 유사한 실제
      질환 사례·실측 인물 데이터를 검색해 점수 판단의 근거로 반영합니다.</li>
    <li><strong>맞춤 솔루션 도출</strong> — 스킨케어 성분-효능 데이터를 분석해
      가장 취약한 부위에 맞는 관리 팁과 추천 성분을 제시하고, 심각도가 높으면
      전문의 상담과 근처 병원 정보를 함께 안내합니다.</li>
  </ol>
</div>
```

(app.js 686~687행 공유 텍스트("AI 소견: ...", "본 결과는 AI 참고용 스크리닝이며
의료 진단이 아닙니다.")는 화면 밖 공유 문구라 이번 요청 범위 밖으로 보고 손대지
않았습니다 — 8번 항목처럼 "AI 소견" 라벨을 공유 텍스트에도 맞추고 싶으면 알려주세요.)

---

## 검증 체크리스트

1. 결과 화면 진입 시 우측 상단에 "← 뒤로" 버튼이 헤더와 함께 보이고, 스크롤해도
   헤더+버튼이 화면 상단에 고정되는지 (새 스캔 진입 / 이력 상세 진입 둘 다 확인).
2. 원형 게이지 카드에 사진 미니 썸네일 + 점수 + 배지만 남고, 위쪽 중복 텍스트
   카드가 사라졌는지. `resultThumb` 관련 JS 에러가 콘솔에 없는지.
3. feature-grid 6개 카드 각각에 매우양호/양호/주의/관리 필요 배지가 점수에 맞게
   표시되는지 (예: 80점 이상 "매우 양호" 초록 계열).
4. 전체 화면 배경/카드가 코랄-베이지 톤으로 바뀌고, 카드 모서리가 이전보다
   둥글어졌는지 (라이트/다크 모드 구분 없는 앱이라 상관없음).
5. "SKIN 패턴 분석", "스캐닝 소견" 등 라벨 텍스트가 정확히 바뀌었는지.
6. 추천 성분 섹션: 고민 카테고리별로 카드(박스)가 분리되어 보이고, 성분 설명이
   불릿 목록(최대 5줄)으로 나오는지.
7. "이 결과는 어떻게 만들어졌나요?" 문구, 소개 탭 3개 카드 문구가 교체됐는지 —
   특히 소개 탭에 "Gemini"라는 단어가 더 이상 나오지 않는지 확인 (본문 전체
   Ctrl+F "Gemini" 검색 시 소개 탭에는 0건이어야 함).
8. NFR-05(참고용 고지 상시 노출)가 여전히 지켜지는지 — 게이지 카드의 짧은
   배지는 없어졌지만 "이 결과는 어떻게 만들어졌나요?" 섹션이 항상 화면에
   보이는 상태로 남아있는지.
