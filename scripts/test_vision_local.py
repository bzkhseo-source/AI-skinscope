"""
로컬 테스트용 스크립트.
사용법 (PowerShell, venv 활성화 상태):
    python scripts\\test_vision_local.py "C:\\path\\to\\skin_photo.jpg"
"""

import sys
import json
from pathlib import Path

# app 패키지를 찾을 수 있도록 프로젝트 루트를 경로에 추가
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.services.vision_service import analyze_skin_image  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python scripts\\test_vision_local.py <이미지_경로>")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(f"파일을 찾을 수 없습니다: {image_path}")
        sys.exit(1)

    mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    image_bytes = image_path.read_bytes()

    print("Gemini Vision 분석 요청 중...")
    result = analyze_skin_image(image_bytes, mime_type=mime_type)

    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()