# PWA 홈 화면 설치("다운로드용 앱"처럼 보이기) — 점검 및 보강 설계

작성일: 2026-08-29
방향: 별도 앱스토어 등록 없이, 지금 코드 그대로 PWA 홈 화면 설치를 완성도 있게 만든다.

## 0-1. 항목별 적용 플랫폼 (중요 — 아래 각 수정이 iOS/Android 어느 쪽에 효과가 있는지)

| 항목 | iOS | Android | 비고 |
|---|---|---|---|
| `manifest.json` `theme_color` 수정 | 영향 없음 | ✅ 효과 있음 | 설치된 PWA의 상태바/툴바 색은 안드로이드만 이 값을 씀 |
| iOS 전용 메타 태그 4종 (`apple-mobile-web-app-capable` 등) | ✅ 효과 있음 | 영향 없음(무시됨, 해는 없음) | iOS는 `display: standalone`을 완전히 신뢰하지 않고 이 태그로 standalone 여부를 따로 판단 |
| maskable 아이콘 추가 | 해당 없음 | ✅ 효과 있음 | iOS는 아이콘을 항상 고정된 둥근사각형으로 표시해 마스킹 개념 자체가 없음 |
| 홈 화면 추가 안내 배너 | ✅ 필요 (수동 안내만 가능) | ✅ 필요 (자동 설치 이벤트 활용 가능) | 둘 다 필요하지만 동작 방식이 다름 — iOS는 `beforeinstallprompt` API가 없어 "공유 버튼 → 홈 화면에 추가" 안내만 가능, 안드로이드는 그 이벤트를 잡아 앱 내 "설치" 버튼으로 즉시 설치 유도 가능 |
| `service-worker.js` | ✅ 이미 정상 | ✅ 이미 정상 | 공통 웹 표준이라 양쪽 다 동일하게 작동, 추가 조치 불필요 |

즉 "이 수정들을 하면 iOS/Android에 똑같이 적용된다"가 아니라, **iOS 몫과 Android 몫이
나뉘어 있고 두 플랫폼 모두 제대로 동작하게 하려면 각자의 몫을 다 채워야 하는 구조**다.

## 0. 현재 상태 (코드로 확인된 것)

`frontend/index.html`에 이미 아래가 갖춰져 있다.
- `<link rel="manifest" href="manifest.json" />`
- `<link rel="apple-touch-icon" href="icons/icon-192.png" />`
- `<meta name="theme-color" content="#C97A5D" />`
- `app.js` 926~929행: `navigator.serviceWorker.register("service-worker.js")` 등록 코드 존재

즉 PWA의 기본 골격(매니페스트 연결, 서비스워커 등록)은 이미 돼 있다. 다만 아래 두 가지는
**이번에 코드로 확인한 결과 빠져 있거나, 이번 세션에서 기기 연결이 끊겨 직접 파일
내용을 확인하지 못한 부분**이다.

## 1. 확인된 gap: iOS 전용 메타 태그 누락

`index.html`의 `<head>`에 iOS Safari가 "홈 화면에 추가"를 완전한 standalone 앱처럼
동작시키는 데 필요한 아래 메타 태그가 없다.

```html
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<meta name="apple-mobile-web-app-title" content="AI-SkinScope" />
<meta name="mobile-web-app-capable" content="yes" />
```

이게 없으면 iOS에서 홈 화면 아이콘으로 실행해도 Safari 주소창/툴바가 남아있는 채로
열릴 수 있다 (매니페스트의 `display: standalone`만으로는 iOS에서 완전히 보장되지
않고, 이 메타 태그가 별도로 필요하다). `apple-mobile-web-app-title`이 없으면 홈 화면
아이콘 아래 표시되는 이름이 `<title>` 태그 값을 따라가긴 하지만, 명시적으로 지정하는
편이 안전하다.

## 2. 실제 파일 확인 결과 (재연결 후 직접 확인함)

### 2.1 `manifest.json` — 문제 발견: theme_color가 리디자인 전 색상

