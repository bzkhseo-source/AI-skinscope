// ============================================================
// AI-SkinScope — 프론트엔드 로직
// ============================================================

// 로컬(127.0.0.1, localhost) 또는 같은 Wi-Fi의 사설 LAN IP(예: 192.168.x.x,
// 휴대폰으로 개발 PC에 접속해 테스트할 때)에서는 같은 호스트의 로컬 백엔드를,
// 그 외(배포된 도메인)에서는 Render 배포 백엔드를 자동으로 사용한다.
// 프로토콜도 현재 페이지와 동일하게 맞춘다(HTTPS로 접속했다면 백엔드도 HTTPS).
const LOCAL_HOSTNAME_PATTERN =
  /^(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})$/;

const API_BASE = LOCAL_HOSTNAME_PATTERN.test(location.hostname)
  ? `${location.protocol}//${location.hostname}:8000`
  : "https://ai-skinscope.onrender.com";

const state = {
  stream: null,
  capturedBlob: null,
  consentGiven: false,
  currentRecordId: null,
  selectedRating: null,
  // 얼굴을 직접 촬영하는 셀프 스캔 앱이라 전면(셀카) 카메라를 기본값으로 시작한다.
  facingMode: "user", // "environment"=후면, "user"=전면
  returnScreen: "screen-scan", // 결과 화면에서 "뒤로" 눌렀을 때 돌아갈 화면
};

// ---------------- 사용자 식별자 (간단한 로컬 프로토타입용) ----------------
function getUserId() {
  let userId = localStorage.getItem("skinscope_user_id");
  if (!userId) {
    userId = "user_" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("skinscope_user_id", userId);
  }
  return userId;
}

// ---------------- 화면 전환 공통 헬퍼 ----------------
function showScreen(targetId) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.getElementById(targetId).classList.add("active");

  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.target === targetId);
  });

  document.querySelector(".app-header").classList.toggle("show-back", targetId === "screen-result");
}

// ---------------- 탭 전환 ----------------
function initTabs() {
  const tabButtons = document.querySelectorAll(".tab-btn");
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      showScreen(btn.dataset.target);
      if (btn.dataset.target === "screen-history") {
        loadHistory();
      }
    });
  });
}

// ---------------- 동의 체크박스 ----------------
const CONSENT_STORAGE_KEY = "skinscope_consent_given";

function applyConsentGiven() {
  state.consentGiven = true;
  document.getElementById("consentCheckbox").checked = true;
  document.getElementById("consentCard").style.display = "none";
  document.getElementById("shutterBtn").disabled = false;
  document.getElementById("fileTriggerBtn").disabled = false;
  document.getElementById("cameraSwitchBtn").disabled = false;
}

function initConsent() {
  const checkbox = document.getElementById("consentCheckbox");
  const shutterBtn = document.getElementById("shutterBtn");
  const fileTriggerBtn = document.getElementById("fileTriggerBtn");
  const cameraSwitchBtn = document.getElementById("cameraSwitchBtn");

  // 이전에 이미 동의한 적이 있으면, 안내 카드를 다시 보여주지 않는다.
  if (localStorage.getItem(CONSENT_STORAGE_KEY) === "true") {
    applyConsentGiven();
    startCamera();
    initUvCard();
  }

  checkbox.addEventListener("change", () => {
    state.consentGiven = checkbox.checked;
    shutterBtn.disabled = !state.consentGiven;
    fileTriggerBtn.disabled = !state.consentGiven;
    cameraSwitchBtn.disabled = !state.consentGiven;

    if (state.consentGiven) {
      localStorage.setItem(CONSENT_STORAGE_KEY, "true");
      document.getElementById("consentCard").style.display = "none";
      startCamera();
      initUvCard();
    } else {
      stopCamera();
    }
  });
}

// ---------------- 카메라 ----------------
function updateMirrorPreview() {
  const wrap = document.getElementById("viewfinderWrap");
  wrap.classList.toggle("mirror-preview", state.facingMode === "user");
}

function showCameraError(show) {
  document.getElementById("cameraErrorOverlay").style.display = show ? "flex" : "none";
}

// 카메라 스트림이 살아있는지(트랙이 하나라도 "live" 상태인지) 확인한다.
// 모바일 브라우저는 탭이 백그라운드로 밀려나면(외부 링크를 새 탭으로 열 때
// 포함) 카메라 트랙을 강제로 "ended" 상태로 만드는 경우가 있는데, 이때
// <video>는 마지막 프레임에서 멈춘 채로 남아 얼굴 자동 인식도 함께 멎는다.
function isCameraStreamLive() {
  return !!(state.stream && state.stream.getVideoTracks().some((track) => track.readyState === "live"));
}

function applyCameraStream(stream) {
  const video = document.getElementById("cameraVideo");
  state.stream = stream;
  video.srcObject = stream;
  document.getElementById("viewfinderWrap").classList.add("scanning");
  updateMirrorPreview();
  showCameraError(false);
  startAutoCaptureLoop();
  startCaptureGuideLoop();

  stream.getVideoTracks().forEach((track) => {
    track.addEventListener("ended", () => {
      if (state.consentGiven && !state.capturedBlob && isScanScreenActive()) {
        recoverCamera();
      }
    });
  });
}

async function startCamera() {
  try {
    // facingMode를 문자열로 그대로 넘기면 일부 안드로이드 브라우저에서
    // "선호"가 아니라 엄격한 조건처럼 취급되어 후면 카메라로 대체되는
    // 경우가 있었다. { ideal: ... } 형태로 명시하면 브라우저가 이를
    // 확실히 "가능하면 이 방향"이라는 선호도로 해석해 전면 카메라를
    // 더 안정적으로 골라준다.
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: state.facingMode } },
      audio: false,
    });
    applyCameraStream(stream);
  } catch (err) {
    console.warn("선호 방향 카메라 접근 실패, 기본 카메라로 재시도합니다.", err);
    try {
      const fallbackStream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: false,
      });
      applyCameraStream(fallbackStream);
    } catch (err2) {
      console.warn("카메라 접근 완전히 실패, 갤러리 선택으로 대체합니다.", err2);
      showCameraError(true);
    }
  }
}

// 카메라 트랙이 죽어있는 상태(탭 백그라운드 복귀, 권한 재확인 등)에서
// 스트림을 정리하고 다시 시작한다. "확인" 버튼이나 브라우저 권한 응답에
// 대해 페이지가 아무 반응도 하지 않는 문제를 해결하기 위한 명시적 재시도 경로.
async function recoverCamera() {
  stopCamera();
  await startCamera();
}

function isScanScreenActive() {
  return document.getElementById("screen-scan").classList.contains("active");
}

function stopCamera() {
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
    state.stream = null;
  }
  document.getElementById("viewfinderWrap").classList.remove("scanning");
  stopAutoCaptureLoop();
  stopCaptureGuideLoop();
}

async function switchCamera() {
  state.facingMode = state.facingMode === "environment" ? "user" : "environment";
  stopCamera();
  await startCamera();
}

function capturePhotoFromVideo() {
  const video = document.getElementById("cameraVideo");
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth || 720;
  canvas.height = video.videoHeight || 960;
  const ctx = canvas.getContext("2d");

  // 라이브 프리뷰는 CSS(.mirror-preview)로만 거울처럼 반전해 보여줄 뿐,
  // <video>가 담고 있는 원본 프레임 자체는 반전되어 있지 않다. canvas는
  // 화면 표시가 아닌 원본 프레임을 그대로 그리므로, 여기서 다시 반전하면
  // 오히려 저장되는 사진이 실물과 반대로 뒤집힌다. 후면/전면 모두 원본
  // 그대로 캡처한다.
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob(
    (blob) => {
      if (blob) onPhotoCaptured(blob);
    },
    "image/jpeg",
    0.9
  );
}

