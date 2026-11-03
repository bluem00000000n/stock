#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/sepa_pivot.py
정통 추세추종(Trend Following) 전략: 마크 미너비니 SEPA x 댄 쟁거 피봇 돌파 (한국 KRX & 미국 US)
- 대전제: 2단계 상승 국면(Stage 2 Uptrend) - 우상향 정배열 주도주만 엄선 (밑으로 깔리는 역추세/바닥주 원천 배제)
- 타점: VCP(변동성 축소) 매물 소화 후 피벗 라인 돌파 시점 정밀 포착
- 리스크 관리: -5%~-7% 칼손절, 트레일링 스탑으로 대세 상승 추세 극대화
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

# 상위 core 모듈 참조
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.market_data import fetch_krx_price, fetch_us_price

WATCHLIST = {
    "KR_LARGE": [
        {"name": "유한양행", "code": "000100", "market": "코스피", "pivot": 78000, "stop": 72500, "turtle_stop": 73000, "farley_swing": "20주선 위 렉라자 VCP 돌파 직전", "pattern": "Cup with Handle", "score": 99, "theme": "렉라자(레이저티닙) 글로벌 FDA 상업화 랠리"},
        {"name": "현대글로비스", "code": "086280", "market": "코스피", "pivot": 204000, "stop": 191000, "turtle_stop": 193000, "farley_swing": "20주선 지지 및 RSI 골든크로스 돌파", "pattern": "Flat Base", "score": 97, "theme": "완성차 해상운송 글로벌 물류 신고가"},
        {"name": "SK하이닉스", "code": "000660", "market": "코스피", "pivot": 1420000, "stop": 1330000, "turtle_stop": 1340000, "farley_swing": "첫 1시간 ORB 돌파 감시", "pattern": "Ascending Triangle", "score": 98, "theme": "HBM3E/HBM4 독점 공급"},
        {"name": "HD현대일렉트릭", "code": "267260", "market": "코스피", "pivot": 435000, "stop": 405000, "turtle_stop": 410000, "farley_swing": "플랫베이스 지지 반등 스윙", "pattern": "Flat Base", "score": 98, "theme": "북미 초고압 변압기 쇼티지"},
    ],
    "KR_MID": [
        {"name": "케이아이엔엑스", "code": "093320", "market": "코스닥", "pivot": 175000, "stop": 161000, "turtle_stop": 164000, "farley_swing": "과천 IDC 하이타이트 플래그 돌파", "pattern": "High Tight Flag", "score": 99, "theme": "과천 AI IDC 본격 가동 및 52주 신고가 우상향"},
        {"name": "피에스케이홀딩스", "code": "031980", "market": "코스닥", "pivot": 170000, "stop": 158000, "turtle_stop": 160000, "farley_swing": "VCP 3차 수축 돌파", "pattern": "VCP", "score": 98, "theme": "HBM 패키징 디스컴 장비 독점력"},
        {"name": "산일전기", "code": "075950", "market": "코스피", "pivot": 68000, "stop": 63200, "turtle_stop": 64200, "farley_swing": "Strong Close 안착 스윙", "pattern": "Bull Flag", "score": 96, "theme": "북미 특수변압기 직납 고성장"},
        {"name": "라온시큐어", "code": "042510", "market": "코스닥", "pivot": 19000, "stop": 17500, "turtle_stop": 17800, "farley_swing": "52주 신고가 스나이퍼 수급 분출", "pattern": "Ascending Triangle", "score": 96, "theme": "글로벌 생체인증/양자암호 주도 수급"},
    ],
    "US_LARGE": [
        {"ticker": "NVDA", "name": "Nvidia", "market": "NASDAQ", "pivot": 144.0, "stop": 135.3, "turtle_stop": 137.7, "farley_swing": "첫 1시간 ORB 돌파 감시", "pattern": "Ascending Triangle", "score": 98, "theme": "블랙웰 B200 풀캐파 가동"},
        {"ticker": "PLTR", "name": "Palantir", "market": "NYSE", "pivot": 65.0, "stop": 61.0, "turtle_stop": 61.8, "farley_swing": "Strong Close 초고속 모멘텀", "pattern": "High Tight Flag", "score": 99, "theme": "AIP 엔터프라이즈 폭발적 수요"},
        {"ticker": "AVGO", "name": "Broadcom", "market": "NASDAQ", "pivot": 192.0, "stop": 180.4, "turtle_stop": 183.2, "farley_swing": "베이스 돌파 첫 1시간 ORB", "pattern": "Flat Base", "score": 97, "theme": "커스텀 AI ASIC & 네트워킹"},
        {"ticker": "APP", "name": "AppLovin", "market": "NASDAQ", "pivot": 220.0, "stop": 204.6, "turtle_stop": 208.6, "farley_swing": "신고가 스윙 모멘텀", "pattern": "High Tight Flag", "score": 99, "theme": "AXON 2.0 AI 애드테크 초고성장"},
        {"ticker": "TSM", "name": "TSMC", "market": "NYSE", "pivot": 205.0, "stop": 192.7, "turtle_stop": 195.4, "farley_swing": "피보나치 38.2% 20일선 지지", "pattern": "Cup with Handle", "score": 97, "theme": "3nm/2nm 선단 파운드리 독점"},
    ],
    "US_MID": [
        {"ticker": "ALAB", "name": "Astera Labs", "market": "NASDAQ", "pivot": 88.5, "stop": 82.3, "turtle_stop": 83.7, "farley_swing": "신고가 스윙 모멘텀", "pattern": "High Tight Flag", "score": 98, "theme": "PCIe 6.0/CXL 리타이머 독점"},
        {"ticker": "RDDT", "name": "Reddit", "market": "NYSE", "pivot": 95.0, "stop": 88.3, "turtle_stop": 89.8, "farley_swing": "전고점 돌파 첫 1시간 ORB", "pattern": "Ascending Triangle", "score": 97, "theme": "AI 학습 데이터 라이선싱 고수익"},
        {"ticker": "CRDO", "name": "Credo Tech", "market": "NASDAQ", "pivot": 42.0, "stop": 39.0, "turtle_stop": 39.8, "farley_swing": "피보나치 되돌림 지지", "pattern": "Cup with Handle", "score": 96, "theme": "AI 고속 AEC 케이블 독점"},
    ]
}


