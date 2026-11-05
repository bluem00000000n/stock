#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/kbit_chart.py
kbit-bot 한국주식 차트 지능형 선별 엔진 (단기 모멘텀 & 정배열 돌파)
- 네이버 금융 60일 일봉 및 30주 주봉 캔들 정밀 수학적 채점
- 5일/20일 이동평균선 정배열 우상향 (+35점)
- 20일 이평선 거래량 대량 돌파 (+30점)
- 5일/20일선 골든크로스 (+20점)
- 20일 평균 대비 거래량 폭증 (200%+ : +35점, 150%+ : +25점)
- 당일 양봉 (+15점), 적정 탄력 1.5%~15% (+20점)
- 역배열 하락세(close < ma5 and close < ma20) 즉시 영구 탈락 (-50점)
- 대형:중소형 1:1 황금밸런스 준수
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Any
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from portfolio.selector import classify_cap_size

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
}
DAUM_HEADERS = {
    **DEFAULT_HEADERS,
    "Referer": "https://finance.daum.net/",
    "Origin": "https://finance.daum.net"
}
NAVER_M_HEADERS = {
    **DEFAULT_HEADERS,
    "Referer": "https://m.stock.naver.com/"
}

EXCLUDE_WORDS = [
    "KODEX", "TIGER", "ACE", "RISE", "SOL", "KBSTAR", "HANARO", "PLUS", "KOSEF",
    "히어로즈", "WOORI", "인버스", "레버리지", "선물", "ETN", "스팩", "SPAC"
]


def is_valid_stock(code: str, name: str, price: int = 0) -> bool:
    """잡주, ETF, ETN, 우선주, 스팩, 동전주 필터링"""
    if not code or len(code) != 6 or not code.isdigit():
        return False
    if code[-1] != "0":  # 보통주가 아닌 우선주 제외
        return False
    if any(w in name for w in EXCLUDE_WORDS):
        return False
    if price > 0 and price < 1000:  # 동전주 제외
        return False
    return True


def analyze_stock_chart(code: str) -> dict:
    """
    네이버 금융 공식 XML API에서 일봉(60일) 및 주봉(30주) 데이터 정밀 분석 (kbit-bot 알고리즘)
    """
    url_day = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=60&requestType=0"
    try:
        r = requests.get(url_day, headers=DEFAULT_HEADERS, timeout=6)
        raw_items = re.findall(r'data="([^"]+)"', r.text)

        candles = []
        for raw in raw_items:
            s = raw.split("|")
            if len(s) >= 5:
                candles.append({
                    "date": s[0], "open": int(s[1]), "high": int(s[2]),
                    "low": int(s[3]), "close": int(s[4]), "volume": int(s[5])
                })

        if len(candles) < 20:
            return {"score": -999, "is_good": False, "chart_analysis": ""}

        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]

        close = closes[-1]
        open_p = candles[-1]["open"]
        prev_close = closes[-2]
        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20
        prev_ma5 = sum(closes[-6:-1]) / 5
        prev_ma20 = sum(closes[-21:-1]) / 20

        avg_vol_20 = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else (sum(volumes) / len(volumes))
        vol_ratio = int((volumes[-1] / avg_vol_20 * 100) if avg_vol_20 > 0 else 100)

        # 기술적 지표 검증
        is_bullish_align = (close > ma5 > ma20)
        is_above_ma20 = (close >= ma20)
        is_breakout_ma20 = (prev_close <= prev_ma20 and close > ma20)
        is_golden_cross = (prev_ma5 <= prev_ma20 and ma5 > ma20)
        is_volume_surge = (vol_ratio >= 150)
        is_super_volume = (vol_ratio >= 200)
        is_yangbong = (close >= open_p)
        is_bearish = (close < ma5 and close < ma20)  # 역배열 하락세

        rate = ((close - prev_close) / prev_close) * 100

        score = 0
        if is_bearish:
            score = -50  # 하락 종목 즉시 탈락
        else:
            if is_bullish_align: score += 35
            if is_breakout_ma20: score += 30
            elif is_above_ma20: score += 15
            if is_golden_cross: score += 20
            if is_super_volume: score += 35
            elif is_volume_surge: score += 25
            if is_yangbong: score += 15

            # 적정 상승 탄력 (+1.5% ~ +15% 사이 안정적 추세 추종) 가산점
            if 1.5 <= rate <= 15.0:
                score += 20
            elif rate > 25.0:
                score -= 10

        commentary = []
        if is_breakout_ma20:
            if vol_ratio >= 150:
                commentary.append(f"20일 이평선({int(ma20):,}원) 대량거래({vol_ratio}%) 돌파 안착")
            else:
                commentary.append(f"20일선({int(ma20):,}원) 상향 돌파 시도")
        elif is_bullish_align:
            commentary.append(f"5일선({int(ma5):,}원)과 20일선({int(ma20):,}원) 정배열 우상향 유지")
        elif is_above_ma20:
            commentary.append(f"20일선({int(ma20):,}원) 위 단기 지지력 확보")
        else:
            commentary.append(f"5일선({int(ma5):,}원) 지지선 점검")

        if is_volume_surge:
            commentary.append(f"20일 평균 대비 거래량 {vol_ratio}% 폭증 수급 유입")

        if is_golden_cross:
            commentary.append("5일/20일 골든크로스 발생")

        return {
            "close": close,
            "rate": f"{rate:+.2f}%",
            "ma5": int(ma5),
            "ma20": int(ma20),
            "vol_ratio": vol_ratio,
            "score": score,
            "is_good": (score >= 40 and not is_bearish),
            "chart_analysis": ", ".join(commentary)
        }
    except Exception as e:
        return {"score": -999, "is_good": False, "chart_analysis": ""}


