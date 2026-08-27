# -*- coding: utf-8 -*-
"""
프론트엔드 정적 파일을 HTTPS로 서빙하는 로컬 테스트 전용 스크립트.

같은 Wi-Fi의 휴대폰에서 카메라 기능(getUserMedia)을 테스트하려면 브라우저가
"보안 컨텍스트"로 인식해야 하는데, localhost/127.0.0.1이 아닌 사설 LAN IP는
HTTP로는 보안 컨텍스트로 취급되지 않는다. 자체 서명 인증서(certs/)로 HTTPS를
띄워 이 문제를 우회한다. 처음 접속 시 브라우저의 "안전하지 않음" 경고는
자체 서명 인증서라 정상이며, "고급 > 계속 진행"을 누르면 된다.

사용법:
    python scripts\\serve_https.py
"""

import http.server
import ssl
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
CERT_PATH = Path(__file__).resolve().parent.parent / "certs" / "cert.pem"
KEY_PATH = Path(__file__).resolve().parent.parent / "certs" / "key.pem"
PORT = 5500


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)


def main() -> None:
    if not CERT_PATH.exists() or not KEY_PATH.exists():
        raise SystemExit(
            "인증서가 없습니다. 먼저 certs/cert.pem, certs/key.pem을 생성하세요."
        )

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(CERT_PATH), keyfile=str(KEY_PATH))

    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    print(f"HTTPS 프론트엔드 서버 시작: https://0.0.0.0:{PORT} (frontend/ 서빙)")
    print("같은 Wi-Fi의 휴대폰에서는 https://<이 PC의 LAN IP>:5500 으로 접속하세요.")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
