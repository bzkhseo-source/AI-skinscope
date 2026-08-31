"""사진 분석 정확도 개선을 위한 전처리 모듈.

목표는 세 가지다.
1. 조명색 편차 완화 — 실내 백열등/LED/자연광에 따라 같은 피부도 사진마다
   다르게 찍히는 색 편차를 줄여, redness/pigmentation/moisture 점수의
   조명 의존도를 낮춘다.
2. 질감(모공/주름) 가시성 강화 — 색상(HSV의 H/S)은 그대로 두고 밝기(V)
   채널에만 로컬 대비를 강화해, 색 정보 손실 없이 미세 질감을 더 잘
   보이게 한다.
3. 명백히 분석 불가능한 사진(과다 노출/암부)을 Gemini 호출 전에 걸러내
   불필요한 API 비용과 지연을 줄인다.

주의: 화이트밸런스 보정은 "장면 평균이 무채색"이라는 gray-world 가정을
그대로 쓰지 않는다. 얼굴 클로즈업 사진의 평균색은 원래 살구/분홍빛이라,
gray-world를 100% 적용하면 자연스러운 홍조/붉은기까지 지워 버려 오히려
redness 판단 근거를 훼손한다. 그래서 보정 강도를 절반 이하로 낮추고
채널별 보정 계수에 상한/하한을 둬 "명백한 색 편차만 완화"하는 수준으로
제한한다.
"""

import io
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

# ---- 화이트밸런스 보정 파라미터 ----
# strength: gray-world 보정치를 몇 %만 반영할지 (1.0 = 완전 적용, 0.0 = 미적용).
#   자연스러운 피부 붉은기까지 지우지 않도록 절반 이하로 제한한다.
WB_STRENGTH = 0.4
# 채널별 보정 계수의 허용 범위. 이 범위를 벗어나는 극단적 보정은 하지 않는다
# (색 편차가 아주 심한 사진이라도 원본 톤을 크게 훼손하지 않기 위한 안전장치).
WB_MIN_GAIN = 0.85
WB_MAX_GAIN = 1.15

# ---- 질감 강조 파라미터 (HSV V채널 언샤프마스킹) ----
TEXTURE_UNSHARP_RADIUS = 3
TEXTURE_UNSHARP_PERCENT = 140
TEXTURE_UNSHARP_THRESHOLD = 2
TEXTURE_AUTOCONTRAST_CUTOFF = 1  # %

# ---- 품질 사전평가 파라미터 ----
# 아래 비율을 넘으면 "명백히 분석 불가능"으로 보고 Gemini 호출 전에
# 조기 반환한다. 애매한 경우까지 여기서 걸러내면 정상 사진을 오탐으로
# 되돌려보낼 위험이 있으므로, 기존 프롬프트의 "관대하게 판단하라" 원칙과
# 동일하게 아주 극단적인 경우만 잡도록 임계값을 보수적으로 잡는다.
EXTREME_DARK_PIXEL_THRESHOLD = 25  # 0~255 밝기 이 값 미만이면 "암부"로 카운트
EXTREME_DARK_RATIO = 0.97  # 프레임의 97% 이상이 암부면 조기 실패
EXTREME_BRIGHT_PIXEL_THRESHOLD = 235
EXTREME_BRIGHT_RATIO = 0.97

# 블러(초점) 정도는 이미지 해상도/피사체 거리에 따라 라플라시안 분산 값이
# 크게 달라져 안전한 절대 임계값을 잡기 어렵다(실측 데이터로 보정된 값이
# 아님). 그래서 하드 차단에는 쓰지 않고, 값 자체를 품질 메트릭으로만
# 계산해 Gemini 프롬프트에 참고 정보로 넘긴다.


@dataclass
class QualityMetrics:
    blur_variance: float
    mean_brightness: float
    dark_ratio: float
    bright_ratio: float

    @property
    def is_extreme_failure(self) -> bool:
        return self.dark_ratio >= EXTREME_DARK_RATIO or self.bright_ratio >= EXTREME_BRIGHT_RATIO

    @property
    def failure_note(self) -> str:
        if self.dark_ratio >= EXTREME_DARK_RATIO:
            return "사진이 너무 어둡습니다. 밝은 곳에서 다시 촬영해 주세요."
        if self.bright_ratio >= EXTREME_BRIGHT_RATIO:
            return "사진이 너무 밝게(과다노출) 촬영되었습니다. 다시 촬영해 주세요."
        return ""


@dataclass
class PreprocessResult:
    quality: QualityMetrics
    # 아래 두 필드는 quality.is_extreme_failure가 True면 None이다
    # (Gemini를 호출하지 않으므로 만들 필요가 없다).
    wb_corrected_jpeg: Optional[bytes]
    texture_enhanced_jpeg: Optional[bytes]


