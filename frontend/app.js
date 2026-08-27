// ============================================================
// AI-SkinScope — 프론트엔드 로직
// ============================================================

// 로컬(127.0.0.1, localhost)에서는 로컬 백엔드를, 그 외(배포된 도메인)에서는
// Render 배포 백엔드를 자동으로 사용한다. 앞으로 API_BASE를 수동으로
// 바꿨다 되돌렸다 할 필요가 없다.
const API_BASE =
  location.hostname === "127.0.0.1" || location.hostname === "localhost"
    ? "http://127.0.0.1:8000"
    : "https://ai-skinscope.onrender.com";

const state = {
  stream: null,
  capturedBlob: null,
  consentGiven: false,
  currentRecordId: null,
  selectedRating: null,
  facingMode: "environment", // "environment"=후면, "user"=전면
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
async function startCamera() {
  const video = document.getElementById("cameraVideo");
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: state.facingMode },
      audio: false,
    });
    video.srcObject = state.stream;
    document.getElementById("viewfinderWrap").classList.add("scanning");
  } catch (err) {
    console.warn("카메라 접근 실패, 갤러리 선택으로 대체합니다.", err);
  }
}

function stopCamera() {
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
    state.stream = null;
  }
  document.getElementById("viewfinderWrap").classList.remove("scanning");
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

  // 전면 카메라는 좌우 반전되어 보이므로, 저장 시에는 원래 방향으로 되돌린다.
  if (state.facingMode === "user") {
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
  }
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

  document.getElementById("shutterBtn").style.display = "none";
  document.getElementById("fileTriggerBtn").style.display = "none";
  document.getElementById("cameraSwitchBtn").style.display = "none";
  document.getElementById("consentCard").style.display = "none";
  document.getElementById("analyzeBtn").style.display = "block";
  document.getElementById("retakeBtn").style.display = "block";
}

function resetCaptureUI() {
  state.capturedBlob = null;
  const video = document.getElementById("cameraVideo");
  const previewImg = document.getElementById("previewImg");
  video.style.display = "block";
  previewImg.style.display = "none";

  document.getElementById("viewfinderWrap").style.display = "";
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

function renderResult(result, thumbUrl) {
  const vision = result.vision;
  state.currentRecordId = result.record_id || null;
  resetFeedbackUI();

  // 상단 요약 카드 (사진 썸네일은 품질 실패 시에도 그대로 보여준다)
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
    document.getElementById("summaryScoreValue").textContent = "-";
    const summaryBadge = document.getElementById("summaryStatusBadge");
    summaryBadge.textContent = "재촬영 필요";
    summaryBadge.className = "badge warn";

    document.getElementById("qualityIssueText").textContent =
      vision.quality_note || "사진에서 피부 상태를 충분히 인식하지 못했습니다.";
    qualityCard.style.display = "block";
    reportEl.style.display = "none";

    document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
    document.getElementById("screen-result").classList.add("active");
    return;
  }

  qualityCard.style.display = "none";
  document.getElementById("summaryScoreValue").textContent = vision.overall_score;

  const summaryBadge = document.getElementById("summaryStatusBadge");
  const badge = document.getElementById("statusBadge");
  if (result.needs_dermatologist) {
    summaryBadge.textContent = "전문의 상담 권장";
    summaryBadge.className = "badge warn";
    badge.textContent = "전문의 상담 권장";
    badge.className = "badge warn";
  } else {
    summaryBadge.textContent = "양호";
    summaryBadge.className = "badge ok";
    badge.textContent = "양호";
    badge.className = "badge ok";
  }

  document.getElementById("scoreGauge").style.setProperty("--pct", vision.overall_score);
  document.getElementById("scoreValue").textContent = vision.overall_score;

  const grid = document.getElementById("featureGrid");
  grid.innerHTML = "";
  Object.entries(vision.feature_scores).forEach(([key, value]) => {
    const item = document.createElement("div");
    item.className = "feature-item";
    item.innerHTML = `
      <span class="label">${FEATURE_LABELS[key] || key}</span>
      <span class="num">${value}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${value}%"></div></div>
    `;
    grid.appendChild(item);
  });

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

  document.getElementById("aiSummaryText").textContent = vision.ai_summary;

  const tipsList = document.getElementById("careTipsList");
  tipsList.innerHTML = "";
  (vision.care_tips || []).forEach((tip) => {
    const li = document.createElement("li");
    li.textContent = tip;
    tipsList.appendChild(li);
  });

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

// ---------------- 초기화 ----------------
function init() {
  initTabs();
  initConsent();
  initUserIdField();
  initFeedback();

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
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("service-worker.js").catch((err) => {
      console.warn("서비스워커 등록 실패:", err);
    });
  }
}

document.addEventListener("DOMContentLoaded", init);
