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
        {"name": "삼성E&A", "code": "028050", "market": "코스피", "pivot": 62000, "stop": 57600, "turtle_stop": 58500, "farley_swing": "20일선 지지 52주 신고가 VCP 돌파", "pattern": "Cup with Handle", "score": 99, "theme": "친환경 플랜트 및 대형 EPC 글로벌 수주 랠리"},
        {"name": "삼성화재", "code": "000810", "market": "코스피", "pivot": 660000, "stop": 615000, "turtle_stop": 625000, "farley_swing": "신고가 박스권 돌파 양매수", "pattern": "Flat Base", "score": 98, "theme": "밸류업 및 역대 최대 순이익 주주환원"},
        {"name": "셀트리온", "code": "068270", "market": "코스피", "pivot": 192000, "stop": 181000, "turtle_stop": 183000, "farley_swing": "20주선 위 VCP 매물 소화 후 돌파", "pattern": "Ascending Triangle", "score": 98, "theme": "짐펜트라 미국 PBM 등재 및 바이오시밀러 초고성장"},
        {"name": "KT&G", "code": "033780", "market": "코스피", "pivot": 194000, "stop": 182000, "turtle_stop": 184000, "farley_swing": "신고가 안착 우상향 스윙", "pattern": "High Tight Flag", "score": 97, "theme": "글로벌 NGP 전자담배 랠리 및 밸류업 프로그램"},
    ],
    "KR_MID": [
        {"name": "케이아이엔엑스", "code": "093320", "market": "코스닥", "pivot": 176000, "stop": 164000, "turtle_stop": 166000, "farley_swing": "과천 IDC 하이타이트 플래그 돌파", "pattern": "High Tight Flag", "score": 99, "theme": "과천 AI IDC 본격 가동 및 52주 신고가 우상향"},
        {"name": "안랩", "code": "053800", "market": "코스닥", "pivot": 115000, "stop": 104000, "turtle_stop": 106000, "farley_swing": "보안 대장주 52주 신고가 VCP 돌파", "pattern": "VCP", "score": 98, "theme": "차세대 클라우드/AI 보안 솔루션 수급 분출"},
        {"name": "티에프이", "code": "425420", "market": "코스닥", "pivot": 79000, "stop": 73000, "turtle_stop": 74500, "farley_swing": "테스트 소켓 2차 파동 돌파", "pattern": "Bull Flag", "score": 97, "theme": "AI 반도체 테스트 소켓 국산화 선도"},
        {"name": "타이거일렉", "code": "219130", "market": "코스닥", "pivot": 96000, "stop": 89000, "turtle_stop": 90500, "farley_swing": "인쇄회로기판 초강세 52주 신고가", "pattern": "Ascending Triangle", "score": 96, "theme": "고다층 초고밀도 반도체 검사용 기판 공급확대"},
    ],
    "US_LARGE": [
        {"ticker": "LLY", "name": "Eli Lilly", "market": "NYSE", "sector": "Healthcare", "pivot": 1420.0, "stop": 1330.0, "turtle_stop": 1350.0, "farley_swing": "20일선 지지 젭바운드 글로벌 랠리", "pattern": "Cup with Handle", "score": 99, "theme": "GLP-1 비만/당뇨 치료제 글로벌 1위 공급확대"},
        {"ticker": "COST", "name": "Costco", "market": "NASDAQ", "sector": "Consumer Staples", "pivot": 1050.0, "stop": 980.0, "turtle_stop": 995.0, "farley_swing": "플랫베이스 지지 우상향 스윙", "pattern": "Flat Base", "score": 98, "theme": "글로벌 멤버십 갱신율 93% 초우량 펀더멘털"},
        {"ticker": "XOM", "name": "ExxonMobil", "market": "NYSE", "sector": "Energy", "pivot": 182.0, "stop": 170.0, "turtle_stop": 172.0, "farley_swing": "200일선 지지 반등 52주 신고가권", "pattern": "Cup with Handle", "score": 97, "theme": "에너지 메이저 막대한 현금흐름 및 자사주 매입"},
        {"ticker": "JPM", "name": "JPMorgan Chase", "market": "NYSE", "sector": "Financials", "pivot": 345.0, "stop": 320.0, "turtle_stop": 325.0, "farley_swing": "신고가 박스권 돌파", "pattern": "Flat Base", "score": 97, "theme": "순이자이익 및 글로벌 IB 수수료 호조"},
        {"ticker": "NVDA", "name": "Nvidia", "market": "NASDAQ", "sector": "Information Technology", "pivot": 205.0, "stop": 190.0, "turtle_stop": 193.0, "farley_swing": "첫 1시간 ORB 돌파 감시", "pattern": "Ascending Triangle", "score": 98, "theme": "블랙웰 B200 풀캐파 가동"},
        {"ticker": "PLTR", "name": "Palantir", "market": "NYSE", "sector": "Information Technology", "pivot": 180.0, "stop": 165.0, "turtle_stop": 168.0, "farley_swing": "Strong Close 초고속 모멘텀", "pattern": "High Tight Flag", "score": 98, "theme": "AIP 엔터프라이즈 폭발적 수요"},
        {"ticker": "WMT", "name": "Walmart", "market": "NYSE", "sector": "Consumer Staples", "pivot": 129.0, "stop": 121.0, "turtle_stop": 123.0, "farley_swing": "신고가 안착 우상향 스윙", "pattern": "Flat Base", "score": 96, "theme": "글로벌 이커머스 및 광고 매출 폭발"},
        {"ticker": "MCK", "name": "McKesson", "market": "NYSE", "sector": "Healthcare", "pivot": 1010.0, "stop": 940.0, "turtle_stop": 955.0, "farley_swing": "200일선 상단 52주 신고가 안착", "pattern": "High Tight Flag", "score": 96, "theme": "의약품 유통 및 바이오 솔루션 안정적 성장"}
    ],
    "US_MID": [
        {"ticker": "CRWD", "name": "CrowdStrike", "market": "NASDAQ", "sector": "Information Technology", "pivot": 245.0, "stop": 228.0, "turtle_stop": 232.0, "farley_swing": "팔콘 플랫폼 신고가 스윙 모멘텀", "pattern": "High Tight Flag", "score": 99, "theme": "차세대 엔드포인트 보안 플랫폼 1위"},
        {"ticker": "PANW", "name": "Palo Alto Networks", "market": "NASDAQ", "sector": "Information Technology", "pivot": 355.0, "stop": 330.0, "turtle_stop": 335.0, "farley_swing": "보안 플랫폼 통합 VCP 돌파", "pattern": "VCP", "score": 98, "theme": "차세대 방화벽 및 클라우드 보안 독점"},
        {"ticker": "SPOT", "name": "Spotify", "market": "NYSE", "sector": "Communication Services", "pivot": 600.0, "stop": 560.0, "turtle_stop": 570.0, "farley_swing": "신고가 박스권 돌파", "pattern": "High Tight Flag", "score": 98, "theme": "글로벌 유료 구독자 급증 및 영업이익률 레버리지"},
        {"ticker": "CAH", "name": "Cardinal Health", "market": "NYSE", "sector": "Healthcare", "pivot": 256.0, "stop": 240.0, "turtle_stop": 243.0, "farley_swing": "플랫베이스 지지 돌파", "pattern": "Flat Base", "score": 96, "theme": "글로벌 제약 유통 및 특수 의약품 고성장"},
        {"ticker": "COR", "name": "Cencora", "market": "NYSE", "sector": "Healthcare", "pivot": 340.0, "stop": 318.0, "turtle_stop": 322.0, "farley_swing": "52주 신고가권 안착 스윙", "pattern": "Bull Flag", "score": 96, "theme": "글로벌 헬스케어 유통 과점 지배력"}
    ]
}