def assess_image_quality(image: Image.Image) -> QualityMetrics:
    """블러(라플라시안 분산)·평균 밝기·암부/명부 비율을 계산한다.
    scipy/cv2 없이 numpy 3x3 컨볼루션만으로 계산해 의존성을 늘리지 않는다."""
    gray = np.asarray(image.convert("L"), dtype=np.float64)

    # 3x3 라플라시안 커널 [[0,1,0],[1,-4,1],[0,1,0]]을 경계를 잘라내고 직접 적용.
    center = gray[1:-1, 1:-1]
    up = gray[:-2, 1:-1]
    down = gray[2:, 1:-1]
    left = gray[1:-1, :-2]
    right = gray[1:-1, 2:]
    laplacian = up + down + left + right - 4 * center
    blur_variance = float(laplacian.var()) if laplacian.size else 0.0

    mean_brightness = float(gray.mean())
    dark_ratio = float((gray < EXTREME_DARK_PIXEL_THRESHOLD).mean())
    bright_ratio = float((gray > EXTREME_BRIGHT_PIXEL_THRESHOLD).mean())

    return QualityMetrics(
        blur_variance=blur_variance,
        mean_brightness=mean_brightness,
        dark_ratio=dark_ratio,
        bright_ratio=bright_ratio,
    )


def correct_white_balance(image: Image.Image) -> Image.Image:
    """완화된 gray-world 화이트밸런스 보정.

    채널별 평균을 전체 평균(무채색 기준)에 맞추되, WB_STRENGTH만큼만
    부분 적용하고 WB_MIN_GAIN~WB_MAX_GAIN으로 보정폭을 제한한다. 얼굴
    사진은 원래 평균색이 살구빛이므로 완전한 gray-world를 적용하면
    자연스러운 피부 붉은기까지 지워버리기 때문이다.
    """
    rgb = image.convert("RGB")
    arr = np.asarray(rgb, dtype=np.float64)

    channel_means = arr.reshape(-1, 3).mean(axis=0)
    channel_means = np.clip(channel_means, 1.0, None)
    gray_mean = channel_means.mean()

    raw_gains = gray_mean / channel_means
    dampened_gains = 1.0 + WB_STRENGTH * (raw_gains - 1.0)
    gains = np.clip(dampened_gains, WB_MIN_GAIN, WB_MAX_GAIN)

    corrected = np.clip(arr * gains, 0, 255).astype(np.uint8)
    return Image.fromarray(corrected, mode="RGB")


def enhance_texture(image: Image.Image) -> Image.Image:
    """HSV의 V(밝기) 채널에만 언샤프마스킹 + 오토컨트라스트를 적용해
    모공/주름 등 미세 질감을 강조한다. H(색상)/S(채도)는 원본을 그대로
    유지해, redness/pigmentation/personal_color 판단에 쓰이는 색 정보를
    훼손하지 않는다."""
    hsv = image.convert("RGB").convert("HSV")
    h, s, v = hsv.split()

    v_enhanced = v.filter(
        ImageFilter.UnsharpMask(
            radius=TEXTURE_UNSHARP_RADIUS,
            percent=TEXTURE_UNSHARP_PERCENT,
            threshold=TEXTURE_UNSHARP_THRESHOLD,
        )
    )
    v_enhanced = ImageOps.autocontrast(v_enhanced, cutoff=TEXTURE_AUTOCONTRAST_CUTOFF)

    enhanced_hsv = Image.merge("HSV", (h, s, v_enhanced))
    return enhanced_hsv.convert("RGB")


def _to_jpeg_bytes(image: Image.Image, quality: int = 90) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def preprocess_for_analysis(image_bytes: bytes) -> PreprocessResult:
    """분석 파이프라인의 진입점. 실패해도 예외를 던지지 않고, 각 단계가
    실패하면 해당 단계만 원본으로 대체해 전체 분석이 막히지 않게 한다."""
    image = Image.open(io.BytesIO(image_bytes))
    image.load()
    # EXIF Orientation 태그를 반영해 회전/미러링된 상태로 저장된 사진도
    # 올바른 방향으로 맞춘다 (일부 기기/브라우저 조합에서 발생 가능).
    image = ImageOps.exif_transpose(image) or image
    image = image.convert("RGB")

    quality = assess_image_quality(image)

    if quality.is_extreme_failure:
        return PreprocessResult(quality=quality, wb_corrected_jpeg=None, texture_enhanced_jpeg=None)

    try:
        wb_image = correct_white_balance(image)
    except Exception as exc:  # noqa: BLE001
        logger.warning("화이트밸런스 보정 실패, 원본으로 대체합니다: %s", exc)
        wb_image = image

    try:
        texture_image = enhance_texture(wb_image)
    except Exception as exc:  # noqa: BLE001
        logger.warning("질감 강조 실패, 원본으로 대체합니다: %s", exc)
        texture_image = wb_image

    return PreprocessResult(
        quality=quality,
        wb_corrected_jpeg=_to_jpeg_bytes(wb_image),
        texture_enhanced_jpeg=_to_jpeg_bytes(texture_image),
    )
