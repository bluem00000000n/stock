#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/sepa_pivot.py
마크 미너비니 SEPA x 댄 쟁거 피봇 감시 전략 (한국 KRX & 미국 US)
순수 분석 모듈: 텔레그램 발송 코드 없음, List[Dict] 시그널 반환
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

# 상위 core 모듈 참조
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.market_data import fetch_krx_price, fetch_us_price

WATCHLIST = {
    "KR_LARGE": [
        {"name": "SK하이닉스", "code": "000660", "market": "코스피", "pivot": 205000, "stop": 192500, "turtle_stop": 194000, "farley_swing": "첫 1시간 ORB 돌파 감시", "pattern": "Ascending Triangle", "score": 98, "theme": "HBM3E/HBM4 독점 공급"},
        {"name": "알테오젠", "code": "196170", "market": "코스닥", "pivot": 420000, "stop": 390000, "turtle_stop": 396000, "farley_swing": "Strong Close 안착 스윙", "pattern": "High Tight Flag", "score": 99, "theme": "ALT-B4 글로벌 빅파마 독점"},
        {"name": "삼양식품", "code": "003230", "market": "코스피", "pivot": 630000, "stop": 592000, "turtle_stop": 602000, "farley_swing": "피보나치 38.2% 20일선 지지", "pattern": "Cup with Handle", "score": 97, "theme": "불닭 글로벌 수출 및 밀양2공장"},
        {"name": "한화에어로스페이스", "code": "012450", "market": "코스피", "pivot": 380000, "stop": 357000, "turtle_stop": 362000, "farley_swing": "첫 1시간 ORB 상회 안착", "pattern": "Bull Flag", "score": 98, "theme": "지상방산 해외 수주 및 인적분할"},
        {"name": "HD현대일렉트릭", "code": "267260", "market": "코스피", "pivot": 360000, "stop": 338000, "turtle_stop": 342000, "farley_swing": "50일선 지지 반등 스윙", "pattern": "Flat Base", "score": 98, "theme": "북미 초고압 변압기 쇼티지"},
    ],
    "KR_MID": [
        {"name": "산일전기", "code": "075950", "market": "코스피", "pivot": 68000, "stop": 63200, "turtle_stop": 64200, "farley_swing": "Strong Close 안착 스윙", "pattern": "Bull Flag", "score": 98, "theme": "북미 특수변압기 직납 고성장"},
        {"name": "제룡전기", "code": "033100", "market": "코스닥", "pivot": 82000, "stop": 77000, "turtle_stop": 77600, "farley_swing": "첫 1시간 ORB 분출", "pattern": "Flat Base", "score": 97, "theme": "주상변압기 마진 40%+ 지속"},
        {"name": "피에스케이홀딩스", "code": "031980", "market": "코스닥", "pivot": 62000, "stop": 58200, "turtle_stop": 58600, "farley_swing": "VCP 3차 수축 돌파", "pattern": "VCP", "score": 96, "theme": "HBM 패키징 디스컴 장비"},
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


def run_analysis(market: str = "KRX") -> List[Dict[str, Any]]:
    """SEPA x 피봇 감시 전략 분석 실행 및 시그널 리스트 반환"""
    signals = []

    if market.upper() in ("KRX", "KR", "KOR"):
        for item in WATCHLIST["KR_LARGE"]:
            item_copy = dict(item)
            item_copy["cap_size"] = "대형주"
            p_info = fetch_krx_price(item["code"])
            cur_price = p_info["price"] if p_info["price"] > 0 else float(item["pivot"])
            pivot_val = float(item["pivot"])
            stop_val = float(item["stop"])
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
            pivot_val = float(item["pivot"])
            stop_val = float(item["stop"])
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
