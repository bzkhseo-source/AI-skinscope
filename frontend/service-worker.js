// v2: 캐시 우선(cache-first) → 네트워크 우선(network-first)으로 변경.
// 개발 중 파일이 자주 바뀌므로, 항상 최신 파일을 먼저 시도하고
// 오프라인일 때만 캐시로 대체한다. CACHE_NAME을 바꿔서 이전 버전
// (skinscope-v1)의 낡은 캐시를 강제로 폐기한다.
const CACHE_NAME = "skinscope-v3";
const PRECACHE_URLS = ["index.html", "styles.css", "app.js", "manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // API 호출(백엔드)은 캐싱하지 않고 항상 네트워크로 보낸다.
  if (url.pathname.startsWith("/analyze") || url.pathname.startsWith("/history")) {
    return;
  }

  // 네트워크 우선: 최신 파일을 먼저 시도하고, 실패(오프라인)할 때만 캐시 사용.
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const cloned = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});