function onPhotoCaptured(blob) {
  state.capturedBlob = blob;
  stopCamera();

  const video = document.getElementById("cameraVideo");
  const previewImg = document.getElementById("previewImg");
  previewImg.src = URL.createObjectURL(blob);
  video.style.display = "none";
  previewImg.style.display = "block";
  document.getElementById("viewfinderWrap").classList.add("hide-guide");

  document.getElementById("shutterBtn").style.display = "none";
  document.getElementById("fileTriggerBtn").style.display = "none";
  document.getElementById("cameraSwitchBtn").style.display = "none";
  document.getElementById("consentCard").style.display = "none";
  document.getElementById("analyzeBtn").style.display = "block";
  document.getElementById("retakeBtn").style.display = "block";
}

// ---------------- 얼굴 자동 감지 + 조건 충족 시 자동 촬영 (로드맵 C) ----------------
// 브라우저 내장 Shape Detection API(FaceDetector)는 지원 브라우저가 매우
// 제한적이므로, 없으면 MediaPipe Tasks Vision(CDN, 번들러 불필요)을 폴백으로
// 로드한다. 둘 다 실패하면 조용히 기존 수동 셔터 버튼으로 대체된다
// (progressive enhancement — 자동 촬영은 있으면 좋은 기능일 뿐 필수가 아니다).
const AUTO_CAPTURE_CHECK_INTERVAL_MS = 250;
const AUTO_CAPTURE_HOLD_MS = 1000; // 정위치 상태가 이만큼 지속되면 자동 촬영
// 얼굴 감지기가 특정 프레임에서만 일시적으로 에러를 던지는 경우가 실제로
// 흔하다(예: MediaPipe의 타임스탬프 제약, 일부 안드로이드 기기의 ML Kit
// 일시적 오류). 한 번의 에러로 자동 촬영 전체를 꺼버리면 그 세션 내내
// 수동 촬영만 가능해지므로, 이 횟수만큼 연속으로 실패할 때만 감지기 자체가
// 근본적으로 동작하지 않는다고 판단해 중단한다.
const AUTO_CAPTURE_MAX_CONSECUTIVE_ERRORS = 8;
const AUTO_CAPTURE_MIN_FACE_RATIO = 0.35; // 가이드 타원 면적 대비 얼굴 박스 최소 비율
const MEDIAPIPE_VISION_URL =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs";
const MEDIAPIPE_WASM_URL =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
const MEDIAPIPE_MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite";

let faceDetectorHandle = null; // 내장 FaceDetector 또는 MediaPipe FaceDetector 인스턴스
let faceDetectionMode = null; // "native" | "mediapipe" | null(미지원 -> 수동 촬영만)
let faceDetectionInitPromise = null;
let autoCaptureTimer = null;
let faceInPositionSince = null;
// 촬영 조건 실시간 안내(거리 체크)가 얼굴 인식을 별도로 다시 돌리지 않고
// 이 값을 재사용할 수 있도록, 자동 촬영 루프가 매 tick마다 갱신해둔다.
let lastFaceRatio = null;

async function initFaceDetection() {
  if (faceDetectionInitPromise) return faceDetectionInitPromise;

  faceDetectionInitPromise = (async () => {
    if ("FaceDetector" in window) {
      try {
        faceDetectorHandle = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 });
        faceDetectionMode = "native";
        console.info("얼굴 자동 감지: 브라우저 내장 FaceDetector 사용");
        return;
      } catch (err) {
        console.warn("내장 FaceDetector 초기화 실패, MediaPipe로 대체합니다.", err);
      }
    }

    try {
      const vision = await import(MEDIAPIPE_VISION_URL);
      const filesetResolver = await vision.FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_URL);
      faceDetectorHandle = await vision.FaceDetector.createFromOptions(filesetResolver, {
        baseOptions: { modelAssetPath: MEDIAPIPE_MODEL_URL },
        runningMode: "VIDEO",
      });
      faceDetectionMode = "mediapipe";
      console.info("얼굴 자동 감지: MediaPipe FaceDetector 사용");
    } catch (err) {
      console.warn("얼굴 자동 감지를 사용할 수 없어 수동 촬영으로만 동작합니다.", err);
      faceDetectionMode = null;
    }
  })();

  return faceDetectionInitPromise;
}

async function detectFaceBoxes(video) {
  if (faceDetectionMode === "native") {
    const faces = await faceDetectorHandle.detect(video);
    return faces.map((f) => f.boundingBox);
  }
  if (faceDetectionMode === "mediapipe") {
    const result = faceDetectorHandle.detectForVideo(video, performance.now());
    return (result.detections || []).map((d) => ({
      x: d.boundingBox.originX,
      y: d.boundingBox.originY,
      width: d.boundingBox.width,
      height: d.boundingBox.height,
    }));
  }
  return [];
}

// 뷰파인더 타원 가이드(중앙, 폭 62%, 세로 3:4 비율)와 얼굴 박스가
// 충분히 겹치는지 대략적으로 판단한다. 정확한 픽셀 단위 겹침 계산 대신,
// 크기 비율과 중심 거리로 "대충 타원 안에 맞게 들어왔는지"만 확인한다.
function isFaceWellPositioned(box, video) {
  const videoW = video.videoWidth;
  const videoH = video.videoHeight;
  if (!videoW || !videoH || !box.width || !box.height) return false;

  const guideW = videoW * 0.62;
  const guideH = guideW * (4 / 3);
  const guideCenterX = videoW / 2;
  const guideCenterY = videoH * 0.44;

  const faceRatio = (box.width * box.height) / (guideW * guideH);
  lastFaceRatio = faceRatio; // 촬영 조건 안내(거리 체크)가 재사용

  const faceCenterX = box.x + box.width / 2;
  const faceCenterY = box.y + box.height / 2;
  const centeredX = Math.abs(faceCenterX - guideCenterX) < guideW * 0.35;
  const centeredY = Math.abs(faceCenterY - guideCenterY) < guideH * 0.35;

  return faceRatio >= AUTO_CAPTURE_MIN_FACE_RATIO && centeredX && centeredY;
}

function setFaceAlignedIndicator(aligned) {
  document.getElementById("viewfinderWrap").classList.toggle("face-aligned", aligned);
}

function startAutoCaptureLoop() {
  stopAutoCaptureLoop();

  initFaceDetection().then(() => {
    if (!faceDetectionMode || !state.stream) return; // 미지원 환경: 수동 셔터만 사용

    let consecutiveErrors = 0;

    autoCaptureTimer = setInterval(async () => {
      if (state.capturedBlob || !state.stream) return;
      const video = document.getElementById("cameraVideo");
      try {
        const boxes = await detectFaceBoxes(video);
        consecutiveErrors = 0;
        if (boxes.length === 0) lastFaceRatio = null;
        const wellPositioned = boxes.length > 0 && isFaceWellPositioned(boxes[0], video);
        setFaceAlignedIndicator(wellPositioned);

        if (wellPositioned) {
          if (faceInPositionSince === null) faceInPositionSince = Date.now();
          if (Date.now() - faceInPositionSince >= AUTO_CAPTURE_HOLD_MS) {
            faceInPositionSince = null;
            // capturePhotoFromVideo()의 canvas.toBlob()이 비동기라 state.capturedBlob이
            // 뒤늦게 설정되므로, 그 사이 인터벌이 한 번 더 돌아 중복 촬영되지 않도록
            // 타이머부터 즉시 멈춘다.
            stopAutoCaptureLoop();
            capturePhotoFromVideo();
          }
        } else {
          faceInPositionSince = null;
        }
      } catch (err) {
        faceInPositionSince = null;
        setFaceAlignedIndicator(false);
        consecutiveErrors += 1;
        if (consecutiveErrors >= AUTO_CAPTURE_MAX_CONSECUTIVE_ERRORS) {
          console.warn("얼굴 감지가 반복적으로 실패해 자동 촬영을 중단합니다.", err);
          stopAutoCaptureLoop();
        }
      }
    }, AUTO_CAPTURE_CHECK_INTERVAL_MS);
  });
}

