# -*- coding: utf-8 -*-
"""
사용자가 제공한 최종 아이콘 원본(frontend/icons/Icon_raw.png, "AI-SkinScope"
텍스트가 함께 있는 목업 이미지)에서 텍스트를 제외한 글리프만 정사각형으로
잘라내 실제 PWA 아이콘 파일(icon-192.png, icon-512.png,
icon-512-maskable.png)을 만든다.

- 글리프 영역은 배경(흰색)이 아닌 픽셀의 바운딩 박스를 텍스트가 시작되기
  전 구간(y<955, 빈 줄로 확인됨)까지만 계산해 자동으로 찾는다.
- maskable 아이콘은 뷰파인더 코너 브라켓이 모서리에 가까워 원형 등으로
  잘리면 잘려나갈 수 있으므로, 글리프를 축소해 흰 배경 캔버스 중앙에
  배치한다.

사용법:
    python scripts\\crop_final_icons.py
"""

from pathlib import Path

import numpy as np
from PIL import Image

ICONS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "icons"
SOURCE_PATH = ICONS_DIR / "Icon_raw.png"

WHITE_THRESHOLD = 20  # 이 값보다 흰색에서 멀면 "내용 있음"으로 간주
# 행(row)별 내용 픽셀 수를 확인해보면 950px까지는 글리프(크로스헤어 끝
# 등)가 있다가 951~956은 완전히 빈 줄이고, 959부터 텍스트가 시작된다.
# 953을 상한으로 잡아 어느 쪽에도 걸치지 않는 여유를 둔다.
GLYPH_BBOX_CUTOFF = 951  # 바운딩 박스 계산에 사용할 y 상한(텍스트 제외)
CROP_MAX_Y = 953  # 패딩을 더해도 이 y좌표를 절대 넘지 않도록 강제
PADDING_RATIO = 0.04  # 글리프 바운딩 박스 주변 여백
MASKABLE_SCALE = 0.55  # 안전 영역(중심 반경 40% 이내) 확보를 위한 축소 비율


def find_glyph_box(arr: np.ndarray) -> tuple[int, int, int, int]:
    rgb = arr[..., :3].astype(int)
    non_white = np.abs(rgb - 255).sum(axis=-1) > WHITE_THRESHOLD
    non_white[GLYPH_BBOX_CUTOFF:, :] = False
    ys, xs = np.where(non_white)
    return xs.min(), ys.min(), xs.max(), ys.max()


def square_crop_box(box, padding_ratio, canvas_size, max_y):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = max(x1 - x0, y1 - y0) / 2 * (1 + padding_ratio)
    left, top = cx - half, cy - half
    right, bottom = cx + half, cy + half
    # 캔버스 밖으로 나가지 않게, 그리고 텍스트 영역을 침범하지 않게 자름
    left, top = max(0, left), max(0, top)
    right = min(canvas_size, right)
    bottom = min(max_y, bottom)
    # bottom이 깎여 정사각형이 아니게 됐다면 짧은 변에 맞춰 다시 정사각형화
    side = min(right - left, bottom - top)
    return round(left), round(top), round(left + side), round(top + side)


def main() -> None:
    source = Image.open(SOURCE_PATH).convert("RGBA")
    arr = np.array(source)

    glyph_box = find_glyph_box(arr)
    crop_box = square_crop_box(glyph_box, PADDING_RATIO, source.width, CROP_MAX_Y)
    glyph = source.crop(crop_box)

    glyph.resize((512, 512), Image.LANCZOS).save(ICONS_DIR / "icon-512.png")
    glyph.resize((192, 192), Image.LANCZOS).save(ICONS_DIR / "icon-192.png")

    # maskable: 흰 배경 512 캔버스 중앙에 글리프를 축소해서 배치
    canvas = Image.new("RGBA", (512, 512), (255, 255, 255, 255))
    scaled_size = round(512 * MASKABLE_SCALE)
    scaled_glyph = glyph.resize((scaled_size, scaled_size), Image.LANCZOS)
    offset = ((512 - scaled_size) // 2, (512 - scaled_size) // 2)
    canvas.paste(scaled_glyph, offset, scaled_glyph)
    canvas.save(ICONS_DIR / "icon-512-maskable.png")

    print(f"glyph bbox(원본 기준): {glyph_box}, crop box: {crop_box}")
    print("생성 완료: icon-192.png, icon-512.png, icon-512-maskable.png")


if __name__ == "__main__":
    main()