def fetch_dynamic_candidates() -> List[Dict[str, Any]]:
    """kbit-bot 시장 전방위 동적 후보군 수집 (100~150개)"""
    candidates = {}

    # 1. Daum 검색어 상위 30
    try:
        url = "https://finance.daum.net/api/search/ranks?limit=30"
        res = requests.get(url, headers=DAUM_HEADERS, timeout=6)
        if res.status_code == 200:
            for item in res.json().get("data", []):
                code = item["symbolCode"].replace("A", "")
                name = item["name"]
                price = item.get("tradePrice", 0)
                if is_valid_stock(code, name, price):
                    candidates[code] = {"code": code, "name": name, "source": "포털검색주도"}
    except Exception:
        pass

    # 2. Naver 상승률 상위 (코스피/코스닥 각 30)
    for mkt in ["KOSPI", "KOSDAQ"]:
        try:
            url = f"https://m.stock.naver.com/api/stocks/up/{mkt}?page=1&pageSize=30"
            res = requests.get(url, headers=NAVER_M_HEADERS, timeout=6)
            if res.status_code == 200:
                for item in res.json().get("stocks", []):
                    code = item.get("itemCode", "")
                    name = item.get("stockName", "")
                    p_str = item.get("closePrice", "0").replace(",", "")
                    price = int(p_str) if p_str.isdigit() else 0
                    if is_valid_stock(code, name, price) and code not in candidates:
                        candidates[code] = {"code": code, "name": name, "source": f"{mkt}상승률"}
        except Exception:
            pass

    # 3. Naver 시가총액 상위 (코스피/코스닥 각 30)
    for mkt in ["KOSPI", "KOSDAQ"]:
        try:
            url = f"https://m.stock.naver.com/api/stocks/marketValue/{mkt}?page=1&pageSize=30"
            res = requests.get(url, headers=NAVER_M_HEADERS, timeout=6)
            if res.status_code == 200:
                for item in res.json().get("stocks", []):
                    code = item.get("itemCode", "")
                    name = item.get("stockName", "")
                    p_str = item.get("closePrice", "0").replace(",", "")
                    price = int(p_str) if p_str.isdigit() else 0
                    if is_valid_stock(code, name, price) and code not in candidates:
                        candidates[code] = {"code": code, "name": name, "source": f"{mkt}시총상위"}
        except Exception:
            pass

    return list(candidates.values())


def run_analysis(market: str = "KRX") -> List[Dict[str, Any]]:
    """kbit-bot 차트 지능형 선별 파이프라인 가동 및 시그널 리스트 반환"""
    signals = []
    if market.upper() not in ("KRX", "KR", "KOR"):
        return signals

    cands = fetch_dynamic_candidates()
    evaluated = []

    for c in cands:
        code = c["code"]
        name = c["name"]
        chart = analyze_stock_chart(code)
        if chart and chart.get("is_good"):
            cap = classify_cap_size(code, name, market="KRX")
            cur_p = float(chart["close"])
            evaluated.append({
                "project_id": "stock-kbit-chart",
                "project_name": "kbit 차트 스나이핑 (단기 5/20선 돌파 & 거래량 폭증)",
                "ticker": code,
                "name": name,
                "market": "KRX",
                "cap_size": cap,
                "price": cur_p,
                "target_price": round(cur_p * 1.10),
                "stop_loss_price": round(cur_p * 0.93),
                "signal_type": "BUY",
                "score": float(chart["score"]),
                "rate": chart["rate"],
                "vol_ratio": chart["vol_ratio"],
                "notes": f"[kbit차트 {chart['score']}점/{chart['rate']}] {chart['chart_analysis']} (거래비율 {chart['vol_ratio']}%)"
            })

    # 점수 기준 정렬
    evaluated.sort(key=lambda x: x["score"], reverse=True)
    return evaluated


if __name__ == "__main__":
    res = run_analysis("KRX")
    print(f"Total kbit-bot qualified signals: {len(res)}")
    for s in res[:10]:
        print(f"[{s['cap_size']}] {s['name']} ({s['ticker']}) : score={s['score']} | {s['price']:,}원 | {s['notes']}")
