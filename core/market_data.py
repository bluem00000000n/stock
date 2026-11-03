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


def fetch_krx_market_summary() -> Dict[str, Any]:
    """
    국내 증시(코스피/코스닥) 마감 지수, 투자자별 수급 동향, 환율, 당일 주도 테마 수집 및 시황 진단
    """
    if "krx_market_summary" in _CACHE:
        return _CACHE["krx_market_summary"]

    summary = {
        "kospi": {"price": "-", "diff": "-", "pct": 0.0, "status": "CLOSED"},
        "kosdaq": {"price": "-", "diff": "-", "pct": 0.0, "status": "CLOSED"},
        "kospi_investors": {"foreign": "0", "inst": "0", "personal": "0"},
        "kosdaq_investors": {"foreign": "0", "inst": "0", "personal": "0"},
        "usd_krw": {"price": "1,340.0", "diff": "0.0", "pct": "0.0%"},
        "leading_themes": [],
        "market_diagnosis": "",
        "action_guide": ""
    }

    # 1. 코스피 / 코스닥 지수
    kospi_data = fetch_url_json("https://m.stock.naver.com/api/index/KOSPI/basic", timeout=4)
    if kospi_data:
        try:
            summary["kospi"] = {
                "price": str(kospi_data.get("closePrice", "-")),
                "diff": str(kospi_data.get("compareToPreviousClosePrice", "-")),
                "pct": float(str(kospi_data.get("fluctuationsRatio", "0")).replace(",", "")),
                "status": str(kospi_data.get("marketStatus", "CLOSED"))
            }
        except Exception:
            pass

    kosdaq_data = fetch_url_json("https://m.stock.naver.com/api/index/KOSDAQ/basic", timeout=4)
    if kosdaq_data:
        try:
            summary["kosdaq"] = {
                "price": str(kosdaq_data.get("closePrice", "-")),
                "diff": str(kosdaq_data.get("compareToPreviousClosePrice", "-")),
                "pct": float(str(kosdaq_data.get("fluctuationsRatio", "0")).replace(",", "")),
                "status": str(kosdaq_data.get("marketStatus", "CLOSED"))
            }
        except Exception:
            pass

    # 2. 투자자별 수급 (외인, 기관, 개인)
    k_trend = fetch_url_json("https://m.stock.naver.com/api/index/KOSPI/trend", timeout=4)
    if k_trend:
        summary["kospi_investors"] = {
            "foreign": str(k_trend.get("foreignValue", "0")),
            "inst": str(k_trend.get("institutionalValue", "0")),
            "personal": str(k_trend.get("personalValue", "0"))
        }

    q_trend = fetch_url_json("https://m.stock.naver.com/api/index/KOSDAQ/trend", timeout=4)
    if q_trend:
        summary["kosdaq_investors"] = {
            "foreign": str(q_trend.get("foreignValue", "0")),
            "inst": str(q_trend.get("institutionalValue", "0")),
            "personal": str(q_trend.get("personalValue", "0"))
        }

    # 3. 환율 (USD/KRW)
    fx_data = fetch_url_json("https://api.stock.naver.com/marketindex/exchange/FX_USDKRW", timeout=4)
    if fx_data and "exchangeInfo" in fx_data:
        info = fx_data["exchangeInfo"]
        summary["usd_krw"] = {
            "price": str(info.get("closePrice", "1,340.0")),
            "diff": str(info.get("fluctuations", "0.0")),
            "pct": str(info.get("fluctuationsRatio", "0.0")) + "%"
        }

    # 4. 당일 주도 테마 Top 4
    theme_data = fetch_url_json("https://m.stock.naver.com/api/stocks/theme", timeout=4)
    if theme_data and "groups" in theme_data:
        themes = []
        for g in theme_data.get("groups", [])[:4]:
            name = g.get("name", "")
            rate = g.get("changeRate", "0.0")
            themes.append(f"{name} (+{rate}%)")
        summary["leading_themes"] = themes

    # 5. 시장 수급 및 시황 종합 진단 생성
    kp_pct = summary["kospi"]["pct"]
    kd_pct = summary["kosdaq"]["pct"]
    k_for_raw = summary["kospi_investors"]["foreign"].replace(",", "").replace("+", "")
    k_inst_raw = summary["kospi_investors"]["inst"].replace(",", "").replace("+", "")
    try:
        k_for_val = int(k_for_raw)
        k_inst_val = int(k_inst_raw)
    except Exception:
        k_for_val = 0
        k_inst_val = 0

    if k_for_val < -5000 and k_inst_val < -2000:
        diag = "외인·기관 양대 시장 대규모 동반 순매도 출회, 기술주 및 대형주 중심 차익 실현에 따른 지수 조정 장세"
        guide = "동시호가 뇌동 종가매수 지양. 보유 주도주 손절/목표가 원칙 관리 및 분할 현금 비중 방어."
    elif k_for_val > 2000 and k_inst_val > 1000:
        diag = "외인·기관 쌍끌이 순매수 유입, 대형 주도주 및 지수 견인 강세 안도 랠리 장세"
        guide = "Stage 2 피봇 돌파 및 수급 스나이퍼 주도주 1차 목표가까지 홀딩 유지, 추세 추종."
    elif k_for_val > 0 and k_inst_val <= 0:
        diag = "외국인 선별 순매수 유입 속 기관 매물 소화, 실적 차별화 개별 모멘텀 장세"
        guide = "지수 연동형 매매보다는 실적 서프라이즈 및 VCP 돌파 종목 중심 선별 대응."
    elif kp_pct < -2.0 or kd_pct < -2.0:
        diag = "글로벌 매크로 불확실성 및 고환율 여파로 지수 변동성 확대 급락 장세"
        guide = "무리한 저점 매수/물타기 절대 금지, 손절 라인 철저 준수 및 리스크 최소화 집중."
    else:
        diag = "지수 숨고르기 속 주도 섹터(방산/전력/바이오 등) 중심 선별적 순환매 장세"
        guide = "정규 6종목 포트폴리오 황금비율 내 안정적 홀딩 대응, 원칙 체결 유지."

    summary["market_diagnosis"] = diag
    summary["action_guide"] = guide

    _CACHE["krx_market_summary"] = summary
    return summary


if __name__ == "__main__":
    macro = fetch_us_macro()
    samsung = fetch_krx_price("005930")
    kr_sum = fetch_krx_market_summary()
    print(f"환율: {macro['usd_krw']} | 나스닥: {macro['nasdaq']}")
    print(f"삼성전자: {samsung['name']} {samsung['price']:,}원 ({samsung['change_pct']}%)")
    print(f"코스피: {kr_sum['kospi']['price']} | 진단: {kr_sum['market_diagnosis']}")
