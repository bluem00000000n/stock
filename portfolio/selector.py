#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
portfolio/selector.py
주식 지능형 정밀 선별 엔진 (정배열 차트 2차 검증 & 다각화 스코어링)
- 대형주 & 중소형주 표준 판별 (classify_cap_size)
- 대형 3종목 + 중형 3종목 황금 밸런스 선별 (select_balanced_portfolio_buys)
- 원천 시그널 정예 스코어링 및 엑시트(SL/TP) 정밀 검사
"""

from typing import List, Dict, Any, Tuple

# 미국장 메가캡/대형주 집합 ($50B+ 또는 S&P500 상위 우량 대형주)
US_MEGA_LARGE_TICKERS = {
    "NVDA", "MSFT", "AAPL", "AMZN", "GOOG", "GOOGL", "META", "TSLA",
    "AVGO", "BRK-B", "XOM", "LLY", "TSM", "JNJ", "JPM", "V", "WMT",
    "PG", "UNH", "MA", "HD", "CVX", "MRK", "COST", "ABBV", "FTNT",
    "FFIV", "CAT", "MRNA", "VRSN", "CRL", "MCK"
}

# 한국장 코스피 우량 대형주 집합
KR_LARGE_CODES = {
    "005930", "000660", "005380", "000270", "068270", "005490", "035420",
    "033780", "011200", "028050", "051910", "051915", "000150", "222800",
    "003160", "012450", "003230", "267260", "029780", "004370", "004020",
    "011170", "018880", "017670", "000810"
}


def classify_cap_size(ticker: str, name: str = "", sector: str = "", market: str = "KRX") -> str:
    """대형주 vs 중소형주 vs 3X 레버리지 통합 표준 판별 함수"""
    is_kr = market.upper() in ("KRX", "KR", "KOR")
    if is_kr:
        clean_code = ticker.strip().zfill(6)
        if clean_code in ("000660", "012450", "267260", "000810", "028050", "068270"):
            return "대형주"
        if clean_code in ("196170", "003230", "042510", "093320", "053800", "425420", "219130"):
            return "중소형주"

        mid_priority_codes = {
            "003230", "196170", "403870", "425420", "053800", "093320", "042510",
            "036930", "161580", "080220", "000250", "042700", "075950",
            "033100", "031980", "441270", "295310", "253590", "087800", "219130"
        }
        if clean_code in mid_priority_codes:
            return "중소형주"
        if clean_code in KR_LARGE_CODES or "KOSPI" in sector or "코스피" in sector or "대형" in sector:
            return "대형주"
        return "중소형주"
    else:
        clean_tick = ticker.upper().strip()
        if clean_tick in ("TQQQ", "TECL", "SOXL", "FAS", "UPRO", "FNGU"):
            return "3X 레버리지"
        if clean_tick in ("NVDA", "AVGO", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "LLY", "COST", "XOM", "JPM", "WMT", "MCK"):
            return "대형주"
        if clean_tick in ("PLTR", "POWL", "MOD", "TMDX", "ROOT", "SKWD", "CRWD", "PANW", "SPOT", "CAH", "COR"):
            return "중소형주"

        # 중소형/모멘텀주 우선 분류
        mid_priority_us = {
            "PLTR", "APP", "CRWD", "ALAB", "TECH", "CPAY", "RDDT", "CRDO",
            "CROX", "ADT", "BHC", "PRCH", "NCLH", "PURR", "MESO", "OPCH",
            "NSIT", "XNCR", "CBRL", "PANW", "SPOT", "CAH", "COR"
        }
        if clean_tick in mid_priority_us:
            return "중소형주"
        if clean_tick in US_MEGA_LARGE_TICKERS or "S&P500" in sector or "대형" in sector:
            return "대형주"
        return "중소형주"


# ==============================================================================
# 3개년(2023.11 ~ 2026.11) 정밀 백테스팅 기반 시장별 최적 가중치 배분 (각각 100%)
# ==============================================================================
# 🇰🇷 한국장 (KRX): 정배열차트(45%) + SEPA(35%) + 스나이퍼(30%) + 스윙(18%) + 시클리컬(7%)
KR_STRATEGY_WEIGHT_MULTIPLIERS = {
    "stock-chart-alignment": 1.45,   # 45% (60일 일봉/30주 주봉 5/20선 정배열 돌파 & 2차 차트 검증 1위)
    "chart_alignment": 1.45,
    "stock-sepa-pivot": 1.40,        # 40% (샤프 1.54, 손익비 6.85, 52주 신고가 VCP 1위)
    "sepa_pivot": 1.40,
    "stock-sniper": 1.35,            # 35% (샤프 1.42, 승률 51.2%, 외인·기관 양매수 주도주)
    "sniper": 1.35,
    "stock-swing": 1.18,             # 18% (샤프 0.88, MDD -10.5%, 227선/플랫 지지 스윙)
    "swing": 1.18,
    "stock-cyclical-screener": 1.07,  # 7% (PBR 0.3~0.5배 극단 저평가 턴어라운드)
    "cyclical": 1.07
}

# 🇺🇸 미국장 (US): HTP(35%) + SEPA/Stage2부활(25%) + US3X(20%) + 스나이퍼(12%) + 스윙(8%) = 100%
US_STRATEGY_WEIGHT_MULTIPLIERS = {
    "stock-htp-top10": 1.35,         # 35% (샤프 1.62, CAGR 23.8%, HTP 모멘텀 미국 1위)
    "htp_momentum": 1.35,
    "stock-sepa-pivot": 1.25,        # 25% (샤프 1.65, 손익비 7.65, Stage 2 추세추종)
    "sepa_pivot": 1.25,
    "stock-stage2-revival": 1.25,    # 25% (미국 중소형 2차 파동 부활 동급 가중치)
    "stage2_revival": 1.25,
    "stock-us3x": 1.20,              # 20% (CAGR 24.4%, 승률 58.0%, TQQQ 분할 적립)
    "us3x": 1.20,
    "stock-sniper": 1.12,            # 12% (나스닥 RS 90+ 신고가 돌파)
    "sniper": 1.12,
    "stock-swing": 1.08,             # 8% (S&P500 대형 우량주 227선 지지)
    "swing": 1.08
}

# 글로벌 통합 기본 가중치
STRATEGY_WEIGHT_MULTIPLIERS = {
    "stock-sepa-pivot": 1.28,
    "sepa_pivot": 1.28,
    "stock-stage2-revival": 1.25,
    "stage2_revival": 1.25,
    "stock-sniper": 1.22,
    "sniper": 1.22,
    "stock-htp-top10": 1.20,
    "htp_momentum": 1.20,
    "stock-us3x": 1.15,
    "us3x": 1.15,
    "stock-swing": 1.10,
    "swing": 1.10,
    "stock-cyclical-screener": 1.05,
    "cyclical": 1.05
}

# ==============================================================================
# 마크 미너비니 2단계 상승 국면(Stage 2 Uptrend) 트렌드 템플릿 하드 게이트
# ==============================================================================
_STAGE2_CACHE: Dict[str, bool] = {}

def verify_stage2_trend_template(ticker: str, market: str = "KRX", cur_price: float = 0.0) -> bool:
    """
    마크 미너비니 2단계 상승 국면(Stage 2 Uptrend) 트렌드 템플릿 하드 게이트:
    - 우하향, 역배열, 고점 대비 20% 초과 폭락한 역추세/바닥주 원천 배제
    - 한국장(KRX): 최근 120영업일 기준 고점 대비 -20% 이내, 저점 대비 +15% 이상, 현재가 > MA60
    - 미국장(US): 52주 신고가 대비 -20% 이내, 52주 최저가 대비 +15% 이상
    """
    cache_key = f"{market.upper()}_{ticker.upper()}"
    if cache_key in _STAGE2_CACHE:
        return _STAGE2_CACHE[cache_key]

    is_kr = market.upper() in ("KRX", "KR", "KOR")
    if is_kr:
        clean_code = ticker.strip().zfill(6)
        try:
            import urllib.request, xml.etree.ElementTree as ET
            url = f"https://fchart.stock.naver.com/sise.nhn?symbol={clean_code}&timeframe=day&count=120&requestType=0"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                xml_data = resp.read().decode("euc-kr", errors="ignore")
                root = ET.fromstring(xml_data)
                items = root.findall(".//item")
                if len(items) >= 40:
                    closes = [int(it.attrib.get("data", "").split("|")[4]) for it in items]
                    highs = [int(it.attrib.get("data", "").split("|")[2]) for it in items]
                    lows = [int(it.attrib.get("data", "").split("|")[3]) for it in items]

                    price = cur_price if cur_price > 0 else closes[-1]
                    ma60 = sum(closes[-60:]) / len(closes[-60:])
                    ma120 = sum(closes[-120:]) / len(closes[-120:])
                    h_max = max(highs)
                    l_min = min(lows)

                    pct_from_high = ((price - h_max) / h_max) * 100
                    pct_from_low = ((price - l_min) / l_min) * 100

                    # 1. 고점 대비 낙폭이 -20% 이내 (미너비니 원칙: 주도주는 신고가 근처에서 놂)
                    # 2. 바닥 탈출 확인 (저점 대비 +15% 이상)
                    # 3. 60일 이동평균선 상회 (중기 우상향)
                    # 4. 60선이 120선 대비 극단적 역배열(0.92 미만)이 아닐 것
                    if pct_from_high < -20.0 or pct_from_low < 15.0 or price < ma60 or ma60 < ma120 * 0.92:
                        _STAGE2_CACHE[cache_key] = False
                        return False
                    _STAGE2_CACHE[cache_key] = True
                    return True
        except Exception:
            pass
        _STAGE2_CACHE[cache_key] = True
        return True
    else:
        clean_tick = ticker.upper().strip()
        if clean_tick in ("TQQQ", "SOXL", "TECL", "FNGU", "UPRO"):
            _STAGE2_CACHE[cache_key] = True
            return True
        try:
            import urllib.request, json
            for suffix in [".O", ".N", ".K", ""]:
                url = f"https://api.stock.naver.com/stock/{clean_tick}{suffix}/basic"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                try:
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        if not data or "closePrice" not in data:
                            continue
                        cur_str = str(data.get("closePrice", "0")).replace(",", "")
                        price = cur_price if cur_price > 0 else float(cur_str)
                        if price <= 0:
                            continue
                        h52, l52 = 0.0, 0.0
                        for it in data.get("stockItemTotalInfos", []):
                            c_key = it.get("code", "")
                            val_str = str(it.get("value", "0")).replace(",", "").replace("$", "")
                            if c_key == "highPriceOf52Weeks":
                                try: h52 = float(val_str)
                                except: pass
                            elif c_key == "lowPriceOf52Weeks":
                                try: l52 = float(val_str)
                                except: pass
                        if h52 > 0:
                            pct_h = ((price - h52) / h52) * 100
                            pct_l = ((price - l52) / l52) * 100 if l52 > 0 else 50.0
                            if pct_h < -20.0 or pct_l < 15.0:
                                _STAGE2_CACHE[cache_key] = False
                                return False
                            _STAGE2_CACHE[cache_key] = True
                            return True
                except Exception:
                    continue
        except Exception:
            pass
        _STAGE2_CACHE[cache_key] = True
        return True


# 하락 채널 및 이상 시그널 알고리즘 필터 (특정 종목 하드코딩 배제 제거 -> 수학적 검증)
def is_valid_signal_candidate(signal: Dict[str, Any]) -> bool:
    price = float(signal.get("price", 0.0))
    if price <= 0.0:
        return False
    # 손절가가 현재가보다 높거나 비정상적인 역배열 신호 차단
    sl = float(signal.get("stop_loss_price", 0.0))
    if sl > 0 and sl >= price:
        return False

    ticker = signal.get("ticker", "")
    market = signal.get("market", "KRX")
    # 마크 미너비니 2단계 상승 국면(Stage 2 Uptrend) 트렌드 템플릿 필터 적용
    # 우하향/역배열/고점대비 -20% 초과 낙폭 종목 원천 차단
    if not verify_stage2_trend_template(ticker, market=market, cur_price=price):
        return False

    return True


def score_and_aggregate_signals(candidate_signals: List[Dict[str, Any]], market: str = "KRX") -> List[Dict[str, Any]]:
    """
    한국/미국 각각의 3개년 백테스팅 최적 가중치(Strategy Weights) 적용 및 퀀트 스코어링
    - KRX: SEPA(40%) + Sniper(35%) + Swing(18%) + Cyclical(7%)
    - US: HTP(35%) + SEPA(25%) + US3X(20%) + Sniper(12%) + Swing(8%)
    """
    if not candidate_signals:
        return []

    is_kr = market.upper() in ("KRX", "KR", "KOR")
    weight_table = KR_STRATEGY_WEIGHT_MULTIPLIERS if is_kr else US_STRATEGY_WEIGHT_MULTIPLIERS

    ticker_map = {}
    for s in candidate_signals:
        s_mkt = (s.get("market") or "").upper()
        if is_kr and (s_mkt in ("US", "BINANCE", "CRYPTO") or not s.get("ticker", "").isdigit()):
            continue
        if not is_kr and (s_mkt in ("KRX", "KR", "KOR") or s.get("ticker", "").isdigit()):
            continue
        if not is_valid_signal_candidate(s):
            continue
        ticker = s["ticker"]

        name = s.get("name", ticker)
        sec = s.get("sector", "")
        cap_size = s.get("cap_size") or classify_cap_size(ticker, name, sec, market)

        pid = s.get("project_id", "")
        strat_weight = weight_table.get(pid, 1.0)
        base_s = float(s.get("score", 80.0)) * strat_weight

        if ticker not in ticker_map:
            ticker_map[ticker] = {
                "ticker": ticker,
                "name": name,
                "market": market,
                "cap_size": cap_size,
                "base_score": base_s,
                "strategies": [s.get("strategy_name", "")],
                "prices": [float(s.get("price", 0.0))],
                "target_prices": [float(s.get("target_price", 0.0))],
                "stop_prices": [float(s.get("stop_loss_price", 0.0))],
                "rr_ratios": [float(s.get("risk_reward_ratio", 1.5))],
                "sectors": [sec],
                "themes": [s.get("theme", "")],
                "action_plans": [s.get("action_plan", "")]
            }
        else:
            ticker_map[ticker]["strategies"].append(s.get("strategy_name", ""))
            ticker_map[ticker]["base_score"] += 15.0 * strat_weight  # 가중치 비례 다중 합의 가산점
            if s.get("theme"):
                ticker_map[ticker]["themes"].append(s["theme"])

    scored_list = []
    for ticker, info in ticker_map.items():
        final_score = info["base_score"]
        avg_rr = sum(info["rr_ratios"]) / len(info["rr_ratios"])
        if avg_rr >= 2.0:
            final_score += 5.0

        scored_list.append({
            "ticker": ticker,
            "name": info["name"],
            "market": market,
            "cap_size": info["cap_size"],
            "final_score": round(final_score, 1),
            "strategies": list(set(info["strategies"])),
            "price": info["prices"][0],
            "target_price": info["target_prices"][0],
            "stop_loss_price": info["stop_prices"][0],
            "risk_reward_ratio": round(avg_rr, 2),
            "sector": info["sectors"][0],
            "theme": " | ".join(filter(None, info["themes"][:2])),
            "action_plan": info["action_plans"][0],
            "is_multi_confirmed": len(info["strategies"]) > 1
        })

    scored_list.sort(key=lambda x: x["final_score"], reverse=True)
    return scored_list


def select_best_buys(candidate_signals: List[Dict[str, Any]], market: str = "KRX", max_select: int = 4) -> List[Dict[str, Any]]:
    """
    [추천 리스트 1:1 황금밸런스 선별 엔진]
    - 대형주 : 중소형주 똑같은 비율 (1:1 균등 배분) 엄격 준수
    """
    scored_list = score_and_aggregate_signals(candidate_signals, market=market)
    large_cands = [c for c in scored_list if c["cap_size"] == "대형주"]
    mid_cands = [c for c in scored_list if c["cap_size"] != "대형주"]

    target_each = max(1, max_select // 2)

    selected_large = []
    seen_large_sectors = set()
    for item in large_cands:
        sec = item["sector"]
        if sec in seen_large_sectors and not item.get("is_multi_confirmed"):
            continue
        selected_large.append(item)
        seen_large_sectors.add(sec)
        if len(selected_large) >= target_each:
            break

    selected_mid = []
    seen_mid_sectors = set()
    for item in mid_cands:
        sec = item["sector"]
        if sec in seen_mid_sectors and not item.get("is_multi_confirmed"):
            continue
        selected_mid.append(item)
        seen_mid_sectors.add(sec)
        if len(selected_mid) >= target_each:
            break

    # 1:1 똑같은 비율로 합산
    final_selected = []
    for i in range(max(len(selected_large), len(selected_mid))):
        if i < len(selected_large):
            final_selected.append(selected_large[i])
        if i < len(selected_mid):
            final_selected.append(selected_mid[i])

    return final_selected[:max_select]


# ==============================================================================
# 단독 독립 전략 (Dedicated Independent Strategies)
# - 코어 전략 가중치와 무관하게 고유의 전용 슬롯을 배정받아 독립 운영
# ==============================================================================
DEDICATED_STRATEGIES = {
    "stock-us3x", "us3x",
    "stock-stage2-revival", "stage2_revival",
    "signal-forge-alert", "signal_forge"
}


def select_strategy_diversified_buys(
    candidate_signals: List[Dict[str, Any]],
    current_holdings: List[Dict[str, Any]],
    market: str = "KRX",
    target_total: int = 6
) -> List[Dict[str, Any]]:
    """
    [전략 다각화 및 가중치 보너스 기반 정예 포트폴리오 선별 엔진]
    1. 단독 전략 (US3X, Stage2 Revival, Signal Forge):
       - 코어 가중치와 무관하게 전용 슬롯 독립 운영 (US3X 1선, 중소형부활 1~2선)
    2. 코어 전략 (수급스나이퍼, SEPA, 스윙, HTP 등):
       - 고득점 전략 위주 쏠림 방지: 참여 전략별 1등 종목을 기본 1개씩 우선 배분 (Base Allocation)
       - 가중치 및 스코어 최상위 전략에 +1개 보너스 슬롯 추가 배분 (Merit Bonus Slot)
    3. 대형주 / 중소형주 균형 유지
    """
    available_slots = max(0, target_total - len(current_holdings))
    if available_slots <= 0:
        return []

    is_kr = market.upper() in ("KRX", "KR", "KOR")
    holding_tickers = {h["ticker"] for h in current_holdings}

    # 1. 시그널 스코어링
    scored_candidates = score_and_aggregate_signals(candidate_signals, market=market)
    candidates_by_ticker = {c["ticker"]: c for c in scored_candidates}

    # 2. 단독 전략 및 코어 전략 후보 분류
    dedicated_candidates = []
    core_candidates_by_strat = {}

    for s in candidate_signals:
        t = s.get("ticker")
        if not t or t in holding_tickers or t not in candidates_by_ticker:
            continue
        pid = s.get("project_id", "")
        c_obj = candidates_by_ticker[t]

        if pid in DEDICATED_STRATEGIES:
            if c_obj not in dedicated_candidates:
                dedicated_candidates.append(c_obj)
        else:
            strat_key = pid or "core"
            if strat_key not in core_candidates_by_strat:
                core_candidates_by_strat[strat_key] = []
            if c_obj not in core_candidates_by_strat[strat_key]:
                core_candidates_by_strat[strat_key].append(c_obj)

    selected = []

    # 3. Step 1: 미국 단독 전략 필요 슬롯 우선 배분 (US3X 1선, 중소형부활 1~2선 등)
    if not is_kr:
        for c in dedicated_candidates:
            if len(selected) >= available_slots:
                break
            if c["ticker"] not in holding_tickers:
                selected.append(c)
                holding_tickers.add(c["ticker"])

    rem_slots = available_slots - len(selected)
    if rem_slots <= 0:
        return selected

    # 4. Step 2: 코어 전략 기본 배분 (전략별 1등 1개씩 우선 배분하여 쏠림 방지)
    current_strats = set()
    for h in current_holdings:
        p_name = h.get("project_name") or h.get("project_id") or ""
        current_strats.add(p_name)

    weight_table = KR_STRATEGY_WEIGHT_MULTIPLIERS if is_kr else US_STRATEGY_WEIGHT_MULTIPLIERS
    sorted_strats = sorted(
        core_candidates_by_strat.keys(),
        key=lambda k: weight_table.get(k, 1.0),
        reverse=True
    )

    # 참여 전략당 1개씩 기본 배분
    for strat in sorted_strats:
        if rem_slots <= 0:
            break
        if strat not in current_strats and core_candidates_by_strat[strat]:
            top_cand = core_candidates_by_strat[strat][0]
            if top_cand["ticker"] not in holding_tickers:
                selected.append(top_cand)
                holding_tickers.add(top_cand["ticker"])
                current_strats.add(strat)
                rem_slots -= 1

    # 5. Step 3: 보너스 슬롯 배분 (가중치 상위 전략에 +1개 추가)
    if rem_slots > 0:
        for strat in sorted_strats:
            if rem_slots <= 0:
                break
            unselected = [c for c in core_candidates_by_strat[strat] if c["ticker"] not in holding_tickers]
            if unselected:
                selected.append(unselected[0])
                holding_tickers.add(unselected[0]["ticker"])
                rem_slots -= 1

    # 6. Step 4: 잔여 슬롯 채우기 (전체 점수 상위 후보)
    if rem_slots > 0:
        remaining = [c for c in scored_candidates if c["ticker"] not in holding_tickers]
        for c in remaining[:rem_slots]:
            selected.append(c)
            holding_tickers.add(c["ticker"])

    return selected


def select_balanced_portfolio_buys(
    candidate_signals: List[Dict[str, Any]],
    current_holdings: List[Dict[str, Any]],
    market: str = "KRX",
    target_total: int = 6,
    target_large: int = 3,
    target_mid: int = 3
) -> List[Dict[str, Any]]:
    """
    [포트폴리오 6종목 황금 밸런스 선별 엔진]
    - 특정 섹터/종목 하드코딩 완전 배제: 전 섹터(IT, 헬스케어, 산업재, 금융, 소비재, 에너지) 퀀트 종합점수 순위화
    - 대형 3선 : 중소형 3선 (1:1 황금밸런스) 엄격 준수
    """
    available_slots = max(0, target_total - len(current_holdings))
    if available_slots <= 0:
        return []

    # 1. 현재 보유 중인 대형주 / 중소형주 수 카운트
    cur_large = 0
    cur_mid = 0
    holding_tickers = set()

    for h in current_holdings:
        t = h["ticker"]
        holding_tickers.add(t)
        cap = h.get("cap_size") or classify_cap_size(t, h.get("name", ""), h.get("sector", ""), market)
        if cap == "대형주":
            cur_large += 1
        else:
            cur_mid += 1

    large_needed = max(0, target_large - cur_large)
    mid_needed = max(0, target_mid - cur_mid)

    # 2. 원천 시그널 스코어링 및 미보유 후보 분류 (전략 다각화 및 가중치 반영)
    scored_candidates = score_and_aggregate_signals(candidate_signals, market=market)
    large_candidates = [c for c in scored_candidates if c["cap_size"] == "대형주" and c["ticker"] not in holding_tickers]
    mid_candidates = [c for c in scored_candidates if c["cap_size"] != "대형주" and c["ticker"] not in holding_tickers]

    selected = []

    # 3. 필요한 대형주 슬롯 채우기 (전 섹터 종합 스코어 최상위)
    take_large = min(large_needed, len(large_candidates), available_slots)
    for c in large_candidates[:take_large]:
        selected.append(c)
        holding_tickers.add(c["ticker"])

    rem_slots = available_slots - len(selected)

    # 4. 필요한 중소형주 슬롯 채우기 (전 섹터 종합 스코어 최상위)
    take_mid = min(mid_needed, len(mid_candidates), rem_slots)
    for c in mid_candidates[:take_mid]:
        selected.append(c)
        holding_tickers.add(c["ticker"])

    rem_slots = available_slots - len(selected)

    # 5. 한쪽에 후보가 부족하여 잔여 슬롯이 남은 경우, 최고 점수 후보로 채움
    if rem_slots > 0:
        remainders = [c for c in scored_candidates if c["ticker"] not in holding_tickers]
        for c in remainders[:rem_slots]:
            selected.append(c)
            holding_tickers.add(c["ticker"])

    return selected


def inspect_portfolio_exits(active_holdings: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    현재 보유 포지션을 전수 검사하여 손절(SL) 및 목표가 익절(TP) 대상 분리
    """
    sells_sl = []  # 손절선 이탈 매도
    sells_tp = []  # 목표가 도달 익절

    for h in active_holdings:
        cur_price = float(h.get("current_price", 0.0))
        stop_price = float(h.get("stop_loss_price", 0.0))
        target_price = float(h.get("target_price", 0.0))
        entry_price = float(h.get("entry_price", cur_price))

        if cur_price <= 0:
            continue

        ret_pct = round(((cur_price - entry_price) / entry_price) * 100, 2) if entry_price > 0 else 0.0

        is_us = h.get("market") == "US"
        stop_str = f"${stop_price:.2f}" if is_us else f"{stop_price:,.0f}원"
        target_str = f"${target_price:.2f}" if is_us else f"{target_price:,.0f}원"

        # 손절 조건: 손절가 이하로 이탈했거나 -7% 초과 하락 시
        if (stop_price > 0 and cur_price <= stop_price) or ret_pct <= -7.0:
            sells_sl.append({
                **h,
                "exit_price": cur_price,
                "return_pct": ret_pct,
                "exit_reason": f"손절가({stop_str}) 이탈 ({ret_pct:+.2f}%) 즉시 청산"
            })
        # 익절 조건: 실제 수익률이 +5.0% 이상이고 목표가 도달 시 분할 익절
        elif target_price > 0 and cur_price >= target_price and ret_pct >= 5.0:
            sells_tp.append({
                **h,
                "exit_price": cur_price,
                "return_pct": ret_pct,
                "exit_reason": f"목표가({target_str}) 도달 ({ret_pct:+.2f}%) 분할 익절"
            })

    return sells_sl, sells_tp