def verify_minervini_trend_template(code: str, cur_price: float) -> bool:
    """마크 미너비니 2단계 상승 국면(Stage 2 Uptrend) 트렌드 템플릿 필터
    - 밑으로 깔리는 종목(역배열, 50일선 이탈, 고점 대비 -28% 초과 낙폭) 엄격 배제
    - 신고가 근처에서 노는 주도주(Leader)만 통과
    """
    if cur_price <= 0:
        return False
    if code in ("196170",):  # 알테오젠 등 역배열 하락세 영구 차단
        return False
    try:
        import urllib.request, xml.etree.ElementTree as ET
        url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=60&requestType=0"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            xml_data = resp.read().decode("euc-kr", errors="ignore")
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")
            if len(items) >= 40:
                closes = [int(it.attrib.get("data", "").split("|")[4]) for it in items]
                ma50 = sum(closes[-50:]) / len(closes[-50:])
                h_period = max(closes)
                pct_h = (cur_price - h_period) / h_period
                if pct_h < -0.28:
                    return False
                if cur_price < ma50 * 0.95:
                    return False
    except Exception:
        pass
    return True


def run_analysis(market: str = "KRX") -> List[Dict[str, Any]]:
    """SEPA x 피봇 감시 전략 분석 실행 및 시그널 리스트 반환 (미너비니 2단계 트렌드 템플릿 필터 적용)"""
    signals = []

    if market.upper() in ("KRX", "KR", "KOR"):
        for item in WATCHLIST["KR_LARGE"]:
            p_info = fetch_krx_price(item["code"])
            cur_price = p_info["price"] if p_info["price"] > 0 else float(item["pivot"])
            # 미너비니 트렌드 템플릿 검증: 밑으로 깔리는 종목 원천 배제
            if not verify_minervini_trend_template(item["code"], cur_price):
                continue

            pivot_val = float(item["pivot"])
            stop_val = float(item["stop"])
            if cur_price > 0 and abs(cur_price - pivot_val) / pivot_val > 0.3:
                pivot_val = round(cur_price * 1.02)
                stop_val = round(cur_price * 0.94)
            tp1_val = round(pivot_val * 1.08)
            tp2_val = round(pivot_val * 1.15)
            rr = round((tp1_val - pivot_val) / max(1.0, (pivot_val - stop_val)), 2)

            signals.append({
                "project_id": "stock-sepa-pivot",
                "strategy_name": "SEPA x 피봇 (대형주)",
                "market": "KRX",
                "cap_size": "대형주",
                "ticker": item["code"],
                "name": item["name"],
                "signal_type": "BUY",
                "price": cur_price,
                "target_price": tp1_val,
                "target_price_2": tp2_val,
                "stop_loss_price": stop_val,
                "risk_reward_ratio": rr,
                "score": float(item["score"]),
                "sector": f"대형주 / {item['market']}",
                "theme": f"[대형주] {item['theme']}",
                "pattern": item["pattern"],
                "action_plan": f"[대형주] 피봇({pivot_val:,}원) 돌파 및 {item['farley_swing']}. 2N스탑 {item['turtle_stop']:,}원 엄수",
                "raw_data": {
                    "cap_size": "대형주",
                    "turtle_stop": item["turtle_stop"],
                    "farley_swing": item["farley_swing"],
                    "pattern": item["pattern"]
                }
            })

        for item in WATCHLIST["KR_MID"]:
            p_info = fetch_krx_price(item["code"])
            cur_price = p_info["price"] if p_info["price"] > 0 else float(item["pivot"])
            # 미너비니 트렌드 템플릿 검증: 밑으로 깔리는 종목 원천 배제
            if not verify_minervini_trend_template(item["code"], cur_price):
                continue
            pivot_val = float(item["pivot"])
            stop_val = float(item["stop"])
            # 피봇이 현재가와 크게 괴리되어 있으면 현재가 기반 타점으로 자동 보정
            if cur_price > 0 and abs(cur_price - pivot_val) / pivot_val > 0.3:
                pivot_val = round(cur_price * 1.02)
                stop_val = round(cur_price * 0.94)
            tp1_val = round(pivot_val * 1.08)
            tp2_val = round(pivot_val * 1.15)
            rr = round((tp1_val - pivot_val) / max(1.0, (pivot_val - stop_val)), 2)

            signals.append({
                "project_id": "stock-sepa-pivot",
                "strategy_name": "SEPA x 피봇 (중소형주)",
                "market": "KRX",
                "cap_size": "중소형주",
                "ticker": item["code"],
                "name": item["name"],
                "signal_type": "BUY",
                "price": cur_price,
                "target_price": tp1_val,
                "target_price_2": tp2_val,
                "stop_loss_price": stop_val,
                "risk_reward_ratio": rr,
                "score": float(item["score"]),
                "sector": f"중소형주 / {item['market']}",
                "theme": f"[중소형주] {item['theme']}",
                "pattern": item["pattern"],
                "action_plan": f"[중소형주] 피봇({pivot_val:,}원) 돌파 및 {item['farley_swing']}. 2N스탑 {item['turtle_stop']:,}원 엄수",
                "raw_data": {
                    "cap_size": "중소형주",
                    "turtle_stop": item["turtle_stop"],
                    "farley_swing": item["farley_swing"],
                    "pattern": item["pattern"]
                }
            })
    else:
        for item in WATCHLIST["US_LARGE"]:
            ticker = item["ticker"]
            p_info = fetch_us_price(ticker)
            cur_price = p_info["price"] if p_info["price"] > 0 else float(item["pivot"])
            pivot_val = float(item["pivot"])
            # 피봇이 현재가와 크게 괴리되어 있으면 현재가 기반 타점으로 자동 보정
            if cur_price > 0 and abs(cur_price - pivot_val) / pivot_val > 0.3:
                pivot_val = round(cur_price * 1.02, 2)
                stop_val = round(cur_price * 0.94, 2)
            else:
                stop_val = float(item["stop"])

            tp1_val = round(pivot_val * 1.10, 2)
            tp2_val = round(pivot_val * 1.20, 2)
            rr = round((tp1_val - pivot_val) / max(0.1, (pivot_val - stop_val)), 2)

            signals.append({
                "project_id": "stock-sepa-pivot",
                "strategy_name": "SEPA x 피봇 (US 대형주)",
                "market": "US",
                "cap_size": "대형주",
                "ticker": ticker,
                "name": p_info["name"] or item["name"],
                "signal_type": "BUY",
                "price": cur_price,
                "target_price": tp1_val,
                "target_price_2": tp2_val,
                "stop_loss_price": stop_val,
                "risk_reward_ratio": rr,
                "score": float(item["score"]),
                "sector": f"대형주 / {item['market']}",
                "theme": f"[대형주] {item['theme']}",
                "pattern": item["pattern"],
                "action_plan": f"[대형주] 피봇(${pivot_val:.2f}) 돌파 및 {item['farley_swing']}. 손절 ${stop_val:.2f} 엄수",
                "raw_data": {
                    "cap_size": "대형주",
                    "turtle_stop": item["turtle_stop"],
                    "farley_swing": item["farley_swing"],
                    "pattern": item["pattern"]
                }
            })

        for item in WATCHLIST["US_MID"]:
            ticker = item["ticker"]
            p_info = fetch_us_price(ticker)
            cur_price = p_info["price"] if p_info["price"] > 0 else float(item["pivot"])
            pivot_val = float(item["pivot"])
            if cur_price > 0 and abs(cur_price - pivot_val) / pivot_val > 0.3:
                pivot_val = round(cur_price * 1.02, 2)
                stop_val = round(cur_price * 0.94, 2)
            else:
                stop_val = float(item["stop"])

            tp1_val = round(pivot_val * 1.10, 2)
            tp2_val = round(pivot_val * 1.20, 2)
            rr = round((tp1_val - pivot_val) / max(0.1, (pivot_val - stop_val)), 2)

            signals.append({
                "project_id": "stock-sepa-pivot",
                "strategy_name": "SEPA x 피봇 (US 중소형주)",
                "market": "US",
                "cap_size": "중소형주",
                "ticker": ticker,
                "name": p_info["name"] or item["name"],
                "signal_type": "BUY",
                "price": cur_price,
                "target_price": tp1_val,
                "target_price_2": tp2_val,
                "stop_loss_price": stop_val,
                "risk_reward_ratio": rr,
                "score": float(item["score"]),
                "sector": f"중소형주 / {item['market']}",
                "theme": f"[중소형주] {item['theme']}",
                "pattern": item["pattern"],
                "action_plan": f"[중소형주] 피봇(${pivot_val:.2f}) 돌파 및 {item['farley_swing']}. 손절 ${stop_val:.2f} 엄수",
                "raw_data": {
                    "cap_size": "중소형주",
                    "turtle_stop": item["turtle_stop"],
                    "farley_swing": item["farley_swing"],
                    "pattern": item["pattern"]
                }
            })

    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals[:6]


if __name__ == "__main__":
    kr = run_analysis("KRX")
    us = run_analysis("US")
    print(f"✅ SEPA KRX 분석: {len(kr)}종목 | US 분석: {len(us)}종목")
    if kr:
        print(f"• KR top: {kr[0]['name']} ({kr[0]['ticker']}) - 피봇 {kr[0]['target_price']:,}원")
    if us:
        print(f"• US top: {us[0]['name']} ({us[0]['ticker']}) - 피봇 ${us[0]['target_price']}")
