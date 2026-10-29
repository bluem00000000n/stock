#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screener/filters.py
백찬규 센터장(NH투자증권) 유튜브 실무 스크리너 조건 필터링 엔진
영상 출처: https://youtu.be/0Wil9zzGTAU ("여의도 증권사에서 종목 찾을 때 쓰는 실무 정보 공개")

1. 한국주식 스크리너 - 성장주 후보 (대형주):
   - 시가총액 1조원 이상
   - 27년 매출액 증감율 8% 이상
   - 27년 영업이익 증감율 16% 이상
   - 26년 ROE 15% 이상
   - EPS 추정치(최근 1M) 1% 이상
   - EPS 추정치(최근 3M) 0% 이상
   - 외국인 순매수 금액(억원, 20일) >= 0
   - 정렬: 거래량 52주평균 대비 5일평균 변화율 내림차순
   => 영상 최종 도출 4종목: 두산, 심텍, 디아이, HPSP

2. 한국주식 중소형 스크리너 (중소형주 수급 가치):
   - 시가총액: 2,000억원 이상 1조원 이하 (1,200억~1조 유연 매칭)
   - 거래량 52주 평균 대비 5일 평균 200% 이상 (5일 평균 거래량 2배 폭증)
   - 당일 등락률 > 0% (거래량 터진 음봉 손절매 제외, 거래량 터진 양봉만 선별)
   - 기관 20일 순매수 금액 > 0 (기관 수급 유입)
   - 트레일링 P/B: 5.0배 이하 (저PBR / 낙폭과대 바닥탈출)
   => 영상 최종 도출 8종목: 파인엠텍, 명신산업, 이녹스첨단소재, 디오 등
"""

import re
from typing import List, Dict, Any, Optional


def to_float(val: Any) -> Optional[float]:
    """문자열, %, 쉼표가 섞인 다양한 수치를 float으로 안전 변환"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s or s in ('-', 'N/A', 'NaN', 'null', 'none', '#N/A', '#DIV/0!'):
        return None

    s = s.replace('%', '').replace(',', '').replace(' ', '')
    try:
        return float(s)
    except ValueError:
        return None


def normalize_market_cap(val: Any) -> Optional[float]:
    """
    시가총액을 '억원' 단위의 float으로 표준화
    - 1조원 = 10,000억원
    """
    num = to_float(val)
    if num is None:
        return None

    if num > 100_000_000: # 원 단위 (1조원 -> 10,000억)
        return num / 100_000_000.0
    elif num < 100: # 조 단위 (1.5조 -> 15,000억)
        return num * 10_000.0
    else: # 이미 억원 단위
        return num


def normalize_vol_ratio(item: Dict[str, Any]) -> float:
    """거래량 52주 대비 5일 평균 비율(%) 또는 변화율 산출"""
    # 1. 이미 배율(vol_ratio)이 제공된 경우
    ratio = to_float(item.get("vol_ratio"))
    if ratio is not None:
        return ratio

    # 2. 변화율(vol_change_rate)이 있는 경우 (예: +100% -> 200% 배율)
    rate = to_float(item.get("vol_change_rate"))
    if rate is not None:
        return rate + 100.0 if rate >= 0 else rate

    # 3. 5일 평균과 52주 평균 거래량이 있는 경우
    vol_5d = to_float(item.get("vol_5d"))
    vol_52w = to_float(item.get("vol_52w"))
    if vol_5d is not None and vol_52w is not None and vol_52w > 0:
        return round((vol_5d / vol_52w) * 100.0, 1)

    return 100.0


