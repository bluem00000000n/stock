#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/market_data.py
공통 시장 데이터 수집 및 캐싱 모듈
(네이버 증권, 야후 파이낸스, 환율, VIX, 미국 3대 지수 야간 선물 등)
"""

import json
import ssl
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, Any, Optional

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

_CACHE = {}


def fetch_url_json(url: str, timeout: int = 8) -> Optional[Dict[str, Any]]:
    """안전한 JSON API 호출"""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception:
        return None


def fetch_krx_price(code: str) -> Dict[str, Any]:
    """네이버 증권 모바일 API를 통한 국내 주식/ETF 실시간 시세 조회"""
    clean_code = code.strip().zfill(6)
    if f"krx_{clean_code}" in _CACHE:
        return _CACHE[f"krx_{clean_code}"]

    url = f"https://m.stock.naver.com/api/stock/{clean_code}/basic"
    data = fetch_url_json(url)

    res = {
        "code": clean_code,
        "name": "",
        "price": 0.0,
        "change_pct": 0.0,
        "volume": 0
    }

    if data:
        try:
            res["name"] = data.get("stockName", "")
            close_price_str = str(data.get("closePrice", "0")).replace(",", "")
            res["price"] = float(close_price_str)
            change_rate_str = str(data.get("fluctuationsRatio", "0")).replace(",", "")
            res["change_pct"] = float(change_rate_str)
            res["volume"] = int(str(data.get("accumulatedTradingVolume", "0")).replace(",", ""))
        except Exception:
            pass

    _CACHE[f"krx_{clean_code}"] = res
    return res


def fetch_us_price(ticker: str) -> Dict[str, Any]:
    """네이버 증권 해외 주식 API를 통한 미국 주식/ETF 실시간 시세 조회"""
    clean_ticker = ticker.strip().upper()
    if f"us_{clean_ticker}" in _CACHE:
        return _CACHE[f"us_{clean_ticker}"]

    res = {
        "ticker": clean_ticker,
        "name": clean_ticker,
        "price": 0.0,
        "change_pct": 0.0
    }

    # NASDAQ(.O), NYSE(.N), NYSE American(.K), bare ticker 순차 조회
    for suffix in [".O", ".N", ".K", ""]:
        sym = f"{clean_ticker}{suffix}"
        url = f"https://api.stock.naver.com/stock/{sym}/basic"
        data = fetch_url_json(url, timeout=4)
        if data and "closePrice" in data:
            try:
                res["name"] = data.get("stockName", clean_ticker)
                close_price_str = str(data.get("closePrice", "0")).replace(",", "")
                res["price"] = float(close_price_str)
                change_rate_str = str(data.get("fluctuationsRatio", "0")).replace(",", "")
                res["change_pct"] = float(change_rate_str)
                break
            except Exception:
                continue

    _CACHE[f"us_{clean_ticker}"] = res
    return res


def fetch_us_macro() -> Dict[str, Any]:
    """야간 미 증시 3대 지수, 환율, VIX 실시간 수집 (Naver Finance API)"""
    if "us_macro" in _CACHE:
        return _CACHE["us_macro"]

    result = {
        "dow": {"val": "-", "pct": 0.0},
        "nasdaq": {"val": "-", "pct": 0.0},
        "sp500": {"val": "-", "pct": 0.0},
        "usd_krw": "1,344.9",
        "us10y": "4.20%",
        "vix": "21.15"
    }

    # 1. 환율 (USD/KRW)
    try:
        fx_url = "https://api.stock.naver.com/marketindex/exchange/FX_USDKRW"
        fx_data = fetch_url_json(fx_url, timeout=4)
        if fx_data and "exchangeInfo" in fx_data:
            result["usd_krw"] = fx_data["exchangeInfo"].get("closePrice", "1,344.9")
    except Exception:
        pass

    # 2. 미국 3대 지수 및 VIX
    indices = {
        "dow": "https://api.stock.naver.com/index/.DJI/basic",
        "nasdaq": "https://api.stock.naver.com/index/.IXIC/basic",
        "sp500": "https://api.stock.naver.com/index/.INX/basic",
        "vix": "https://api.stock.naver.com/index/.VIX/basic"
    }

    for key, url in indices.items():
        try:
            d = fetch_url_json(url, timeout=4)
            if d and "closePrice" in d:
                price = str(d.get("closePrice", "-"))
                ratio = float(str(d.get("fluctuationsRatio", "0")).replace(",", ""))
                if key == "vix":
                    result["vix"] = price
                else:
                    result[key] = {"val": price, "pct": ratio}
        except Exception:
            pass

    _CACHE["us_macro"] = result
    return result


if __name__ == "__main__":
    macro = fetch_us_macro()
    samsung = fetch_krx_price("005930")
    print(f"환율: {macro['usd_krw']} | 나스닥: {macro['nasdaq']}")
    print(f"삼성전자: {samsung['name']} {samsung['price']:,}원 ({samsung['change_pct']}%)")
