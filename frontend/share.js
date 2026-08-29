// ============================================================
// AI-SkinScope — 공유 링크 전용 읽기 전용 뷰어
// index.html의 앱 로직과 별개로 동작하는 독립 스크립트다(사진 촬영,
// 로그인/동의, 이력 등 앱 전용 기능은 전혀 필요 없는 단순 조회 페이지).
// ============================================================

const LOCAL_HOSTNAME_PATTERN =
  /^(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})$/;

const API_BASE = LOCAL_HOSTNAME_PATTERN.test(location.hostname)
  ? `${location.protocol}//${location.hostname}:8000`
  : "https://ai-skinscope.onrender.com";

const FEATURE_LABELS = {
  pore: "모공",
  elasticity: "탄력",
  moisture: "수분",
  wrinkle: "주름",
  pigmentation: "색소침착",
  redness: "붉은기",
};

// app.js의 overallScoreTier()/featureScoreTier()와 동일한 기준.
function overallScoreTier(score) {
  if (score <= 40) return { cls: "derm", label: "피부과 전문의 진료 권고" };
  if (score <= 50) return { cls: "warn", label: "경고" };
  if (score <= 60) return { cls: "caution", label: "주의" };
  if (score <= 70) return { cls: "ok", label: "양호" };
  if (score <= 80) return { cls: "excellent", label: "매우양호" };
  return { cls: "top", label: "백옥 피부 미녀(미남)" };
}

function featureScoreTier(score) {
  if (score >= 80) return { cls: "excellent", label: "매우 양호" };
  if (score >= 60) return { cls: "ok", label: "양호" };
  if (score >= 40) return { cls: "caution", label: "주의" };
  return { cls: "warn", label: "관리 필요" };
}

function getTokenFromUrl() {
  return new URLSearchParams(location.search).get("token");
}

function renderSharedResult(result) {
  const tier = result.needs_dermatologist
    ? { cls: "derm", label: "피부과 전문의 진료 권고" }
    : overallScoreTier(result.overall_score);

  document.getElementById("scoreValue").textContent = result.overall_score;

  const scoreTierBadge = document.getElementById("scoreTierBadge");
  scoreTierBadge.textContent = tier.label;
  scoreTierBadge.className = `badge ${tier.cls}`;

  const scoreDesc = document.getElementById("scoreDescText");
  if (result.needs_dermatologist) {
    scoreDesc.textContent = "전문의 상담을 권장드려요. 가까운 피부과 방문을 고려해보세요.";
    scoreDesc.classList.add("warn");
  } else {
    scoreDesc.textContent = result.ai_focus || result.ai_summary || "";
  }

  const grid = document.getElementById("featureGrid");
  grid.innerHTML = "";
  Object.entries(result.feature_scores).forEach(([key, value]) => {
    const tier2 = featureScoreTier(value);
    const item = document.createElement("div");
    item.className = "feature-item";
    item.innerHTML = `
      <div class="feature-item-head">
        <span class="label">${FEATURE_LABELS[key] || key}</span>
        <span class="badge ${tier2.cls}">${tier2.label}</span>
      </div>
      <div class="num">${value}<small>/100</small></div>
      <div class="bar-track"><div class="bar-fill ${tier2.cls}" style="width:${value}%"></div></div>
    `;
    grid.appendChild(item);
  });

  if (result.ai_focus || result.ai_detail) {
    document.getElementById("aiOpinionCard").style.display = "block";
    const aiFocusEl = document.getElementById("aiFocusText");
    const aiDetailEl = document.getElementById("aiDetailText");
    if (result.ai_focus) {
      aiFocusEl.textContent = result.ai_focus;
      aiFocusEl.style.display = "block";
    }
    aiDetailEl.textContent = result.ai_detail || result.ai_summary || "";
  }

  if (result.care_tips && result.care_tips.length > 0) {
    document.getElementById("careTipsCard").style.display = "block";
    const tipsList = document.getElementById("careTipsList");
    tipsList.innerHTML = "";
    result.care_tips.forEach((tip) => {
      const li = document.createElement("li");
      li.textContent = tip;
      tipsList.appendChild(li);
    });
  }

  document.getElementById("shareLoading").style.display = "none";
  document.getElementById("shareReport").style.display = "flex";
}

function showShareError() {
  document.getElementById("shareLoading").style.display = "none";
  document.getElementById("shareError").style.display = "block";
}

async function init() {
  const token = getTokenFromUrl();
  if (!token) {
    showShareError();
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/share/${encodeURIComponent(token)}`);
    if (!response.ok) {
      showShareError();
      return;
    }
    const result = await response.json();
    renderSharedResult(result);
  } catch (err) {
    console.error(err);
    showShareError();
  }
}

document.addEventListener("DOMContentLoaded", init);