def filter_growth_large_candidates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    한국주식 스크리너 - 성장주 후보 (대형주)
    - 시가총액: 1조원 이상 (>= 10,000억원)
    - 27년 매출액 증감율: 8% 이상
    - 27년 영업이익 증감율: 16% 이상
    - 26년 ROE: 15% 이상
    - EPS 추정치 (최근 1M): 1% 이상
    - EPS 추정치 (최근 3M): 0% 이상
    - 외국인 순매수 금액 (20일): 0 이상
    - 정렬: 거래량 (52주평균 대비 5일평균 변화율) 내림차순
    """
    passed = []

    for item in items:
        # 시총 검사 (1조원 = 10,000억원)
        marcap_eok = normalize_market_cap(item.get("market_cap"))
        if marcap_eok is None or marcap_eok < 10_000:
            continue

        # 27년 매출액 증감율 (>= 8.0%)
        sales_27 = to_float(item.get("sales_growth_27"))
        if sales_27 is None or sales_27 < 8.0:
            continue

        # 27년 영업이익 증감율 (>= 16.0%)
        op_27 = to_float(item.get("op_growth_27"))
        if op_27 is None or op_27 < 16.0:
            continue

        # 26년 ROE (>= 15.0%)
        roe_26 = to_float(item.get("roe_26"))
        if roe_26 is None or roe_26 < 15.0:
            continue

        # EPS 1M (>= 1.0%)
        eps_1m = to_float(item.get("eps_chg_1m"))
        if eps_1m is None or eps_1m < 1.0:
            continue

        # EPS 3M (>= 0.0%)
        eps_3m = to_float(item.get("eps_chg_3m"))
        if eps_3m is None or eps_3m < 0.0:
            continue

        # 외국인 순매수 금액 20일 (>= 0)
        foreign_20d = to_float(item.get("foreign_net_buy_20d"))
        if foreign_20d is None or foreign_20d < 0.0:
            continue

        # 거래량 변화율 계산
        vol_change = to_float(item.get("vol_change_rate"))
        if vol_change is None:
            vr = normalize_vol_ratio(item)
            vol_change = vr - 100.0

        passed_item = dict(item)
        passed_item["_marcap_eok"] = marcap_eok
        passed_item["_sales_growth_27"] = sales_27
        passed_item["_op_growth_27"] = op_27
        passed_item["_roe_26"] = roe_26
        passed_item["_eps_chg_1m"] = eps_1m
        passed_item["_eps_chg_3m"] = eps_3m
        passed_item["_foreign_net_buy_20d"] = foreign_20d
        passed_item["_vol_change_rate"] = vol_change
        passed.append(passed_item)

    # 거래량 52주 대비 5일 평균 변화율 내림차순 정렬
    passed.sort(key=lambda x: x["_vol_change_rate"], reverse=True)
    return passed


def filter_mid_small_candidates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    한국주식 중소형 스크리너 (중소형주 수급 가치)
    - 시가총액: 2,000억원 이상 ~ 1조원 이하 (1,200억~1조 유연 커버)
    - 거래량: 52주 평균 대비 5일 평균 200% 이상 (5일 평균이 52주 평균의 2배 폭증)
    - 당일 등락률: > 0% (손절매 음봉 제외, 양봉 반등 종목만)
    - 기관 순매수 (20일): >= 0 (기관 수급 플러스 유입)
    - 트레일링 P/B: 5.0배 이하 (저PBR / 바닥탈출)
    """
    passed = []

    for item in items:
        # 시총 검사: 2,000억 ~ 10,000억 (1,200억 이상 유연 커버)
        marcap_eok = normalize_market_cap(item.get("market_cap"))
        if marcap_eok is None or marcap_eok < 1200 or marcap_eok > 10_000:
            continue

        # 거래량 검사: 52주 대비 5일 평균이 200% 이상
        vol_ratio = normalize_vol_ratio(item)
        if vol_ratio < 200.0:
            continue

        # 당일 등락률 검사 (음봉 손절매 제외, 양봉 반등 > 0%)
        fluct = to_float(item.get("fluctuations_ratio"))
        # fluctuations_ratio가 있는 경우 0% 초과여야 함 (데이터 미제공 시 통과)
        if fluct is not None and fluct <= 0.0:
            continue

        # 기관 20일 순매수 검사 (기관 수급 플러스)
        organ_20d = to_float(item.get("organ_net_buy_20d"))
        if organ_20d is not None and organ_20d < 0.0:
            continue

        # 트레일링 P/B (5.0배 이하 또는 저PBR)
        trailing_pb = to_float(item.get("trailing_pb"))
        if trailing_pb is not None and trailing_pb > 5.0:
            continue

        passed_item = dict(item)
        passed_item["_marcap_eok"] = marcap_eok
        passed_item["_vol_ratio"] = vol_ratio
        passed_item["_trailing_pb"] = trailing_pb if trailing_pb is not None else 1.0
        passed_item["_fluctuations_ratio"] = fluct if fluct is not None else 0.0
        passed_item["_organ_net_buy_20d"] = organ_20d if organ_20d is not None else 0.0
        passed.append(passed_item)

    # 거래량 비율 내림차순 정렬
    passed.sort(key=lambda x: x["_vol_ratio"], reverse=True)
    return passed
