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
  setFaceAlignedIndicator(false);
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

// ---------------- 분석 요청 ----------------
async function submitAnalysis() {
  if (!state.capturedBlob) return;

  const loadingOverlay = document.getElementById("loadingOverlay");
  loadingOverlay.classList.add("active");

  try {
    const location = await getLocation();

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
function splitEfficacyToBullets(text, maxLines) {
  if (!text) return [];
  return text
    .split(/(?<=[.!?])\s+|\n+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, maxLines);
}

function renderResult(result, thumbUrl) {
  const vision = result.vision;
  state.currentRecordId = result.record_id || null;
  state.currentVision = vision;
  state.currentNeedsDermatologist = result.needs_dermatologist;
  resetFeedbackUI();

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
  // 다이어그램 점(dot)은 화면에 계속 남아있는 요소이므로, 이전 결과의 색이
  // 남지 않도록 매번 기본 상태로 되돌린 뒤 새로 칠한다.
  REGION_ORDER.forEach((key) => {
    const dot = document.getElementById(`dot-${key}`);
    if (dot) dot.setAttribute("class", "region-dot");
  });

  if (vision.regional_scores) {
    regionalCard.style.display = "block";
    REGION_ORDER.forEach((key) => {
      const region = vision.regional_scores[key];
      if (!region) return;

      const composite = Math.round((region.pore + region.oiliness + region.trouble) / 3);
      const tier = regionScoreTier(composite);

      const dot = document.getElementById(`dot-${key}`);
      if (dot) dot.setAttribute("class", `region-dot ${tier}`);

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
  if (result.skin_age) {
    skinAgeBadge.style.display = "inline-block";
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
    skinAgeBadge.style.display = "none";
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
      title.textContent = `${group.concern_label_ko} 관리에 도움이 되는 성분`;
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
            <span class="ingredient-search">관련 화장품 검색 →</span>
          </div>
          ${bulletsHtml}
        `;
        groupDiv.appendChild(item);
      });

      productRecoList.appendChild(groupDiv);
    });
  } else {
    productRecoCard.style.display = "none";
  }

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

  document.getElementById("resultReport").style.display = "flex";

  // 결과 전용 화면으로 전환 (탭바에는 없는 화면이므로 showScreen 대신 직접 처리)
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.getElementById("screen-result").classList.add("active");
  document.querySelector(".app-header").classList.add("show-back");
}

// ---------------- 결과 공유 (FR 고도화: 사진은 공유 대상에서 제외) ----------------
function buildShareText() {
  const vision = state.currentVision;
  if (!vision) return "";

  const status = state.currentNeedsDermatologist ? "전문의 상담 권장" : "양호";
  const lines = [
    "[AI-SkinScope 스캔 결과]",
    `종합 점수: ${vision.overall_score}/100 (${status})`,
  ];
  if (vision.ai_focus) lines.push(`스캐닝 소견: ${vision.ai_focus}`);
  lines.push("본 결과는 AI 참고용 스크리닝이며 의료 진단이 아닙니다.");
  return lines.join("\n");
}

async function shareResult() {
  const text = buildShareText();
  if (!text) return;

  if (navigator.share) {
    try {
      await navigator.share({ title: "AI-SkinScope 스캔 결과", text });
    } catch (err) {
      if (err.name !== "AbortError") console.error(err);
    }
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
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

  listEl.innerHTML = "";
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
        <div class="score">${entry.overall_score}</div>
      `;
      div.addEventListener("click", () => openHistoryDetail(entry.id));
      listEl.appendChild(div);
    });
  } catch (err) {
    console.error(err);
    emptyEl.style.display = "block";
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
  initProfileInputs();
  initGuideModal();
  initFaceDetection(); // 네트워크 로딩이 있어 카메라 시작 전에 미리 준비해둔다

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