function stopAutoCaptureLoop() {
  if (autoCaptureTimer) {
    clearInterval(autoCaptureTimer);
    autoCaptureTimer = null;
  }
  faceInPositionSince = null;
  lastFaceRatio = null;
  setFaceAlignedIndicator(false);
}

// ---------------- 촬영 조건 실시간 안내 (밝기·거리, 소프트 가이드) ----------------
// 촬영 자체를 막지 않는다 — 매번 비슷한 조건으로 찍도록 유도하는 참고용
// 안내일 뿐이며, 이 안내가 있어도 셔터 버튼은 항상 눌러진다.
const CAPTURE_GUIDE_CHECK_INTERVAL_MS = 500;
const BRIGHTNESS_THRESHOLD = 80; // 0~255 평균 밝기 기준(경험적)
const FACE_TOO_FAR_RATIO = 0.15; // 이보다 작으면 얼굴이 가이드 대비 너무 작음(멀다)
const FACE_TOO_CLOSE_RATIO = 0.9; // 이보다 크면 너무 큼(가깝다)

let captureGuideTimer = null;
let brightnessSampleCanvas = null;

function computeAverageBrightness(video) {
  if (!video.videoWidth || !video.videoHeight) return null;
  if (!brightnessSampleCanvas) brightnessSampleCanvas = document.createElement("canvas");

  // 픽셀 단위 정확도가 필요 없으므로 아주 작게 리사이즈해 성능 부담을 줄인다.
  const sampleW = 40;
  const sampleH = 30;
  brightnessSampleCanvas.width = sampleW;
  brightnessSampleCanvas.height = sampleH;
  const ctx = brightnessSampleCanvas.getContext("2d", { willReadFrequently: true });

  let data;
  try {
    ctx.drawImage(video, 0, 0, sampleW, sampleH);
    data = ctx.getImageData(0, 0, sampleW, sampleH).data;
  } catch (err) {
    return null; // 드문 보안/브라우저 제약으로 실패해도 조용히 건너뛴다
  }

  let sum = 0;
  const pixelCount = sampleW * sampleH;
  for (let i = 0; i < data.length; i += 4) {
    sum += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
  }
  return sum / pixelCount;
}

function setCaptureConditionHint(text) {
  const el = document.getElementById("captureConditionHint");
  if (!el) return;
  if (text) {
    el.textContent = text;
    el.style.display = "block";
  } else {
    el.style.display = "none";
  }
}

function startCaptureGuideLoop() {
  stopCaptureGuideLoop();
  captureGuideTimer = setInterval(() => {
    if (state.capturedBlob || !state.stream) return;

    const video = document.getElementById("cameraVideo");
    const brightness = computeAverageBrightness(video);
    if (brightness !== null && brightness < BRIGHTNESS_THRESHOLD) {
      setCaptureConditionHint("조금 더 밝은 곳에서 찍어주세요");
      return;
    }

    // 거리 체크는 자동 촬영(로드맵 C)이 지원되는 환경에서만 가능하다 —
    // lastFaceRatio가 없으면(미지원/얼굴 미검출) 밝기만으로 안내한다.
    if (lastFaceRatio !== null) {
      if (lastFaceRatio < FACE_TOO_FAR_RATIO) {
        setCaptureConditionHint("조금 더 가까이서 찍어주세요");
        return;
      }
      if (lastFaceRatio > FACE_TOO_CLOSE_RATIO) {
        setCaptureConditionHint("조금 더 멀리서 찍어주세요");
        return;
      }
    }

    setCaptureConditionHint(null);
  }, CAPTURE_GUIDE_CHECK_INTERVAL_MS);
}

function stopCaptureGuideLoop() {
  if (captureGuideTimer) {
    clearInterval(captureGuideTimer);
    captureGuideTimer = null;
  }
  setCaptureConditionHint(null);
}

function resetCaptureUI() {
  state.capturedBlob = null;
  const video = document.getElementById("cameraVideo");
  const previewImg = document.getElementById("previewImg");
  video.style.display = "block";
  previewImg.style.display = "none";

  const viewfinderWrap = document.getElementById("viewfinderWrap");
  viewfinderWrap.style.display = "";
  viewfinderWrap.classList.remove("hide-guide");
  document.getElementById("shutterBtn").style.display = "inline-block";
  document.getElementById("fileTriggerBtn").style.display = "block";
  document.getElementById("cameraSwitchBtn").style.display = "block";
  // 이미 동의를 완료한 사용자에게는 안내 카드를 다시 띄우지 않는다.
  document.getElementById("consentCard").style.display = state.consentGiven ? "none" : "block";
  document.getElementById("analyzeBtn").style.display = "none";
  document.getElementById("retakeBtn").style.display = "none";

  showScreen("screen-scan");
  if (state.consentGiven) startCamera();
}

// ---------------- 나이/성별 입력 (선택, 로컬 기억) ----------------
const AGE_STORAGE_KEY = "skinscope_age";
const GENDER_STORAGE_KEY = "skinscope_gender";

function initProfileInputs() {
  const ageInput = document.getElementById("ageInput");
  const genderSelect = document.getElementById("genderSelect");

  const savedAge = localStorage.getItem(AGE_STORAGE_KEY);
  const savedGender = localStorage.getItem(GENDER_STORAGE_KEY);
  if (savedAge) ageInput.value = savedAge;
  if (savedGender) genderSelect.value = savedGender;

  ageInput.addEventListener("change", () => {
    if (ageInput.value) localStorage.setItem(AGE_STORAGE_KEY, ageInput.value);
    else localStorage.removeItem(AGE_STORAGE_KEY);
  });
  genderSelect.addEventListener("change", () => {
    if (genderSelect.value) localStorage.setItem(GENDER_STORAGE_KEY, genderSelect.value);
    else localStorage.removeItem(GENDER_STORAGE_KEY);
  });
}

function getAgeGenderInput() {
  const ageValue = document.getElementById("ageInput").value.trim();
  const genderValue = document.getElementById("genderSelect").value;
  const age = ageValue ? Number(ageValue) : null;
  return {
    age: age && age >= 1 && age <= 120 ? age : null,
    gender: genderValue || null,
  };
}

// ---------------- 위치 정보 (선택) ----------------
function getLocation() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => resolve(null),
      { timeout: 4000 }
    );
  });
}

// 자외선 지수 카드 추가로 위치 요청 빈도가 늘어나므로, 이 브라우저에서
// 처음 위치를 요청하기 직전에 한 번만 용도를 안내한다.
const LOCATION_NOTICE_KEY = "skinscope_location_notice_shown";

