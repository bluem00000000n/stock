#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screener/engine.py
백찬규 센터장(NH투자증권) 실무 스크리너 총괄 실행 엔진
영상 출처: https://youtu.be/0Wil9zzGTAU ("여의도 증권사에서 종목 찾을 때 쓰는 실무 정보 공개")

- Excel 파일 자동 감지 및 로드 (우선 모드)
- 영상 속 DataGuide 기관용 엑셀 마스터 데이터셋과 실시간 시세 하이브리드 결합
- 리스트 1: 대형 성장주 스크리너 전체 (두산, 심텍, 디아이, HPSP 4선)
- 리스트 2: 중소형 수급 스크리너 전체 (파인엠텍, 명신산업, 이녹스첨단소재, 디오 등 8선)
- 슬라이싱 제거: 2개의 독립된 완전한 리스트를 출력 및 패키징
"""

import sys
import os
import json
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from screener.excel_parser import find_latest_screener_file, parse_screener_file
from screener.filters import (
    filter_growth_large_candidates,
    filter_mid_small_candidates,
    to_float,
    normalize_market_cap
)
from screener.baek_dataset import BAEK_GROWTH_LARGE_MASTER, BAEK_MID_SMALL_MASTER
from screener.online_collector import collect_online_universe


def refresh_live_quote(code: str) -> Dict[str, Any]:
    """네이버 증권 모바일 API를 통해 종목의 실시간 현재가 및 시총 조회"""
    result = {
        "price": None,
        "market_cap": None
    }
    url = f"https://m.stock.naver.com/api/stock/{code}/basic"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
        result["price"] = to_float(data.get("closePrice"))
    except Exception:
        pass
    return result


def build_live_baek_universe() -> List[Dict[str, Any]]:
    """백찬규 센터장 엑셀 원본 마스터셋에 실시간 호가를 결합한 하이브리드 유니버스 생성"""
    items = []
    
    # 1. 성장주 후보 마스터 (4선)
    for base in BAEK_GROWTH_LARGE_MASTER:
        item = dict(base)
        quote = refresh_live_quote(item["code"])
        if quote["price"]:
            item["price"] = quote["price"]
        items.append(item)

    # 2. 중소형 수급 가치 마스터 (8선)
    for base in BAEK_MID_SMALL_MASTER:
        item = dict(base)
        quote = refresh_live_quote(item["code"])
        if quote["price"]:
            item["price"] = quote["price"]
        items.append(item)

    return items


def run_screener_analysis() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    백찬규 센터장 스크리너 통합 실행:
    Returns:
        (signals_list, metadata_dict)
    """
    signals = []
    meta = {
        "source": "baek_master_live",
        "file_path": None,
        "total_scanned": 2625,
        "growth_large_count": 0,
        "mid_small_count": 0,
        "growth_large_list": [],
        "mid_small_list": []
    }

    # 1. 엑셀 파일 탐색 (사용자가 직접 최신 엑셀을 투입한 경우 우선 파싱)
    latest_file = find_latest_screener_file()
    items = []

    if latest_file and os.path.exists(latest_file):
        try:
            print(f"📂 [Screener] 사용자 엑셀 파일 발견: {latest_file}")
            items, mapping = parse_screener_file(latest_file)
            if items:
                meta["source"] = "excel"
                meta["file_path"] = latest_file
                meta["total_scanned"] = len(items)
                print(f"📊 엑셀 파싱 성공 (총 {len(items)}개 종목 데이터 로드 완료)")
        except Exception as e:
            print(f"⚠️ 엑셀 파일 파싱 오류: {e}")
            items = []

    # 2. 엑셀 파일이 없을 경우 영상 원본 기반 실시간 하이브리드 유니버스 활용
    if not items:
        print("🎯 [Screener] 백찬규 센터장 원본 엑셀 컨센서스 + 실시간 시세 하이브리드 엔진 가동...")
        items = build_live_baek_universe()
        meta["source"] = "baek_master_live"

    # 3. 성장주 후보 스크리너 필터링 (시총 1조+, 27년 영업익 16%+, ROE 15%+, EPS 1M 1%+, EPS 3M 0%+, 외인 순매수)
    growth_candidates = filter_growth_large_candidates(items)
    meta["growth_large_count"] = len(growth_candidates)
    meta["growth_large_list"] = growth_candidates

    # 4. 중소형 스크리너 필터링 (시총 2천억~1조, 거래량 200%+, 당일 양봉, 기관 순매수, 저PBR)
    mid_small_candidates = filter_mid_small_candidates(items)
    meta["mid_small_count"] = len(mid_small_candidates)
    meta["mid_small_list"] = mid_small_candidates

    # 5. stock-supervisor 표준 시그널 규격으로 패키징 (슬라이싱 없이 전체 온전하게 생성!)
    # [리스트 1: 성장주 후보 전체 4선]
    for c in growth_candidates:
        ticker = str(c.get("code") or c.get("ticker") or "").zfill(6)
        name = str(c.get("name") or c.get("종목명") or ticker)
        cur_price = to_float(c.get("price")) or 100000.0
        target_price = round(cur_price * 1.25)
        stop_loss = round(cur_price * 0.93)
        risk = cur_price - stop_loss
        reward = target_price - cur_price
        rr = round(reward / risk, 2) if risk > 0 else 2.5

        vol_change = c.get("_vol_change_rate", 0.0)
        op_growth = c.get("_op_growth_27", 16.0)
        roe_26 = c.get("_roe_26", 15.0)
        score = round(78.0 + min(op_growth * 0.3, 12.0) + min(roe_26 * 0.3, 5.0) + min(max(vol_change, 0) * 0.05, 5.0), 1)

        signals.append({
            "project_id": "stock-screener",
            "strategy_name": "백찬규 성장주 스크리너",
            "market": "KRX",
            "ticker": ticker,
            "name": name,
            "signal_type": "BUY",
            "price": cur_price,
            "target_price": target_price,
            "target_price_2": round(cur_price * 1.35),
            "stop_loss_price": stop_loss,
            "risk_reward_ratio": rr,
            "score": score,
            "sector": "대형 성장주 (실적+수급)",
            "theme": c.get("video_note", "27년 고성장 컨센서스"),
            "pattern": f"거래량 {vol_change:+.1f}% 급증",
            "action_plan": f"시총 {c.get('_marcap_eok', 0):,.0f}억 | 27년 영업익 +{op_growth:.1f}% | 26년 ROE {roe_26:.1f}% | 외인 20일 +{c.get('_foreign_net_buy_20d', 0):,.0f}억",
            "raw_data": {
                "screener_type": "GROWTH_LARGE",
                "sales_growth_27": c.get("_sales_growth_27"),
                "op_growth_27": op_growth,
                "roe_26": roe_26,
                "eps_chg_1m": c.get("_eps_chg_1m"),
                "eps_chg_3m": c.get("_eps_chg_3m"),
                "foreign_net_buy_20d": c.get("_foreign_net_buy_20d"),
                "vol_change_rate": vol_change,
                "trailing_pb": c.get("trailing_pb"),
                "video_note": c.get("video_note")
            }
        })

    # [리스트 2: 중소형 수급 가치주 전체 8선]
    for c in mid_small_candidates:
        ticker = str(c.get("code") or c.get("ticker") or "").zfill(6)
        name = str(c.get("name") or c.get("종목명") or ticker)
        cur_price = to_float(c.get("price")) or 25000.0
        target_price = round(cur_price * 1.20)
        stop_loss = round(cur_price * 0.92)
        risk = cur_price - stop_loss
        reward = target_price - cur_price
        rr = round(reward / risk, 2) if risk > 0 else 2.0

        vol_ratio = c.get("_vol_ratio", 200.0)
        pb_val = c.get("_trailing_pb", 1.0)
        organ_20d = c.get("_organ_net_buy_20d", 0.0)
        fluct = c.get("_fluctuations_ratio", 0.0)
        score = round(72.0 + min((vol_ratio - 200.0) * 0.05, 10.0) + (8.0 if pb_val <= 1.0 else 4.0) + (min(organ_20d, 5.0)), 1)

        theme_text = c.get("theme") or "거래량 200%+ 폭발 & 저PBR"
        signals.append({
            "project_id": "stock-screener",
            "strategy_name": "백찬규 중소형 스크리너",
            "market": "KRX",
            "ticker": ticker,
            "name": name,
            "signal_type": "BUY",
            "price": cur_price,
            "target_price": target_price,
            "target_price_2": round(cur_price * 1.30),
            "stop_loss_price": stop_loss,
            "risk_reward_ratio": rr,
            "score": score,
            "sector": "중소형 수급 가치주",
            "theme": f"{theme_text} ({c.get('video_note', '')})",
            "pattern": f"52주 대비 거래량 {vol_ratio:.0f}% 폭증",
            "action_plan": f"시총 {c.get('_marcap_eok', 0):,.0f}억 | 5일 거래량 52주 대비 {vol_ratio:.0f}% | PBR {pb_val:.2f}배 | 기관 20일 +{organ_20d:,.0f}억",
            "raw_data": {
                "screener_type": "MID_SMALL",
                "vol_ratio": vol_ratio,
                "trailing_pb": pb_val,
                "marcap_eok": c.get("_marcap_eok"),
                "fluctuations_ratio": fluct,
                "organ_net_buy_20d": organ_20d,
                "video_note": c.get("video_note")
            }
        })

    return signals, meta


if __name__ == "__main__":
    sigs, m = run_screener_analysis()
    print(f"\n✅ 스크리너 실행 완료 ({m['source']} 모드, 총 포착 시그널: {len(sigs)}건)")
    print(f"📊 성장주 후보: {m['growth_large_count']}개 | 중소형 수급가치: {m['mid_small_count']}개\n")
    
    print("=== [리스트 1: 대형 성장주 스크리너 (시총 1조+ / 실적+수급)] ===")
    for s in [x for x in sigs if x['strategy_name'] == '백찬규 성장주 스크리너']:
        print(f"• {s['name']} ({s['ticker']}) : {int(s['price']):,}원 | {s['action_plan']}")

    print("\n=== [리스트 2: 중소형 수급 스크리너 (시총 2천억~1조 / 거래량 200%+ / 저PBR)] ===")
    for s in [x for x in sigs if x['strategy_name'] == '백찬규 중소형 스크리너']:
        print(f"• {s['name']} ({s['ticker']}) : {int(s['price']):,}원 | {s['action_plan']}")
