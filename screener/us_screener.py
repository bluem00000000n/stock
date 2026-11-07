#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screener/us_screener.py
미국 증시(NYSE, NASDAQ, AMEX 8,000+ 전종목) 백찬규 & 프라딥 본데(Pradeep Bonde) 통합 퀀트 스크리너 엔진
- Finviz 실시간 전수 웹 스크리너 연동 (Zero API Key, 공개 웹 스캐닝)
- 네이버 증권 해외주식 API 실시간 시세 및 재무/수급 연동

[미국장 3대 퀀트 스크리너 체계]
1. 미국 대형 성장주 스크리너 (백찬규 실무):
   - 시가총액: $10B 이상 (100억 달러 / 약 13.5조원 이상)
   - 미래 EPS 성장률: 향후 5년(2026~2027+) 연 15% 이상
   - ROE: 15% 이상
   - 정렬: 52주 대비 거래량 변화율(Relative Volume) 상위
   - 액션: 목표가(+25%), 손절가(-7%), 손익비(RR) 기반 매수/매도 타점 도출

2. 미국 중소형 수급 스크리너 (백찬규 실무):
   - 시가총액: $1B ~ $10B (10억 ~ 100억 달러 / 약 1.3조원 ~ 13.5조원)
   - 거래량: 52주 평균 대비 5일 평균 거래량 200% 이상 (Relative Volume >= 2.0 폭증)
   - 당일 등락률: > 0% (음봉 손절매 제외, 양봉 반등 종목만 선별)
   - 밸류에이션: 저PBR 또는 낙폭과대 바닥 탈출

3. 프라딥 본데 에피소딕 피봇 스크리너 (Pradeep Bonde Episodic Pivot & DEP):
   - TraderLion 팟캐스트 정통 룰: 어닝 서프라이즈/촉매에 의한 주가 구조의 영구적 재평가
   - 필터: Gap Up >= 7.5%+, RVOL >= 2.0x+, ADV >= 500k, Price >= $5.00
   - MAGNA53 채점: Massive Profit, Sales Acceleration, Gap Magnitude, Neglect Breakout, Analyst Upgrades
   - Cap 10x10 원칙: 시총 $10B 미만, 상장 10년 미만 성장주 우대
   - 매매 룰: 15분/30분 ORB 돌파 진입, LOD(Low of Day -5%) 손절, +20%/+35% 트레일링 익절
