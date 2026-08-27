# UI/UX 리디자인 2차 — Claude Code 작업 지시서

작성: claude.ai 세션 | 작성일: 2026-08-27
대상: `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`
전제: `docs/UI_REDESIGN_SPEC.md`(1차)가 이미 적용된 상태의 코드를 기준으로 작성함.
      아래 라인 번호는 1차 적용 후의 **현재** 파일 기준.

결론부터: 요청하신 5가지 전부 CSS/HTML(+SVG) 범위에서 처리 가능하고, 백엔드나
데이터 구조 변경이 필요 없어 리스크가 낮습니다. 항목별로 정리했습니다.

---

## 1. "← 뒤로" 버튼 줄바꿈 수정

**원인**: `styles.css` 379~389행 `.back-btn`에 `white-space: nowrap`이 없어서,
좁은 화면에서 헤더 안 공간이 부족하면 텍스트가 "← 뒤" / "로"로 줄바꿈됩니다.

**styles.css** 379~389행 교체:

```css
.back-btn {
  display: none;
  flex-shrink: 0;
  white-space: nowrap;
  background: none;
  border: none;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-ink-soft);
  cursor: pointer;
  padding: 0;
}
```

---

## 2. 결과 상단 카드 — 사진(좌) + 게이지(우) 가로 배치, 상태 배지를 게이지 안으로

지금은 사진이 작은 원형 아바타로 게이지 위에 놓이고, 점수 아래에 배지가 따로
있습니다(세로 배치). 요청하신 목업은 사진을 크게 왼쪽에, 점수 게이지를 오른쪽에
나란히 놓고 "양호" 배지를 게이지 안쪽(점수 숫자 위)으로 넣는 가로 배치입니다.

**index.html** 100~106행 `.gauge-card` 블록 교체:

```html
<div class="gauge-card">
  <img id="resultThumb" class="result-thumb-mini" alt="분석한 사진" />
  <div class="gauge" id="scoreGauge" style="--pct:0">
    <div class="value">
      <span class="badge ok" id="statusBadge">양호</span>
      <div class="score-num"><span id="scoreValue">0</span><small>/100</small></div>
    </div>
  </div>
</div>
```

(`scoreValue`/`statusBadge`/`scoreGauge`/`resultThumb` id는 그대로라 `app.js`는
수정할 필요 없음 — 마크업 위치만 옮긴 것.)

**styles.css** 463~503행 교체:

```css
.gauge-card {
  background: var(--color-surface);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 20px;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16px;
}

.gauge {
  width: 116px;
  height: 116px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: conic-gradient(var(--color-accent) calc(var(--pct, 0) * 1%), var(--color-line) 0);
  flex-shrink: 0;
}

.gauge::before {
  content: '';
  position: absolute;
  inset: 9px;
  border-radius: 50%;
  background: var(--color-surface);
}

.gauge .value {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
}

.gauge .value .score-num {
  font-family: var(--font-mono);
  font-size: 24px;
  font-weight: 600;
}

.gauge .value .score-num small {
  font-size: 11px;
  color: var(--color-ink-soft);
}
```

**styles.css** 392~400행 `.result-thumb-mini` 교체(원형 아바타 → 둥근 사각형,
크기 확대):

```css
.result-thumb-mini {
  width: 92px;
  height: 92px;
  border-radius: var(--radius-card-sm);
  object-fit: cover;
  border: 2px solid var(--color-surface);
  box-shadow: var(--shadow-card);
  flex-shrink: 0;
}
```

---

## 3. feature-grid(모공/탄력/수분/주름 등) 카드 — 상태색 배경 + 아이콘 스타일

⚠판단: 첨부해주신 목업 하단(Moisture/Wrinkle 카드)은 라벨이 영문으로 되어있는데,
이건 처음 주셨던 "Modern Organic" 레퍼런스 이미지를 그대로 오려붙이신 것으로
보입니다. 실제 화면(위쪽 스크린샷)은 계속 한글 라벨(모공/탄력/수분/주름)을 쓰고
있어서, **라벨은 한글 그대로 두고 카드의 시각 스타일(상태색 배경 + 아이콘)만**
그 레퍼런스에서 가져왔습니다. 영문 라벨로 바꾸길 원하시면 말씀해주세요.