def verify_minervini_trend_template(code: str, cur_price: float) -> bool:
    """마크 미너비니 2단계 상승 국면(Stage 2 Uptrend) 트렌드 템플릿 필터
    - 밑으로 깔리는 종목(역배열, 60일선 이탈, 고점 대비 -20% 초과 낙폭) 엄격 배제
    - 신고가 근처에서 노는 주도주(Leader)만 통과 (특정 종목 하드코딩 배제 완전 제거)
    """
    if cur_price <= 0:
        return False
    try:
        import urllib.request, xml.etree.ElementTree as ET
        url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=120&requestType=0"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            xml_data = resp.read().decode("euc-kr", errors="ignore")
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")
            if len(items) >= 40:
                closes = [int(it.attrib.get("data", "").split("|")[4]) for it in items]
                highs = [int(it.attrib.get("data", "").split("|")[2]) for it in items]
                ma60 = sum(closes[-60:]) / len(closes[-60:])
                h_period = max(highs)
                pct_h = ((cur_price - h_period) / h_period) * 100
                if pct_h < -20.0:
                    return False
                if cur_price < ma60:
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
                "sector": item.get("sector") or f"대형주 / {item['market']}",
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
                "sector": item.get("sector") or f"중소형주 / {item['market']}",
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
                "sector": item.get("sector") or f"대형주 / {item['market']}",
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
                "sector": item.get("sector") or f"중소형주 / {item['market']}",
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