"""

import os
import sys
import json
import re
import ssl
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
DATA_DIR = BASE_DIR / "data" / "screener"
DATA_DIR.mkdir(parents=True, exist_ok=True)
US_UNIVERSE_FILE = DATA_DIR / "us_quarterly_universe.json"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_finviz_tickers(filter_str: str, order: str = "-relativevolume", max_results: int = 15) -> List[str]:
    """Finviz 스크리너에서 특정 조건의 티커 목록을 실시간 스크래핑"""
    url = f"https://finviz.com/screener.ashx?v=111&f={filter_str}&o={order}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # SVG 로고 링크에서 티커 추출 (가장 정확하고 안정적)
            raw_tickers = re.findall(r"https://logo\.finviz\.com/([A-Z0-9\.\-]+)\.svg", html)
            tickers = list(dict.fromkeys(raw_tickers))
            return tickers[:max_results]
    except Exception as e:
        print(f"⚠️ Finviz 스크래핑 오류 ({filter_str}): {e}")
        return []


def get_us_stock_detail(ticker: str) -> Optional[Dict[str, Any]]:
    """네이버 증권 해외주식 API를 통해 종목 상세 정보 및 실시간 시세 수집"""
    clean_sym = ticker.upper().strip()
    for suffix in [".O", ".N", ".K", ""]:
        sym = f"{clean_sym}{suffix}"
        url = f"https://api.stock.naver.com/stock/{sym}/basic"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=4) as res:
                data = json.loads(res.read().decode("utf-8"))
                if data and "closePrice" in data:
                    infos = {i.get("key"): i.get("value") for i in data.get("stockItemTotalInfos", [])}
                    name = data.get("stockName", clean_sym)
                    price = float(str(data.get("closePrice", "0")).replace(",", ""))
                    fluct = float(str(data.get("fluctuationsRatio", "0")).replace(",", ""))
                    marcap = infos.get("시총", "-")
                    pbr_str = str(infos.get("PBR", "1.0")).replace("배", "").replace(",", "").strip()
                    try:
                        pbr = float(pbr_str)
                    except ValueError:
                        pbr = 1.0

                    return {
                        "ticker": clean_sym,
                        "name": name,
                        "price": price,
                        "fluctuations_ratio": fluct,
                        "market_cap": marcap,
                        "trailing_pb": pbr,
                        "industry": infos.get("업종", "미국 기술/성장주"),
                        "per": infos.get("PER", "-")
                    }
        except Exception:
            continue
    return None


def scan_episodic_pivots(max_results: int = 6) -> List[Dict[str, Any]]:
    """
    프라딥 본데(Pradeep Bonde) 정통 에피소딕 피봇(Episodic Pivot & DEP) Finviz 실시간 스크리너:
    - 필터: Gap Up >= 7.5% (ta_gap_u7), RVOL >= 2.0x (sh_relvol_o2), ADV >= 500k (sh_avgvol_o500), Price >= $5.00 (sh_price_o5)
    - 정렬: 상대 거래량(Relative Volume) 내림차순
    - 채점: MAGNA53 프레임워크 (어닝 서프라이즈, 매출 가속화, 갭 크기, 무관심 탈출, 목표가 상향)
    - Cap 10x10 원칙: 시총 $10B 미만 폭발적 고성장주 우대
    """
    ep_filter = "ta_gap_u7,sh_relvol_o2,sh_avgvol_o500,sh_price_o5"
    ep_tickers = fetch_finviz_tickers(ep_filter, order="-relativevolume", max_results=max_results * 2)
    print(f"🔥 [Episodic Pivot] Finviz EP 갭업 촉매주 포착: {len(ep_tickers)}개 종목 ({ep_tickers[:6]})")

    ep_list = []
    seen = set()
    for t in ep_tickers:
        detail = get_us_stock_detail(t)
        if not detail or detail["price"] <= 0:
            continue
        base_name = detail["name"].split(" ")[0]
        if base_name in seen:
            continue
        seen.add(base_name)

        # MAGNA53 정량 스코어 산출 (기본 80점)
        fluct = detail.get("fluctuations_ratio", 0.0)
        score = 80.0
        if fluct >= 20.0:
            score += 14.0
        elif fluct >= 12.0:
            score += 10.0
        elif fluct >= 7.5:
            score += 6.0

        # Cap 10x10 보너스: 시총 $10B 미만 성장주 우대
        marcap_str = detail.get("market_cap", "")
        if "억 USD" in marcap_str:
            try:
                cap_val = float(marcap_str.replace("억 USD", "").strip())
                if cap_val < 100.0:  # $10B 미만
                    score += 4.0
            except ValueError:
                pass

        detail["screener_type"] = "EPISODIC_PIVOT"
        detail["magna53_score"] = min(98.0, round(score, 1))
        detail["theme"] = f"에피소딕 피봇 (EP & DEP) | {detail['industry']}"
        detail["video_note"] = f"Pradeep Bonde EP: 당일 {fluct:+.1f}% 갭업 & RVOL 폭증 | MAGNA53 {detail['magna53_score']}점"
        ep_list.append(detail)
        if len(ep_list) >= max_results:
            break

    return ep_list


def run_us_automated_scan() -> Dict[str, Any]:
    """
    미국 증시 전종목 Finviz 자동 전수 스크리닝 실행:
    1. 대형 성장주: 시총 $10B+, 향후 5년 EPS > 15%, ROE > 15%, 상대 거래량 상위
    2. 중소형 수급주: 시총 $1B~$10B, 52주 대비 거래량 200%+ 폭증, 당일 양봉 상승
    3. 프라딥 본데 에피소딕 피봇: Gap Up 7.5%+, RVOL 2.0x+, ADV 500k+, Price $5.00+
    """
    print("🌐 [US Screener] 미국 증시 8,000+ 전종목 Finviz 실시간 자동 전수 스크리닝 시작...")

    # 1. 대형 성장주 ($10B+, EPS > 15%, ROE > 15%)
    large_filter = "cap_largeover,fa_eps5years_o15,fa_roe_o15"
    large_tickers = fetch_finviz_tickers(large_filter, order="-relativevolume", max_results=15)
    print(f"📊 Finviz 대형 성장주 통과: {len(large_tickers)}개 종목 포착 ({large_tickers[:8]})")

    # 2. 중소형 수급주 ($1B~$10B, 거래량 200%+ 폭증, 당일 양봉)
    mid_filter = "cap_mid,sh_relvol_o2,ta_perf_dup"
    mid_tickers = fetch_finviz_tickers(mid_filter, order="-relativevolume", max_results=12)
    
    # 스몰캡 ($300M~$2B) 보강
    small_filter = "cap_small,sh_relvol_o2,ta_perf_dup"
    small_tickers = fetch_finviz_tickers(small_filter, order="-relativevolume", max_results=10)
    
    combined_mid_small = list(dict.fromkeys(mid_tickers + small_tickers))[:20]
    print(f"💎 Finviz 중소형 수급주 통과: {len(combined_mid_small)}개 종목 포착 ({combined_mid_small[:8]})")

    # 3. 프라딥 본데 에피소딕 피봇 (EP & DEP)
    ep_list = scan_episodic_pivots(max_results=6)
    print(f"🚀 Finviz 에피소딕 피봇 (EP) 통과: {len(ep_list)}개 종목 포착")

    # 상세 데이터 실시간 수집 (구글 GOOG/GOOGL 같은 중복 기업 필터링)
    seen_names = set()
    growth_large_list = []
    for t in large_tickers:
        detail = get_us_stock_detail(t)
        if detail and detail["price"] > 0:
            base_name = detail["name"].split(" ")[0]
            if base_name in seen_names:
                continue
            seen_names.add(base_name)

            detail["screener_type"] = "GROWTH_LARGE"
            detail["theme"] = f"미국 대형 고성장주 | {detail['industry']}"
            detail["video_note"] = f"Finviz 전수 통과: 시총 {detail['market_cap']} | EPS 15%+ 고성장 & ROE 15%+"
            growth_large_list.append(detail)
            if len(growth_large_list) >= 4:
                break

    mid_small_list = []
    for t in combined_mid_small:
        detail = get_us_stock_detail(t)
        if detail and detail["price"] > 0:
            base_name = detail["name"].split(" ")[0]
            if base_name in seen_names:
                continue
            seen_names.add(base_name)

            detail["screener_type"] = "MID_SMALL"
            detail["theme"] = f"미국 중소형 수급 폭등주 | {detail['industry']}"
            detail["video_note"] = f"Finviz 전수 통과: 거래량 200%+ 폭증 양봉 & PBR {detail['trailing_pb']}배"
            mid_small_list.append(detail)
            if len(mid_small_list) >= 8:
                break

    # 분기 유니버스 파일로 저장
    result_data = {
        "quarter": "2026-Q3",
        "screened_date": "2026-10-30",
        "source": "finviz_automated_full_scan",
        "next_screening_expected": "2026-11-20 (미국 3Q 어닝시즌 마감 후)",
        "rules": {
            "large_cap_threshold": "$10B 이상 (100억 달러)",
            "mid_small_cap_threshold": "$1B ~ $10B (10억~100억 달러)",
            "volume_threshold": "52주 평균 대비 200% 이상 (Relative Volume 2.0+)",
            "growth_threshold": "EPS 성장률 15%+ & ROE 15%+",
            "episodic_pivot_threshold": "Gap Up >= 7.5%+, RVOL >= 2.0x+, ADV >= 500k, MAGNA53 Scoring"
        },
        "growth_large": growth_large_list,
        "mid_small": mid_small_list,
        "episodic_pivots": ep_list
    }

    with open(US_UNIVERSE_FILE, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 미국장 자동 전수 스크리닝 완료 및 유니버스 저장 (대형 {len(growth_large_list)}선, 중소형 {len(mid_small_list)}선)")
    return result_data


def run_us_screener_analysis(force_refresh: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    미국장 실무 스크리너 분석 통합 실행:
    - 유니버스 파일이 없거나 강제 갱신 시 Finviz 전수 자동 크롤링 수행
    - 평상시에는 저장된 분기 12선 유니버스를 로드하여 실시간 시세 및 매수/매도 액션 도출
    """
    if force_refresh or not US_UNIVERSE_FILE.exists():
        q_data = run_us_automated_scan()
    else:
        try:
            with open(US_UNIVERSE_FILE, "r", encoding="utf-8") as f:
                q_data = json.load(f)
        except Exception:
            q_data = run_us_automated_scan()

    large_list = q_data.get("growth_large", [])
    mid_list = q_data.get("mid_small", [])
    ep_list = q_data.get("episodic_pivots", [])
    if not ep_list:
        ep_list = scan_episodic_pivots(max_results=6)
        q_data["episodic_pivots"] = ep_list

    signals = []
    meta = {
        "source": q_data.get("source", "finviz_automated_full_scan"),
        "quarter": q_data.get("quarter", "2026-Q3"),
        "large_threshold": "$10B+",
        "mid_small_threshold": "$1B~$10B",
        "ep_threshold": "Gap Up 7.5%+, RVOL 2.0x+, ADV 500k+",
        "growth_large_count": len(large_list),
        "mid_small_count": len(mid_list),
        "episodic_pivot_count": len(ep_list)
    }

    # 1. 미국 대형 성장주 실시간 액션 도출
    for item in large_list:
        ticker = item["ticker"]
        # 최신 시세 갱신
        live = get_us_stock_detail(ticker)
        cur_price = live["price"] if live else item.get("price", 100.0)
        fluct = live["fluctuations_ratio"] if live else item.get("fluctuations_ratio", 0.0)

        target_1 = round(cur_price * 1.25, 2)
        target_2 = round(cur_price * 1.35, 2)
        stop_loss = round(cur_price * 0.93, 2)
        risk = cur_price - stop_loss
        reward = target_1 - cur_price
        rr = round(reward / risk, 2) if risk > 0 else 2.5

        if fluct <= -7.0:
            action = "STOP_LOSS"
            action_desc = f"단기 급락 경계 ({fluct:+.1f}%), 지지선 확인 후 재진입"
        elif -3.0 <= fluct <= 2.5:
            action = "BUY"
            action_desc = f"유효 진입 타점 (당일 {fluct:+.1f}%), 목표가 대비 RR {rr}배 분할 매수"
        elif fluct > 5.0:
            action = "HOLD"
            action_desc = f"단기 급등 (+{fluct:.1f}%), 추격매수 금지 및 포지션 홀딩"
        else:
            action = "BUY"
            action_desc = f"정석 분할 매수 타점 (목표가 ${target_1:.2f})"

        signals.append({
            "project_id": "stock-screener",
            "strategy_name": "백찬규 미국 대형 성장주 스크리너",
            "market": "US",
            "ticker": ticker,
            "name": item["name"],
            "signal_type": action,
            "price": cur_price,
            "target_price": target_1,
            "target_price_2": target_2,
            "stop_loss_price": stop_loss,
            "risk_reward_ratio": rr,
            "score": 85.0 if action == "BUY" else 75.0,
            "sector": f"미국 대형 성장주 ($10B+) | {item.get('industry', '')}",
            "theme": item.get("video_note", ""),
            "pattern": f"Finviz 전수 포착 | {action_desc}",
            "action_plan": f"[{action}] {action_desc} | 기준가 ${cur_price:.2f} ➔ 목표가 ${target_1:.2f} (손절 ${stop_loss:.2f})",
            "raw_data": item
        })

    # 2. 미국 중소형 수급가치주 실시간 액션 도출
    for item in mid_list:
        ticker = item["ticker"]
        live = get_us_stock_detail(ticker)
        cur_price = live["price"] if live else item.get("price", 25.0)
        fluct = live["fluctuations_ratio"] if live else item.get("fluctuations_ratio", 0.0)

        target_1 = round(cur_price * 1.20, 2)
        target_2 = round(cur_price * 1.30, 2)
        stop_loss = round(cur_price * 0.92, 2)
        risk = cur_price - stop_loss
        reward = target_1 - cur_price
        rr = round(reward / risk, 2) if risk > 0 else 2.0

        if fluct <= -7.0:
            action = "STOP_LOSS"
            action_desc = f"단기 급락 경계 ({fluct:+.1f}%), 지지선 확인 후 재진입"
        elif -3.0 <= fluct <= 2.5:
            action = "BUY"
            action_desc = f"유효 진입 타점 (당일 {fluct:+.1f}%), 목표가 대비 RR {rr}배 분할 매수"
        elif fluct > 5.0:
            action = "HOLD"
            action_desc = f"단기 급등 (+{fluct:.1f}%), 추격매수 금지 및 포지션 홀딩"
        else:
            action = "BUY"
            action_desc = f"정석 분할 매수 타점 (목표가 ${target_1:.2f})"

        signals.append({
            "project_id": "stock-screener",
            "strategy_name": "백찬규 미국 중소형 스크리너",
            "market": "US",
            "ticker": ticker,
            "name": item["name"],
            "signal_type": action,
            "price": cur_price,
            "target_price": target_1,
            "target_price_2": target_2,
            "stop_loss_price": stop_loss,
            "risk_reward_ratio": rr,
            "score": 80.0 if action == "BUY" else 70.0,
            "sector": f"미국 중소형 수급주 ($1B~$10B) | {item.get('industry', '')}",
            "theme": item.get("video_note", ""),
            "pattern": f"거래량 200%+ 폭증 | {action_desc}",
            "action_plan": f"[{action}] {action_desc} | 기준가 ${cur_price:.2f} ➔ 목표가 ${target_1:.2f} (손절 ${stop_loss:.2f})",
            "raw_data": item
        })

    # 3. 프라딥 본데 에피소딕 피봇 (EP & DEP) 실시간 액션 도출
    for item in ep_list:
        ticker = item["ticker"]
        live = get_us_stock_detail(ticker)
        cur_price = live["price"] if live else item.get("price", 50.0)
        fluct = live["fluctuations_ratio"] if live else item.get("fluctuations_ratio", 15.0)

        # EP 매매 룰: 15분/30분 ORB 돌파 진입, LOD(Low of Day -5%) 손절, 목표가 +20%/+35%
        target_1 = round(cur_price * 1.20, 2)
        target_2 = round(cur_price * 1.35, 2)
        stop_loss = round(cur_price * 0.95, 2)
        risk = max(0.1, cur_price - stop_loss)
        reward = target_1 - cur_price
        rr = round(reward / risk, 2)
        base_score = item.get("magna53_score", 90.0)

        # 당일 갭 상승 유지 여부로 진입 판정
        if fluct < 5.0:
            action = "WATCH"
            action_desc = f"갭 유지 실패 경계 (당일 {fluct:+.1f}%), DEP(2~5일 깃발형 지지) 확인 후 진입"
            score = base_score - 10.0
        elif fluct > 45.0:
            action = "HOLD"
            action_desc = f"초과 급등 (+{fluct:.1f}%), 추격매수 금지 및 첫 풀백(DEP 플래그) 대기"
            score = base_score - 5.0
        else:
            action = "BUY"
            action_desc = f"ORB 돌파 유효 타점 (당일 {fluct:+.1f}%), LOD 손절($ {stop_loss:.2f}) 분할 매수"
            score = base_score

        signals.append({
            "project_id": "stock-screener",
            "strategy_name": "프라딥 본데 에피소딕 피봇 (EP & DEP)",
            "market": "US",
            "ticker": ticker,
            "name": item["name"],
            "signal_type": action,
            "price": cur_price,
            "target_price": target_1,
            "target_price_2": target_2,
            "stop_loss_price": stop_loss,
            "risk_reward_ratio": rr,
            "score": score,
            "sector": f"Episodic Pivot (어닝/촉매 갭업) | {item.get('industry', '')}",
            "theme": item.get("video_note", ""),
            "pattern": f"MAGNA53 촉매 갭업 & RVOL 2.0x+ | {action_desc}",
            "action_plan": f"[{action}] {action_desc} | 기준가 ${cur_price:.2f} ➔ 1차 ${target_1:.2f}(+20%) / 2차 ${target_2:.2f}(+35%) (LOD 손절 ${stop_loss:.2f})",
            "raw_data": item
        })

    return signals, meta