또한 레퍼런스의 "양호" 카드는 청록색 계열인데, 저희 팔레트는 이미 `--color-sage`
(양호)/`--color-amber`(주의)/`--color-brick`(관리 필요)/`--color-excellent`
(매우 양호) 4개 상태색을 갖고 있어서(1차 작업 때 추가함), 새 청록색을 또 넣기보다
**기존 상태색 토큰을 그대로 재사용**했습니다 — 팔레트가 흩어지지 않게 하기 위함.

지금은 카드 배경이 항상 흰색이고 진행 막대(bar)만 있는데, 배경을 상태색의 옅은
틴트로 바꾸고 막대 대신 상태색 스파크라인 아이콘을 넣습니다.

**app.js** 525~536행(featureGrid 렌더링) 교체:

```js
const grid = document.getElementById("featureGrid");
grid.innerHTML = "";
Object.entries(vision.feature_scores).forEach(([key, value]) => {
  const tier = featureScoreTier(value);
  const item = document.createElement("div");
  item.className = `feature-item ${tier.cls}`;
  item.innerHTML = `
    <div class="feature-item-head">
      <span class="label">${FEATURE_LABELS[key] || key}</span>
      <svg class="feature-item-icon" viewBox="0 0 40 20" aria-hidden="true">
        <path d="M1 15 L10 9 L17 13 L26 4 L32 8 L39 2" />
      </svg>
    </div>
    <span class="num">${value}</span>
    <span class="badge ${tier.cls}">${tier.label}</span>
  `;
  grid.appendChild(item);
});
```

**styles.css** 520~552행(`.feature-item` 관련 전체) 교체:

```css
.feature-item {
  background: var(--color-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-card-sm);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.feature-item.excellent { background: rgba(79, 122, 85, 0.10); border-color: transparent; }
.feature-item.ok        { background: rgba(124, 154, 114, 0.10); border-color: transparent; }
.feature-item.caution   { background: rgba(211, 144, 63, 0.10); border-color: transparent; }
.feature-item.warn      { background: rgba(183, 91, 68, 0.10); border-color: transparent; }

.feature-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.feature-item .label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-ink-soft);
  text-transform: uppercase;
}

.feature-item-icon {
  width: 32px;
  height: 16px;
  fill: none;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.feature-item.excellent .feature-item-icon { stroke: var(--color-excellent); }
.feature-item.ok        .feature-item-icon { stroke: var(--color-sage); }
.feature-item.caution   .feature-item-icon { stroke: var(--color-amber); }
.feature-item.warn      .feature-item-icon { stroke: var(--color-brick); }

.feature-item .num {
  font-family: var(--font-mono);
  font-size: 20px;
  font-weight: 600;
}
```

(기존 `.bar-track`/`.bar-fill` 규칙은 더 이상 쓰이지 않으므로 삭제해도 되고,
그냥 남겨둬도 무해합니다 — 카드 배경색 자체가 상태를 이미 보여줘서 막대는
중복이라 뺐습니다. 막대도 같이 유지하고 싶으면 알려주세요.)

---

## 4. 부위별 분석 — 얼굴 다이어그램을 라인아트 아이콘으로

지금은 살구색 타원 배경 위에 색깔 점 5개(이마/코/양볼/턱)를 찍는 방식인데,
목업은 이목구비가 있는 심플한 흑백 라인아트 얼굴입니다.

⚠판단: 지금 점(dot) 5개는 장식이 아니라 **부위별 상태를 색으로 보여주는
기능**입니다(`region-dot ok/caution/warn` 클래스를 JS가 실시간으로 칠함).
목업 그림 자체에는 점이 없지만, 점을 완전히 빼면 "어느 부위가 안 좋은지"를
한눈에 보여주는 기능이 사라지므로, **얼굴 그림만 라인아트로 바꾸고 점은 같은
위치에 그대로 유지**했습니다. 점까지 빼고 순수 장식용 아이콘으로만 쓰길
원하시면 말씀해주세요.

**index.html** 112~120행 SVG 교체:

```html
<svg viewBox="0 0 200 240" class="face-diagram-svg" aria-hidden="true">
  <path class="face-outline" d="M100 18 C138 18 158 52 158 96 C158 150 136 200 100 214
    C64 200 42 150 42 96 C42 52 62 18 100 18 Z"></path>
  <path class="face-feature" d="M42 90 C30 88 28 108 40 112"></path>
  <path class="face-feature" d="M158 90 C170 88 172 108 160 112"></path>
  <path class="face-feature" d="M66 84 C74 78 86 78 94 84"></path>
  <path class="face-feature" d="M106 84 C114 78 126 78 134 84"></path>
  <ellipse class="face-feature-fill" cx="80" cy="96" rx="7" ry="4"></ellipse>
  <ellipse class="face-feature-fill" cx="120" cy="96" rx="7" ry="4"></ellipse>
  <path class="face-feature" d="M98 100 C96 116 92 128 88 134 C92 138 100 138 104 134"></path>
  <path class="face-feature" d="M80 156 C90 164 110 164 120 156"></path>
  <circle id="dot-forehead" cx="100" cy="52" r="11" class="region-dot"></circle>
  <circle id="dot-nose" cx="100" cy="128" r="11" class="region-dot"></circle>
  <circle id="dot-cheek_l" cx="52" cy="128" r="11" class="region-dot"></circle>
  <circle id="dot-cheek_r" cx="148" cy="128" r="11" class="region-dot"></circle>
  <circle id="dot-chin" cx="100" cy="196" r="11" class="region-dot"></circle>
</svg>
```

**styles.css** `.face-outline` 규칙(현재 593~598행 근처) 교체 + 신규 규칙 추가:

```css
.face-outline {
  fill: none;
  stroke: var(--color-ink);
  stroke-width: 2.5;
  stroke-linejoin: round;
}

.face-feature {
  fill: none;
  stroke: var(--color-ink-soft);
  stroke-width: 2;
  stroke-linecap: round;
}

.face-feature-fill {
  fill: var(--color-ink-soft);
}
```

(`.region-dot` 관련 규칙은 그대로 유지 — 좌표(cx/cy)도 원래 값 그대로 재사용해서
JS(`dot-forehead` 등 id 기반 조회) 수정이 필요 없습니다. 다만 새 얼굴 윤곽 위에
점 위치가 살짝 안 맞아 보일 수 있어서, 적용 후 실제 화면 보고 좌표를 미세
조정하는 게 좋습니다 — 라인아트 자체가 대략적인 스케치라 정확도보다는 느낌
전달용입니다.)

---

## 5. 텍스트 줄바꿈 — 단어 단위로 (word-break)

`.region-note`(부위별 분석 코멘트)뿐 아니라 `.ai-detail`, `.ingredient-efficacy-list`
등 서술형 한글 문장이 들어가는 곳 전부 같은 문제가 있을 수 있어서, 개별 클래스가
아니라 **전역으로 한 번에** 적용하는 걸 권합니다.

**styles.css** 33~40행(`html, body` 규칙)에 한 줄 추가:

```css
html, body {
  margin: 0;
  padding: 0;
  background: var(--color-bg);
  color: var(--color-ink);
  font-family: var(--font-body);
  -webkit-font-smoothing: antialiased;
  word-break: keep-all;
  overflow-wrap: break-word;
}
```

`word-break: keep-all`은 한글 단어(어절) 단위로 줄바꿈하고, `overflow-wrap:
break-word`는 그래도 한 어절이 카드 폭보다 길면(긴 성분명 등) 그때만 강제로
잘라 넘치지 않게 하는 안전장치입니다. 전역 적용이라 리스크 있어 보일 수 있지만,
레이아웃을 바꾸는 속성이 아니라 줄바꿈 시점만 바꾸는 것이라 부작용 가능성은
낮습니다.

---

## 검증 체크리스트

1. 헤더의 "← 뒤로"가 좁은 화면(iPhone SE 등 375px 너비)에서도 한 줄로 나오는지.
2. 결과 화면 상단 카드에서 사진(둥근 사각형, 좌측)과 점수 게이지(우측)가 나란히
   보이고, "양호" 배지가 게이지 안 점수 숫자 위에 표시되는지.
3. feature-grid 6개 카드 배경이 상태에 따라 옅은 색 틴트로 바뀌고, 진행 막대
   대신 상태색 아이콘이 우측 상단에 보이는지.
4. 부위별 분석 얼굴 그림이 라인아트로 바뀌고, 이마/코/양볼/턱 위치에 상태색
   점이 여전히 정확히(또는 근사하게) 찍히는지 — 위치가 어색하면 좌표만
   미세조정.
5. 부위별 분석 코멘트("볼 중앙부 붉은기 및...") 같은 긴 문장이 화면 폭에서
   단어 중간이 아니라 단어 사이에서 줄바꿈되는지.