function getLocationWithNotice() {
  if (!localStorage.getItem(LOCATION_NOTICE_KEY)) {
    localStorage.setItem(LOCATION_NOTICE_KEY, "true");
    alert(
      "위치 정보는 근처 피부과 검색과 자외선 지수 조회에만 사용되며, 서버에 저장되지 않습니다."
    );
  }
  return getLocation();
}

// ---------------- 자외선 지수 (선택, 위치정보 있을 때만) ----------------
function renderUvCard(uv) {
  const badge = document.getElementById("uvLevelBadge");
  badge.textContent = uv.level_label_ko;
  badge.className = `uv-badge ${uv.level}`;
  document.getElementById("uvIndexValue").textContent = uv.uv_index.toFixed(1);
  document.getElementById("uvAdviceText").textContent = uv.advice;
  document.getElementById("uvCard").style.display = "flex";
}

async function initUvCard() {
  try {
    const location = await getLocationWithNotice();
    if (!location) return;

    const response = await fetch(
      `${API_BASE}/uv-index?latitude=${location.lat}&longitude=${location.lng}`
    );
    if (!response.ok) return; // 키 미설정·조회 실패는 선택 기능이므로 조용히 무시
    renderUvCard(await response.json());
  } catch (err) {
    console.warn("자외선 지수 조회 실패:", err);
  }
}

// ---------------- 분석 요청 ----------------
async function submitAnalysis() {
  if (!state.capturedBlob) return;

  const loadingOverlay = document.getElementById("loadingOverlay");
  loadingOverlay.classList.add("active");

  try {
    const location = await getLocationWithNotice();

    const formData = new FormData();
    formData.append("file", state.capturedBlob, "capture.jpg");
    formData.append("user_id", getUserId());
    if (location) {
      formData.append("latitude", String(location.lat));
      formData.append("longitude", String(location.lng));
    }
    const { age, gender } = getAgeGenderInput();
    if (age) formData.append("age", String(age));
    if (gender) formData.append("gender", gender);

    const response = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      throw new Error(errBody.detail || `분석 요청 실패 (${response.status})`);
    }

    const result = await response.json();
    const thumbUrl = URL.createObjectURL(state.capturedBlob);
    state.returnScreen = "screen-scan";
    renderResult(result, thumbUrl);
  } catch (err) {
    alert("분석 중 오류가 발생했습니다: " + err.message);
    console.error(err);
  } finally {
    loadingOverlay.classList.remove("active");
  }
}

// ---------------- 결과 렌더링 ----------------
const FEATURE_LABELS = {
  pore: "모공",
  elasticity: "탄력",
  moisture: "수분",
  wrinkle: "주름",
  pigmentation: "색소침착",
  redness: "붉은기",
};

const REGION_LABELS = {
  forehead: "이마",
  nose: "코(T존)",
  cheek_l: "왼쪽 볼",
  cheek_r: "오른쪽 볼",
  chin: "턱",
};
const REGION_ORDER = ["forehead", "nose", "cheek_l", "cheek_r", "chin"];

function regionScoreTier(score) {
  if (score >= 70) return "ok";
  if (score >= 40) return "caution";
  return "warn";
}

// feature-grid(모공/탄력/수분/주름/색소침착/붉은기)용 4단계 상태 태그.
function featureScoreTier(score) {
  if (score >= 80) return { cls: "excellent", label: "매우 양호" };
  if (score >= 60) return { cls: "ok", label: "양호" };
  if (score >= 40) return { cls: "caution", label: "주의" };
  return { cls: "warn", label: "관리 필요" };
}

// 종합 점수(overall_score)용 6단계 상태 구간. 기준 평균 60점, 10점 단위로 관리.
function overallScoreTier(score) {
  if (score <= 40) return { cls: "derm", label: "피부과 전문의 진료 권고" };
  if (score <= 50) return { cls: "warn", label: "경고" };
  if (score <= 60) return { cls: "caution", label: "주의" };
  if (score <= 70) return { cls: "ok", label: "양호" };
  if (score <= 80) return { cls: "excellent", label: "매우양호" };
  return { cls: "top", label: "백옥 피부 미녀(미남)" };
}

// 성분 효능 원문(완전한 문장)을 개조식 불릿으로 쪼갠다. 문장 끝
// (마침표/물음표/느낌표 다음 공백, 줄바꿈)을 기준으로 나누고 빈 조각을
// 버린 뒤 최대 maxLines개로 자른다.
// 실제 성분 사진 대신 고민 카테고리를 한눈에 구분할 수 있는 아이콘 (피드백 #163: 가독성/시각 자료 요청)
const CONCERN_ICONS = {
  pore: "🔍",
  acne: "🔴",
  wrinkle: "〰️",
  pigmentation: "🟤",
  redness: "🌡️",
  elasticity: "💪",
  dryness: "💧",
  sensitivity: "⚠️",
};

function splitEfficacyToBullets(text, maxLines) {
  if (!text) return [];
  return text
    .split(/(?<=[.!?])\s+|\n+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, maxLines);
}

// ---------------- 퍼스널컬러 (참고용) ----------------
const UNDERTONE_LABELS = { warm: "웜톤", cool: "쿨톤", neutral: "뉴트럴" };

function renderColorSwatchGroup(container, colors) {
  container.innerHTML = "";
  colors.forEach((c) => {
    const swatch = document.createElement("div");
    swatch.className = "color-swatch";
    swatch.innerHTML = `
      <div class="swatch-chip" style="background:${c.hex}"></div>
      <span class="swatch-label">${c.label_ko}</span>
      <span class="swatch-hex">${c.hex}</span>
    `;
    container.appendChild(swatch);
  });
}

function renderPersonalColor(personalColor) {
  const card = document.getElementById("personalColorCard");
  if (!personalColor) {
    card.style.display = "none";
    return;
  }
  card.style.display = "block";

  const undertoneEl = document.getElementById("personalColorUndertone");
  undertoneEl.textContent =
    personalColor.season_label_ko || UNDERTONE_LABELS[personalColor.undertone] || personalColor.undertone;

  renderColorSwatchGroup(
    document.getElementById("personalColorRecommended"),
    personalColor.recommended_colors || []
  );

  const avoidGroup = document.getElementById("personalColorAvoid");
  if (personalColor.colors_to_avoid && personalColor.colors_to_avoid.length > 0) {
    avoidGroup.style.display = "flex";
    renderColorSwatchGroup(avoidGroup, personalColor.colors_to_avoid);
  } else {
    avoidGroup.style.display = "none";
  }

  document.getElementById("personalColorNote").textContent = personalColor.note || "";
}

