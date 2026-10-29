#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/telegram.py
중앙 통합 텔레그램 알람 발송 모듈
(단일 창구로만 발송되며, 4096자 자동 분할 및 HTML 오류 자동 폴백 지원)
"""

import os
import json
import ssl
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def load_credentials() -> Tuple[str, str]:
    """단일 .env 및 환경변수에서 텔레그램 봇 토큰과 채널 ID 추출"""
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        if ENV_PATH.exists():
            try:
                with open(ENV_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k == "TELEGRAM_TOKEN" and not token:
                                token = v
                            elif k == "TELEGRAM_CHAT_ID" and not chat_id:
                                chat_id = v
            except Exception:
                pass

    # 최종 기본값 폴백
    token = token or "8928552590:AAG5uUN5qEQA1DYDCoT6DNPKRfZhSGt46go"
    chat_id = chat_id or "-5501244097"
    return token, chat_id


def split_message(text: str, max_chunk: int = 3800) -> List[str]:
    """메시지를 3800자 단위 안전 청크로 분할 (단락 단위 분할 우선)"""
    if len(text) <= max_chunk:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) + 2 <= max_chunk:
            current_chunk += ("\n\n" if current_chunk else "") + p
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # 만약 단락 자체가 너무 길면 줄 단위로 분할
            if len(p) > max_chunk:
                lines = p.split("\n")
                sub_chunk = ""
                for line in lines:
                    if len(sub_chunk) + len(line) + 1 <= max_chunk:
                        sub_chunk += ("\n" if sub_chunk else "") + line
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = line
                current_chunk = sub_chunk
            else:
                current_chunk = p

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def send_message(text: str, token: str = None, chat_id: str = None) -> bool:
    """통합 텔레그램 메시지 발송 함수 (HTML 실패 시 텍스트 폴백)"""
    if not token or not chat_id:
        token, chat_id = load_credentials()

    if not token or not chat_id:
        print("[core.telegram] ❌ 에러: TELEGRAM_TOKEN 또는 TELEGRAM_CHAT_ID 미설정")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = split_message(text)
    overall_success = True

    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=12, context=SSL_CTX) as res:
                result = json.loads(res.read().decode("utf-8"))
                if not result.get("ok"):
                    print(f"[core.telegram] ⚠️ 발송 응답 실패: {result}")
                    overall_success = False
        except urllib.error.HTTPError as e:
            # HTML 파싱 오류 시 HTML 태그 제거 후 plain text로 폴백 재시도
            try:
                err_body = e.read().decode("utf-8")
                if "can't parse entities" in err_body or e.code == 400:
                    payload.pop("parse_mode", None)
                    fallback_data = json.dumps(payload).encode("utf-8")
                    fallback_req = urllib.request.Request(url, data=fallback_data, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(fallback_req, timeout=12, context=SSL_CTX) as fb_res:
                        fb_result = json.loads(fb_res.read().decode("utf-8"))
                        if not fb_result.get("ok"):
                            overall_success = False
                else:
                    overall_success = False
            except Exception:
                overall_success = False
        except Exception as e:
            print(f"[core.telegram] ❌ 발송 예외 발생: {e}")
            overall_success = False

    return overall_success


if __name__ == "__main__":
    t, c = load_credentials()
    print(f"✅ Telegram Token: {t[:10]}... | Chat ID: {c}")