현재 내용:
```json
{
  "name": "AI-SkinScope",
  "short_name": "SkinScope",
  "description": "AI 피부 상태 스크리닝 & 코칭 (참고용, 의료 진단 아님)",
  "start_url": "/index.html",
  "display": "standalone",
  "background_color": "#FBF6F3",
  "theme_color": "#1F5C56",
  "orientation": "portrait",
  "icons": [
    { "src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

- **`theme_color: "#1F5C56"`은 "Modern Organic & Skincare" 리디자인 이전의 구 틸
  색상이다.** `index.html`의 `<meta name="theme-color" content="#C97A5D">`는 이미
  코랄로 바뀌었는데, 리디자인 당시 `manifest.json`은 같이 수정되지 않은 것으로
  보인다. 이 값은 Android에서 PWA로 설치했을 때 상단 상태바/툴바 색으로 쓰이므로,
  지금 상태로는 앱 UI는 코랄인데 설치 시 상태바만 틸로 나오는 불일치가 생긴다.
  → **`"#C97A5D"`로 수정 필요.**
- `background_color: "#FBF6F3"`는 코랄 팔레트와 잘 어울리는 값이라 그대로 둬도 된다.
- `display: "standalone"`, `name`/`short_name`은 정상.
- `start_url: "/index.html"`은 `"/"`로 통일해도 되지만(더 표준적), 현재 서빙 방식상
  당장 문제를 일으키진 않아 우선순위는 낮음.
- 아이콘은 `icons/icon-192.png`(1,388B), `icons/icon-512.png`(3,992B) 둘 다 실제로
  존재함을 확인했다. `purpose: "maskable"` 아이콘은 없음 — 없어도 동작은 하지만,
  Android 적응형 아이콘에서 로고가 어색하게 잘릴 수 있어 여유 있으면 하나 추가
  권장(필수는 아님).

### 2.2 `service-worker.js` — 문제 없음, 확인 완료

v4로 network-first 전략이 이미 잘 구현돼 있다(`index.html`/`styles.css`/`app.js`/
`manifest.json`/`share.html`/`share.js` precache, `/analyze`·`/history`·`/share/`는
캐싱 제외, 버전 바뀌면 구 캐시 자동 폐기). 이 부분은 추가 조치 불필요.

## 3. 놓치기 쉬운 UX 포인트: iOS는 설치를 "권유"해주지 않는다

Android/Chrome은 조건이 맞으면 브라우저가 자동으로 "홈 화면에 추가" 배너를 띄워주지만
(`beforeinstallprompt` 이벤트), **iOS Safari는 이 기능이 아예 없다.** 사용자가 직접
공유 버튼(⬆️) → "홈 화면에 추가"를 찾아 눌러야 하는데, 이 경로를 모르는 사용자가
많다. 스크린샷상 테스트 환경이 iOS로 보이므로, 이 부분을 놓치면 "PWA 설치 기반은
다 만들었는데 아무도 설치 안 함"이 될 수 있다.

**제안**: 첫 방문(또는 분석 결과를 1회 이상 받은) 사용자에게 "홈 화면에 추가하고 더
빠르게 사용해보세요" 같은 안내 배너를 앱 자체 UI로 보여준다. iOS/Android 여부를
`navigator.userAgent`로 판별해 문구를 다르게(iOS: "공유 버튼 → 홈 화면에 추가" 안내
이미지, Android: 표준 설치 버튼) 보여주는 정도면 충분하다. 이미 PWA 조건은 다
갖췄으니, 이 배너 하나만 추가해도 실질적인 "설치율"이 크게 달라질 수 있다.

## 4. Claude Code 실행 문구

> 1) `frontend/manifest.json`의 `theme_color`를 `"#1F5C56"`에서 `"#C97A5D"`로
> 바꿔줘 (리디자인 때 index.html은 바뀌었는데 manifest.json이 누락됐었어).
> 2) `frontend/index.html`의 `<head>`에 `apple-mobile-web-app-capable`,
> `apple-mobile-web-app-status-bar-style`, `apple-mobile-web-app-title`,
> `mobile-web-app-capable` 메타 태그를 추가해줘 (§1 참고).
> 3) 여유 있으면 `icons/icon-512-maskable.png`(로고 주변에 안전 여백을 둔 버전)를
> 만들어서 `manifest.json` icons 배열에 `purpose: "maskable"`로 추가해줘. 필수는
> 아니야.
> 4) 사용자가 iOS인지 Android인지 구분해서 "홈 화면에 추가" 안내 배너를 앱 상단이나
> 결과 화면 하단에 한 번 보여주는 컴포넌트를 추가해줘 (닫으면 로컬스토리지에 저장해서
> 다시 안 뜨게). §3 참고.
> (service-worker.js는 이미 잘 구현돼 있어서 손댈 필요 없음.)