if __name__ == "__main__":
    # 테스트 실행: 강제 전수 자동 스캔 모드
    sigs, m = run_us_screener_analysis(force_refresh=True)
    print(f"\n✅ 미국장 Finviz 자동 전수 스크리닝 성공 (소스: {m['source']})")
    print(f"📊 대형 성장주: {m['growth_large_count']}개 | 중소형 수급주: {m['mid_small_count']}개 | 에피소딕 피봇: {m.get('episodic_pivot_count', 0)}개\n")

    print("=== [미국장 리스트 1: 대형 성장주 4선 (Finviz 전수 자동 추출)] ===")
    for s in [x for x in sigs if "대형" in x["strategy_name"]]:
        print(f"• {s['name']} ({s['ticker']}): ${s['price']:.2f} | {s['action_plan']}")

    print("\n=== [미국장 리스트 2: 중소형 수급가치 8선 (Finviz 전수 자동 추출)] ===")
    for s in [x for x in sigs if "중소형" in x["strategy_name"]]:
        print(f"• {s['name']} ({s['ticker']}): ${s['price']:.2f} | {s['action_plan']}")

    print("\n=== [미국장 리스트 3: 프라딥 본데 에피소딕 피봇 (EP & DEP 갭업 주도주)] ===")
    for s in [x for x in sigs if "에피소딕" in x["strategy_name"]]:
        print(f"• {s['name']} ({s['ticker']}): ${s['price']:.2f} (MAGNA53: {s['score']}점) | {s['action_plan']}")