function renderResult(result, thumbUrl) {
  const vision = result.vision;
  state.currentRecordId = result.record_id || null;
  state.currentVision = vision;
  state.currentNeedsDermatologist = result.needs_dermatologist;
  resetFeedbackUI();
  resetChatUI();

  // 게이지 카드 안의 사진 썸네일 (품질 실패 시에는 resultReport 자체가 숨겨진다)
  const resultThumb = document.getElementById("resultThumb");
  if (thumbUrl) {
    resultThumb.src = thumbUrl;
    resultThumb.style.display = "block";
  } else {
    resultThumb.style.display = "none";
  }

  const qualityCard = document.getElementById("qualityIssueCard");
  const reportEl = document.getElementById("resultReport");

  if (!vision.image_quality_ok) {
    // 사진 인식 실패: 오해를 부르는 0점 표시 대신 재촬영 안내로 전환
    document.getElementById("qualityIssueText").textContent =
      vision.quality_note || "사진에서 피부 상태를 충분히 인식하지 못했습니다.";
    qualityCard.style.display = "block";
    reportEl.style.display = "none";

    document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
    document.getElementById("screen-result").classList.add("active");
    document.querySelector(".app-header").classList.add("show-back");
    return;
  }

  qualityCard.style.display = "none";

  // needs_dermatologist는 점수 구간과 별개로 Gemini/Agent가 심각도를 직접
  // 판단해 켜질 수도 있으므로(예: 점수는 애매해도 위험 소견 감지), 그 경우
  // 점수 구간 배지도 항상 "전문의 진료 권고"로 맞춰 서로 모순되지 않게 한다.
  const tier = result.needs_dermatologist
    ? { cls: "derm", label: "피부과 전문의 진료 권고" }
    : overallScoreTier(vision.overall_score);

  const scoreTierBadge = document.getElementById("scoreTierBadge");
  scoreTierBadge.textContent = tier.label;
  scoreTierBadge.className = `badge ${tier.cls}`;

  const scoreDesc = document.getElementById("scoreDescText");
  if (result.needs_dermatologist) {
    scoreDesc.textContent = "전문의 상담을 권장드려요. 가까운 피부과 방문을 고려해보세요.";
    scoreDesc.classList.add("warn");
  } else {
    scoreDesc.textContent = vision.ai_focus || vision.ai_summary || "";
    scoreDesc.classList.remove("warn");
  }

  document.getElementById("scoreValue").textContent = vision.overall_score;

  const grid = document.getElementById("featureGrid");
  grid.innerHTML = "";
  Object.entries(vision.feature_scores).forEach(([key, value]) => {
    const tier = featureScoreTier(value);
    const item = document.createElement("div");
    item.className = "feature-item";
    item.innerHTML = `
      <div class="feature-item-head">
        <span class="label">${FEATURE_LABELS[key] || key}</span>
        <span class="badge ${tier.cls}">${tier.label}</span>
      </div>
      <div class="num">${value}<small>/100</small></div>
      <div class="bar-track"><div class="bar-fill ${tier.cls}" style="width:${value}%"></div></div>
    `;
    grid.appendChild(item);
  });

  const regionalCard = document.getElementById("regionalCard");
  const regionalList = document.getElementById("regionalList");
  regionalList.innerHTML = "";

  if (vision.regional_scores) {
    regionalCard.style.display = "block";
    REGION_ORDER.forEach((key) => {
      const region = vision.regional_scores[key];
      if (!region) return;

      const composite = Math.round((region.pore + region.oiliness + region.trouble) / 3);
      const tier = regionScoreTier(composite);

      const row = document.createElement("div");
      row.className = "region-item";
      row.innerHTML = `
        <div class="region-item-head">
          <span class="region-name">${REGION_LABELS[key] || key}</span>
          <span class="badge ${tier}">${composite}</span>
        </div>
        <div class="region-note">${region.note || ""}</div>
      `;
      regionalList.appendChild(row);
    });
  } else {
    regionalCard.style.display = "none";
  }

  const patternsList = document.getElementById("patternsList");
  patternsList.innerHTML = "";
  if (vision.suspected_patterns && vision.suspected_patterns.length > 0) {
    vision.suspected_patterns.forEach((p) => {
      const div = document.createElement("div");
      div.className = "pattern-item";
      div.innerHTML = `
        <div class="pattern-head">
          <span class="pattern-name">${p.name}</span>
          <span class="pattern-similarity">유사도 ${p.similarity}%</span>
        </div>
        <div class="pattern-note">${p.note || ""}</div>
      `;
      patternsList.appendChild(div);
    });
  } else {
    patternsList.innerHTML =
      '<div class="pattern-empty">사진에서 특별히 두드러진 질환 패턴은 발견되지 않았습니다.</div>';
  }

  const aiFocusEl = document.getElementById("aiFocusText");
  const aiDetailEl = document.getElementById("aiDetailText");
  if (vision.ai_focus) {
    aiFocusEl.textContent = vision.ai_focus;
    aiFocusEl.style.display = "block";
    aiDetailEl.textContent = vision.ai_detail || "";
  } else {
    // 구조화된 소견이 없는 과거 기록은 기존 자유 텍스트 소견으로 대체 표시한다.
    aiFocusEl.style.display = "none";
    aiDetailEl.textContent = vision.ai_summary;
  }

  const skinAgeBadge = document.getElementById("skinAgeBadge");
  skinAgeBadge.style.display = "inline-block";
  if (result.skin_age) {
    if (result.skin_age_reliable === false) {
      skinAgeBadge.textContent = "피부나이 참고용 (데이터 부족)";
      skinAgeBadge.classList.add("muted");
    } else {
      const delta = result.age ? result.skin_age - result.age : null;
      const deltaText = delta ? ` (실제 대비 ${delta > 0 ? "+" : ""}${delta}세)` : "";
      skinAgeBadge.textContent = `피부 나이 ${result.skin_age}세${deltaText}`;
      skinAgeBadge.classList.remove("muted");
    }
  } else {
    skinAgeBadge.textContent = "실제 나이가 입력되지 않아 분석할 수 없습니다";
    skinAgeBadge.classList.add("muted");
  }

  const peerNoteEl = document.getElementById("aiPeerNoteText");
  if (result.peer_comparison_note) {
    peerNoteEl.textContent = result.peer_comparison_note;
    peerNoteEl.style.display = "block";
  } else {
    peerNoteEl.style.display = "none";
  }

  const tipsList = document.getElementById("careTipsList");
  tipsList.innerHTML = "";
  (vision.care_tips || []).forEach((tip) => {
    const li = document.createElement("li");
    li.textContent = tip;
    tipsList.appendChild(li);
  });

  const productRecoCard = document.getElementById("productRecoCard");
  const productRecoList = document.getElementById("productRecoList");
  productRecoList.innerHTML = "";
  if (result.product_recommendations && result.product_recommendations.length > 0) {
    productRecoCard.style.display = "block";
    result.product_recommendations.forEach((group) => {
      const groupDiv = document.createElement("div");
      groupDiv.className = "ingredient-group";

      const title = document.createElement("div");
      title.className = "ingredient-group-title";
      const icon = CONCERN_ICONS[group.concern_key] || "✨";
      title.innerHTML = `<span class="ingredient-group-icon" aria-hidden="true">${icon}</span>${group.concern_label_ko} 관리에 도움이 되는 성분`;
      groupDiv.appendChild(title);

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
            <span class="ingredient-usage-badge">바르는 성분</span>
          </div>
          ${bulletsHtml}
          <span class="ingredient-search-cta">관련 화장품 검색 →</span>
        `;
        groupDiv.appendChild(item);
      });

      productRecoList.appendChild(groupDiv);
    });
  } else {
    productRecoCard.style.display = "none";
  }

  renderPersonalColor(vision.personal_color);

  const hospitalCard = document.getElementById("hospitalCard");
  const hospitalList = document.getElementById("hospitalList");
  hospitalList.innerHTML = "";
  if (result.hospitals && result.hospitals.length > 0) {
    hospitalCard.style.display = "block";
    result.hospitals.forEach((h) => {
      const div = document.createElement("div");
      div.className = "hospital-item";
      const distanceText = h.distance_m ? `${h.distance_m}m` : "";
      div.innerHTML = `
        <div class="name">${h.name}</div>
        <div class="meta">${h.address} ${distanceText}</div>
      `;
      hospitalList.appendChild(div);
    });
  } else {
    hospitalCard.style.display = "none";
  }

  updateInstallBanner();
  document.getElementById("resultReport").style.display = "flex";

  // 결과 전용 화면으로 전환 (탭바에는 없는 화면이므로 showScreen 대신 직접 처리)
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.getElementById("screen-result").classList.add("active");
  document.querySelector(".app-header").classList.add("show-back");
}

// ---------------- 결과 공유 (사진·병원·추천성분 등 개인화 정보는 제외) ----------------
function buildShareText() {
  const vision = state.currentVision;
  if (!vision) return "";

  const tier = state.currentNeedsDermatologist
    ? { label: "피부과 전문의 진료 권고" }
    : overallScoreTier(vision.overall_score);

  const lines = [
    "[AI-SkinScope 스캔 결과]",
    `종합 점수: ${vision.overall_score}/100 (${tier.label})`,
    "",
  ];

  Object.entries(vision.feature_scores).forEach(([key, value]) => {
    const featureTier = featureScoreTier(value);
    lines.push(`- ${FEATURE_LABELS[key] || key}: ${value}/100 (${featureTier.label})`);
  });

  if (vision.ai_focus || vision.ai_detail) {
    lines.push("");
    if (vision.ai_focus) lines.push(`스캐닝 소견: ${vision.ai_focus}`);
    if (vision.ai_detail) lines.push(vision.ai_detail);
  }

  if (vision.care_tips && vision.care_tips.length > 0) {
    lines.push("");
    lines.push("관리 팁:");
    vision.care_tips.forEach((tip) => lines.push(`- ${tip}`));
  }

  lines.push("");
  lines.push("본 결과는 AI 참고용 스크리닝이며 의료 진단이 아닙니다.");
  return lines.join("\n");
}

// 서버에 추측 불가능한 토큰의 임시 공유 링크(7일 후 만료)를 발급받는다.
// record_id가 없는 경우(사진 인식 실패 등 저장되지 않은 결과)는 링크 없이
// 텍스트만 공유한다.
async function createShareUrl() {
  if (!state.currentRecordId) return null;
  try {
    const response = await fetch(`${API_BASE}/analyze/${state.currentRecordId}/share`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: getUserId() }),
    });
    if (!response.ok) {
      console.warn(`공유 링크 생성 실패(HTTP ${response.status}), 텍스트만 공유합니다.`);
      return null;
    }
    const { token } = await response.json();
    return `${location.origin}/share.html?token=${token}`;
  } catch (err) {
    console.warn("공유 링크 생성 실패, 텍스트만 공유합니다.", err);
    return null;
  }
}

async function shareResult() {
  const text = buildShareText();
  if (!text) return;

  const shareUrl = await createShareUrl();

  if (navigator.share) {
    try {
      const shareData = shareUrl
        ? { title: "AI-SkinScope 스캔 결과", text, url: shareUrl }
        : { title: "AI-SkinScope 스캔 결과", text };
      await navigator.share(shareData);
    } catch (err) {
      if (err.name !== "AbortError") console.error(err);
    }
    return;
  }

  const clipboardText = shareUrl ? `${text}\n\n전체 결과 보기: ${shareUrl}` : text;
  try {
    await navigator.clipboard.writeText(clipboardText);
    alert("결과가 클립보드에 복사되었습니다.");
  } catch (err) {
    console.error(err);
    alert("공유하기를 지원하지 않는 환경입니다.");
  }
}

// ---------------- 이력 상세보기 ----------------
async function openHistoryDetail(recordId) {
  const loadingOverlay = document.getElementById("loadingOverlay");
  loadingOverlay.classList.add("active");
  try {
    const response = await fetch(`${API_BASE}/history/${getUserId()}/${recordId}`);
    if (!response.ok) throw new Error(`상세 조회 실패 (${response.status})`);
    const result = await response.json();

    state.returnScreen = "screen-history";
    renderResult(result, null);
  } catch (err) {
    alert("상세 정보를 불러오지 못했습니다: " + err.message);
    console.error(err);
  } finally {
    loadingOverlay.classList.remove("active");
  }
}

// ---------------- 이력 화면 ----------------
async function loadHistory() {
  const listEl = document.getElementById("historyList");
  const emptyEl = document.getElementById("historyEmpty");
  const trendBanner = document.getElementById("trendBanner");
  const trendSeriesCard = document.getElementById("trendSeriesCard");

  listEl.innerHTML = "";
  if (trendSeriesCard) trendSeriesCard.style.display = "none";
  document.getElementById("trendAnalysisCard").style.display = "none";
  try {
    const response = await fetch(`${API_BASE}/history/${getUserId()}`);
    if (!response.ok) throw new Error("이력 조회 실패");
    const data = await response.json();

    if (!data.entries || data.entries.length === 0) {
      emptyEl.style.display = "block";
      trendBanner.style.display = "none";
      return;
    }
    emptyEl.style.display = "none";

    if (data.trend) {
      trendBanner.style.display = "block";
      const delta = data.trend.score_delta;
      document.getElementById("trendDelta").textContent = (delta >= 0 ? "+" : "") + delta;
      document.getElementById("trendMessage").textContent = data.trend.coaching_message;
    } else {
      trendBanner.style.display = "none";
    }

    data.entries.forEach((entry, idx) => {
      const div = document.createElement("div");
      div.className = "history-entry";
      div.style.cursor = "pointer";
      const date = new Date(entry.created_at);
      const dateLabel = `${date.getMonth() + 1}/${date.getDate()} ${date
        .getHours()
        .toString()
        .padStart(2, "0")}:${date.getMinutes().toString().padStart(2, "0")}`;
      div.innerHTML = `
        <div>
          <div class="idx">SCAN ${String(data.entries.length - idx).padStart(3, "0")} · ${dateLabel}</div>
        </div>
        <div class="history-entry-right">
          <div class="score">${entry.overall_score}</div>
          <button class="history-delete-btn" type="button" aria-label="이 기록 삭제">삭제</button>
        </div>
      `;
      div.addEventListener("click", () => openHistoryDetail(entry.id));
      div.querySelector(".history-delete-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        deleteHistoryRecord(entry.id);
      });
      listEl.appendChild(div);
    });

    loadTrendSeries();
  } catch (err) {
    console.error(err);
    emptyEl.style.display = "block";
  }
}

// ---------------- 이력 개별 삭제 (FR-12) ----------------
async function deleteHistoryRecord(recordId) {
  if (!confirm("이 기록을 삭제할까요? 삭제하면 되돌릴 수 없습니다.")) return;

  try {
    const response = await fetch(`${API_BASE}/history/${getUserId()}/${recordId}`, {
      method: "DELETE",
    });
    if (!response.ok && response.status !== 204) {
      throw new Error(`삭제 실패 (${response.status})`);
    }
    loadHistory();
  } catch (err) {
    alert("기록 삭제 중 오류가 발생했습니다: " + err.message);
    console.error(err);
  }
}

// ---------------- 변화 추이 시계열 분석 (FR-09 확장) ----------------
async function loadTrendSeries() {
  const card = document.getElementById("trendSeriesCard");
  if (!card) return;

  try {
    const response = await fetch(`${API_BASE}/history/${getUserId()}/trend`);
    if (!response.ok) {
      // 기록이 2건 미만이면 404 — 시계열 분석 카드를 숨긴다.
      card.style.display = "none";
      return;
    }
    const data = await response.json();
    card.style.display = "block";

    document.getElementById("trendSeriesSummary").textContent = data.summary_message;

    const badgeList = document.getElementById("trendFeatureBadges");
    badgeList.innerHTML = "";
    const directionIcon = { improving: "▲", declining: "▼", stable: "–" };
    const directionCls = { improving: "up", declining: "down", stable: "flat" };
    data.feature_trends.forEach((t) => {
      const badge = document.createElement("div");
      badge.className = `trend-feature-badge ${directionCls[t.direction] || "flat"}`;
      const deltaText = t.delta > 0 ? `+${t.delta}` : `${t.delta}`;
      badge.innerHTML = `
        <span class="trend-feature-label">${t.label_ko}</span>
        <span class="trend-feature-delta">${directionIcon[t.direction] || "–"} ${deltaText}</span>
      `;
      badgeList.appendChild(badge);
    });

    drawTrendChart(data.series);
  } catch (err) {
    card.style.display = "none";
    console.error(err);
  }
}

// svg에 values(0~100 스케일 숫자 배열)를 꺾은선 그래프로 그린다. 종합점수
// 큰 차트와 이력분석의 항목별 미니 차트가 이 함수를 공유한다.
function renderLineChartIntoSvg(svg, values, { width, height, padding, dotRadius }) {
  svg.innerHTML = "";
  if (!values || values.length < 2) return;

  const minScore = Math.min(...values, 0);
  const maxScore = Math.max(...values, 100);
  const range = maxScore - minScore || 1;

  const points = values.map((v, i) => {
    const x = padding + (i / (values.length - 1)) * (width - padding * 2);
    const y = height - padding - ((v - minScore) / range) * (height - padding * 2);
    return `${x},${y}`;
  });

  const ns = "http://www.w3.org/2000/svg";
  const polyline = document.createElementNS(ns, "polyline");
  polyline.setAttribute("points", points.join(" "));
  polyline.setAttribute("class", "trend-chart-line");
  svg.appendChild(polyline);

  points.forEach((pt) => {
    const [x, y] = pt.split(",");
    const circle = document.createElementNS(ns, "circle");
    circle.setAttribute("cx", x);
    circle.setAttribute("cy", y);
    circle.setAttribute("r", String(dotRadius));
    circle.setAttribute("class", "trend-chart-dot");
    svg.appendChild(circle);
  });
}

function drawTrendChart(series) {
  const svg = document.getElementById("trendChartSvg");
  if (!svg) return;
  const values = (series || []).map((p) => p.overall_score);
  renderLineChartIntoSvg(svg, values, { width: 300, height: 100, padding: 10, dotRadius: 3 });
}

// ---------------- 이력분석 리포트 (항목별 그래프 + AI 관리 피드백) ----------------
const TREND_ANALYSIS_CHARTS = [
  { key: "overall_score", label: "종합 점수", overall: true },
  { key: "pore", label: "모공" },
  { key: "elasticity", label: "탄력" },
  { key: "moisture", label: "수분" },
  { key: "wrinkle", label: "주름" },
  { key: "pigmentation", label: "색소침착" },
  { key: "redness", label: "붉은기" },
];

function renderTrendAnalysis(data) {
  const grid = document.getElementById("trendAnalysisGrid");
  grid.innerHTML = "";

  const trendByKey = {};
  (data.feature_trends || []).forEach((t) => {
    trendByKey[t.key] = t;
  });

  TREND_ANALYSIS_CHARTS.forEach(({ key, label, overall }) => {
    const values = data.series.map((p) => (overall ? p.overall_score : p.feature_scores[key]));
    const trend = trendByKey[key];

    const item = document.createElement("div");
    item.className = `trend-analysis-chart-item${overall ? " overall" : ""}`;

    let deltaHtml = "";
    if (trend) {
      const deltaText = trend.delta > 0 ? `+${trend.delta}` : `${trend.delta}`;
      const directionIcon = { improving: "▲", declining: "▼", stable: "–" }[trend.direction] || "–";
      deltaHtml = `<span class="trend-feature-delta">${directionIcon} ${deltaText}</span>`;
    }

    item.innerHTML = `
      <div class="trend-analysis-chart-label">
        <span>${label}</span>
        ${deltaHtml}
      </div>
      <svg class="trend-mini-chart" viewBox="0 0 140 48" aria-hidden="true"></svg>
    `;
    grid.appendChild(item);
    renderLineChartIntoSvg(item.querySelector("svg"), values, {
      width: 140,
      height: 48,
      padding: 6,
      dotRadius: 2,
    });
  });

  document.getElementById("trendAnalysisFeedbackText").textContent = data.ai_feedback;
}

async function runTrendAnalysis() {
  const btn = document.getElementById("trendAnalysisBtn");
  const card = document.getElementById("trendAnalysisCard");

  btn.disabled = true;
  const originalLabel = btn.textContent;
  btn.textContent = "분석 중...";

  try {
    const response = await fetch(`${API_BASE}/history/${getUserId()}/trend-analysis`);
    if (!response.ok) throw new Error(`이력분석 실패 (${response.status})`);
    const data = await response.json();
    renderTrendAnalysis(data);
    card.style.display = "block";
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (err) {
    alert("이력분석 중 오류가 발생했습니다: " + err.message);
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = originalLabel;
  }
}

// ---------------- 사용자 ID 입력 필드 ----------------
function initUserIdField() {
  const input = document.getElementById("userIdInput");
  const saveBtn = document.getElementById("userIdSaveBtn");

  input.value = getUserId();

  saveBtn.addEventListener("click", () => {
    const raw = input.value.trim();

    if (!raw) {
      alert("사용자 ID를 입력해주세요.");
      input.value = getUserId();
      return;
    }
    if (!/^[a-zA-Z0-9_-]{1,40}$/.test(raw)) {
      alert("ID는 영문/숫자/-/_ 조합으로 40자 이내로 입력해주세요.");
      return;
    }

    localStorage.setItem("skinscope_user_id", raw);
    input.value = raw;

    const originalLabel = saveBtn.textContent;
    saveBtn.textContent = "저장됨";
    setTimeout(() => {
      saveBtn.textContent = originalLabel;
    }, 1200);

    if (document.getElementById("screen-history").classList.contains("active")) {
      loadHistory();
    }
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") saveBtn.click();
  });
}

// ---------------- 홈 화면에 추가(PWA 설치) 안내 배너 ----------------
// Android/Chrome은 beforeinstallprompt 이벤트로 설치를 유도할 수 있지만,
// iOS Safari는 이 API 자체가 없어 사용자가 직접 "공유 버튼 → 홈 화면에
// 추가" 경로를 찾아야 한다. 이 경로를 모르는 사용자가 많으므로, 두 플랫폼
// 모두에게 안내 문구를 보여준다.
const INSTALL_BANNER_DISMISSED_KEY = "skinscope_install_banner_dismissed";

function isRunningStandalone() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

function isIOSDevice() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
}

function updateInstallBanner() {
  const banner = document.getElementById("installBanner");
  if (isRunningStandalone() || localStorage.getItem(INSTALL_BANNER_DISMISSED_KEY) === "true") {
    banner.style.display = "none";
    return;
  }

  document.getElementById("installBannerText").textContent = isIOSDevice()
    ? "홈 화면에 추가하고 더 빠르게 사용해보세요 — 하단 공유 버튼(⬆️)을 누른 뒤 \"홈 화면에 추가\"를 선택하세요."
    : "홈 화면에 추가하고 더 빠르게 사용해보세요 — 브라우저 메뉴에서 \"홈 화면에 추가\" 또는 \"앱 설치\"를 선택하세요.";
  banner.style.display = "flex";
}

function initInstallBanner() {
  document.getElementById("installBannerCloseBtn").addEventListener("click", () => {
    localStorage.setItem(INSTALL_BANNER_DISMISSED_KEY, "true");
    document.getElementById("installBanner").style.display = "none";
  });
}

// ---------------- 피드백 (FR-10) ----------------
function resetFeedbackUI() {
  state.selectedRating = null;
  document.querySelectorAll(".rating-btn").forEach((btn) => btn.classList.remove("selected"));
  document.getElementById("feedbackComment").value = "";
  document.getElementById("feedbackDone").style.display = "none";
  document.getElementById("feedbackCard").style.display = state.currentRecordId ? "block" : "none";
}

function initFeedback() {
  document.querySelectorAll(".rating-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.selectedRating = Number(btn.dataset.rating);
      document.querySelectorAll(".rating-btn").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
    });
  });

  document.getElementById("feedbackSubmitBtn").addEventListener("click", async () => {
    if (!state.currentRecordId) return;
    if (!state.selectedRating) {
      alert("만족도 점수를 선택해주세요.");
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE}/analyze/${state.currentRecordId}/feedback`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: getUserId(),
            rating: state.selectedRating,
            comment: document.getElementById("feedbackComment").value.trim() || null,
          }),
        }
      );
      if (!response.ok) throw new Error(`제출 실패 (${response.status})`);

      document.getElementById("feedbackDone").style.display = "block";
    } catch (err) {
      alert("피드백 제출 중 오류가 발생했습니다: " + err.message);
      console.error(err);
    }
  });
}

