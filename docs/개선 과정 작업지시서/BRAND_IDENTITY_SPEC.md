# 브랜드(BI) 적용 — 블루 BI 로고·아이콘, iOS 홈 화면 앱 상단/하단 가림 수정

작성일: 2026-11-15
범위: 헤더 로고, 홈 화면(PWA·iOS) 아이콘, 파비콘, iOS 홈 화면 앱의 안전영역(safe-area)

## 0. 배경

BI 컬러 서베이(`AI-SkinScope_BI_컬러서베이/` — A 포레스트그린, B 블루, C 샴페인골드,
D 스킨) 중 A·B 두 안을 실제 화면에 적용한 미리보기(현재 / 로고·아이콘만 교체 /
화면 색상까지 BI에 맞춤)로 비교한 뒤 **B 블루 — 로고·아이콘만 교체(시안 1)**로
결정했다. 네 시안은 도형이 모두 같고 색만 다르다(블루: 네이비 `#1F3A5F`, 미디엄
블루 `#33557F`, 골드 `#C9B07A`, 슬로건 `#4F6E91`).

화면 색상(버튼·게이지·배지의 `#4F6BED` 계열)은 이번에 바꾸지 않았다. 블루 BI와
같은 파랑 계열이라 로고만 바꿔도 이질감이 크지 않다는 판단이다.

## 1. 헤더 로고 — BI 가로형 로고를 원본 그대로 사용

- `frontend/icons/brand/logo_horizontal.svg`를 BI 원본 파일 그대로(바이트 동일)
  넣고, 헤더의 텍스트 로고(`AI-<span>SkinScope</span>`)와 아래 영문 문구를 이
  이미지 하나로 대체했다(`index.html`, `share.html`).
- 로고에 포함된 슬로건 **SKIN ANALYSIS & WELLNESS**는 헤더 크기(가로 186px)에서
  작게 보이지만, **BI를 바꾸지 않고 원본 그대로 쓰기로 결정**했다. 검토 단계에서
  만든 "심볼 + 워드마크 + 텍스트 슬로건" 재조합안은 채택하지 않았다.
- SVG 자체에 상하좌우 여백이 있어 CSS에서 음수 margin으로 헤더 안 위치만 맞췄다
  (이미지를 자르거나 수정하지 않음). 결과 화면처럼 "사용법"과 "뒤로" 버튼이 함께
  있는 가장 좁은 헤더에서도 버튼과 겹치지 않는 폭이다.
- 헤더에 있던 "Reference Screening, Not Diagnosis" 문구는 빠졌다. "의료 진단이 아닌
  참고용" 안내는 촬영 동의 카드, 사용법 안내, 결과 화면 등에 그대로 남아 있다.

## 2. 앱 아이콘·파비콘

| 파일 | 원본 | 용도 |
|---|---|---|
| `icons/icon-192.png`, `icons/icon-512.png` | `brand/symbol_dark.svg` | `manifest.json` 아이콘 |
| `icons/icon-512-maskable.png` | `brand/symbol_dark.svg`를 76%로 줄여 같은 배경(`#1F3A5F`) 위에 배치 | Android 적응형 아이콘. 원형 등으로 잘려도 심볼이 안전영역(지름 80%) 안에 들어가도록 여백 확보 |
| `icons/apple-touch-icon.png` (180px, 신규) | `brand/symbol_dark.svg` | iOS 홈 화면 아이콘. iOS는 투명 배경을 지원하지 않아 배경이 꽉 찬 dark 버전 사용 |
| `icons/favicon-32.png` (신규), `brand/symbol.svg` | `brand/symbol.svg` | 브라우저 탭 아이콘(기존에는 파비콘이 없었음) |

PNG는 `rsvg-convert`로 SVG에서 직접 렌더링했다. 기존 `icons/Icon.png`,
`icons/Icon_raw.png`(이전 아이콘 원본, 어디서도 참조하지 않음)는 이번 범위에서
건드리지 않았다.

## 3. iOS 홈 화면 앱 상단/하단 가림 수정 (safe-area)

**증상**: 아이폰에서 홈 화면 아이콘으로 실행하면 헤더(로고·사용법 버튼)가 시계·
다이내믹 아일랜드(카메라) 영역 밑에 깔려 보이지 않았다. 하단 탭 메뉴도 홈
인디케이터(하단 막대)와 겹쳤다.

**원인**: `index.html`의 `viewport-fit=cover`와
`apple-mobile-web-app-status-bar-style: black-translucent` 설정 때문에 홈 화면 앱은
화면이 상태표시줄 아래까지 그려진다. 그런데 헤더는 `position: sticky; top: 0`에
고정 여백(20px)만 있어 상태표시줄 높이만큼 비켜서지 않았다.

**수정** (`styles.css`):
- `:root`에 `--safe-top: env(safe-area-inset-top, 0px)`,
  `--safe-bottom: env(safe-area-inset-bottom, 0px)` 추가
- `.app-header` 위쪽 여백: `20px` → `calc(20px + var(--safe-top))`
- `.tab-bar`: `padding-bottom: var(--safe-bottom)`
- `.modal-card`(사용법 바텀시트) 아래쪽 여백: `20px` → `calc(20px + var(--safe-bottom))`

헤더 배경이 상태표시줄 영역까지 함께 덮으므로, 스크롤하면 내용은 헤더 뒤로 지나가고
헤더는 상태표시줄 바로 아래 위치를 유지한다. PC 브라우저·안드로이드·아이폰 사파리
탭에서는 `env()` 값이 0이라 기존 레이아웃과 같다.

## 4. 배포 시 주의

`service-worker.js`의 `CACHE_NAME`을 `skinscope-v6` → `skinscope-v7`로 올렸다. 이미
홈 화면에 설치된 앱이 이전 헤더·스타일을 캐시에서 계속 보여주지 않도록 하기
위함이다. 다만 **iOS 홈 화면 아이콘 이미지는 iOS가 설치 시점에 저장해두므로**, 이미
설치한 기기에서 새 아이콘을 보려면 홈 화면에서 앱을 삭제하고 다시 추가해야 한다.

## 5. 검증

- 휴대폰 크기(390·393px)에서 스캔·결과·소개·공유 화면을 렌더링해 헤더 로고와 버튼이
  겹치지 않는지 확인.
- 아이폰 다이내믹 아일랜드 기기의 안전영역 값(상단 59px, 하단 34px)을 넣어 홈 화면
  앱 상태를 재현하고, 수정 전에는 로고가 상태표시줄에 가리고 수정 후에는 상태표시줄
  아래에서 시작하는지 비교 확인. 실제 기기 확인은 배포 후 필요하다.
