#!/usr/bin/env python3
"""
Stock Supervisor - 로컬 뷰어 서버
로컬 환경에서 바로 대시보드를 열어보고 상태를 갱신할 수 있는 간이 HTTP 서버입니다.
사용법: python3 serve.py [포트번호 (기본 8080)]
"""

import sys
import os
import webbrowser
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class SupervisorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        # /api/refresh 요청 시 update_status.py 재실행 후 status.json 반환
        if self.path.startswith('/api/refresh'):
            try:
                subprocess.run([sys.executable, os.path.join(DIRECTORY, "update_status.py")], check=True)
                json_path = os.path.join(DIRECTORY, "data", "status.json")
                with open(json_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
                return
        return super().do_GET()

def run():
    # 최초 실행 시 데이터 최신화 1회 수행
    try:
        subprocess.run([sys.executable, os.path.join(DIRECTORY, "update_status.py")], check=True)
    except Exception as e:
        print(f"Warning: Initial status update failed: {e}")

    server_address = ('', PORT)
    httpd = HTTPServer(server_address, SupervisorHandler)
    url = f"http://localhost:{PORT}"
    print(f"🚀 Stock Supervisor 로컬 서버 구동 중: {url}")
    print("브라우저에서 대시보드를 확인하세요 (종료하려면 Ctrl+C)")
    
    # 브라우저 자동 오픈
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
        httpd.server_close()

if __name__ == '__main__':
    run()