// ---------------- AI에게 물어보기 (챗봇, 로드맵 L) ----------------
function resetChatUI() {
  document.getElementById("chatMessageList").innerHTML = "";
  document.getElementById("chatInput").value = "";
  document.getElementById("chatCard").style.display = state.currentRecordId ? "block" : "none";
}

function renderAiMessage(el, text) {
  // AI 응답(RAG 검색 결과 포함)은 신뢰할 수 없는 텍스트로 취급해 innerHTML이
  // 아닌 textContent로 삽입한다 — 배지만 별도 엘리먼트로 만들어 붙인다(XSS 방지).
  el.innerHTML = "";
  const badge = document.createElement("span");
  badge.className = "chat-ai-badge";
  badge.textContent = "AI 생성 참고용 답변";
  el.appendChild(badge);
  el.appendChild(document.createTextNode(text));
}

function appendChatMessage(role, text) {
  const list = document.getElementById("chatMessageList");
  const el = document.createElement("div");
  el.className = `chat-message ${role}`;
  if (role === "ai") {
    renderAiMessage(el, text);
  } else {
    el.textContent = text;
  }
  list.appendChild(el);
  list.scrollTop = list.scrollHeight;
  return el;
}

async function sendChatMessage(question) {
  const trimmed = (question || "").trim();
  if (!trimmed || !state.currentRecordId) return;

  document.getElementById("chatInput").value = "";
  appendChatMessage("user", trimmed);
  const pendingEl = appendChatMessage("ai", "답변을 준비하고 있어요...");
  pendingEl.classList.add("pending");

  try {
    const response = await fetch(`${API_BASE}/analyze/${state.currentRecordId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: getUserId(), question: trimmed }),
    });
    if (!response.ok) throw new Error(`요청 실패 (${response.status})`);
    const data = await response.json();

    pendingEl.classList.remove("pending");
    renderAiMessage(pendingEl, data.answer);
  } catch (err) {
    pendingEl.classList.remove("pending");
    renderAiMessage(pendingEl, "지금은 답변이 어려워요, 잠시 후 다시 시도해주세요.");
    console.error(err);
  }
}

function initChat() {
  document.getElementById("chatSendBtn").addEventListener("click", () => {
    sendChatMessage(document.getElementById("chatInput").value);
  });
  document.getElementById("chatInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendChatMessage(document.getElementById("chatInput").value);
  });
  document.getElementById("chatSuggestionRow").addEventListener("click", (e) => {
    const chip = e.target.closest(".chat-suggestion-chip");
    if (chip) sendChatMessage(chip.dataset.question);
  });
}

// ---------------- 사용 방법 안내 팝업 ----------------
const GUIDE_SEEN_STORAGE_KEY = "skinscope_guide_seen";

function openGuideModal() {
  document.getElementById("guideModalOverlay").classList.add("active");
}

function closeGuideModal() {
  document.getElementById("guideModalOverlay").classList.remove("active");
  localStorage.setItem(GUIDE_SEEN_STORAGE_KEY, "true");
}

function initGuideModal() {
  document.getElementById("guideOpenBtn").addEventListener("click", openGuideModal);
  document.getElementById("guideCloseBtn").addEventListener("click", closeGuideModal);
  document.getElementById("guideConfirmBtn").addEventListener("click", closeGuideModal);
  document.getElementById("guideModalOverlay").addEventListener("click", (e) => {
    if (e.target.id === "guideModalOverlay") closeGuideModal();
  });

  // 처음 방문하는 사용자에게는 자동으로 한 번 보여준다.
  if (localStorage.getItem(GUIDE_SEEN_STORAGE_KEY) !== "true") {
    openGuideModal();
  }
}

// ---------------- 초기화 ----------------
function init() {
  initTabs();
  initConsent();
  initUserIdField();
  initFeedback();
  initChat();
  initProfileInputs();
  initGuideModal();
  initInstallBanner();
  initFaceDetection(); // 네트워크 로딩이 있어 카메라 시작 전에 미리 준비해둔다

  document.getElementById("trendAnalysisBtn").addEventListener("click", runTrendAnalysis);

  document.getElementById("shutterBtn").addEventListener("click", capturePhotoFromVideo);
  document.getElementById("cameraSwitchBtn").addEventListener("click", switchCamera);
  document.getElementById("fileTriggerBtn").addEventListener("click", () => {
    document.getElementById("fileInput").click();
  });

  document.getElementById("fileInput").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) onPhotoCaptured(file);
  });

  document.getElementById("analyzeBtn").addEventListener("click", submitAnalysis);
  document.getElementById("retakeBtn").addEventListener("click", resetCaptureUI);
  document.getElementById("newScanBtn").addEventListener("click", resetCaptureUI);

  document.getElementById("resultBackBtn").addEventListener("click", () => {
    if (state.returnScreen === "screen-history") {
      showScreen("screen-history");
      loadHistory();
    } else {
      resetCaptureUI();
    }
  });
  document.getElementById("retryFromResultBtn").addEventListener("click", resetCaptureUI);
  document.getElementById("shareResultBtn").addEventListener("click", shareResult);
  document.getElementById("cameraRetryBtn").addEventListener("click", recoverCamera);

  // 성분 검색 등으로 새 탭을 열었다가 돌아오는 경우, 모바일 브라우저가
  // 백그라운드 탭의 카메라 트랙을 강제 종료해두는 경우가 있다. 탭이 다시
  // 보이는 시점에 스캔 화면이면서 스트림이 죽어있으면 자동으로 복구한다.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    if (!state.consentGiven || state.capturedBlob) return;
    if (!isScanScreenActive()) return;
    if (!isCameraStreamLive()) {
      recoverCamera();
    }
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("service-worker.js").catch((err) => {
      console.warn("서비스워커 등록 실패:", err);
    });
  }
}

document.addEventListener("DOMContentLoaded", init);
