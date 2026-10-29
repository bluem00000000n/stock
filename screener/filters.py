#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screener/filters.py
백찬규 센터장(NH투자증권) 유튜브 실무 스크리너 조건 필터링 엔진

1. 한국주식 스크리너 - 성장주 후보:
   - 시가총액 1조원 이상
   - 27년 매출액 증감율 8% 이상
   - 27년 영업이익 증감율 16% 이상
   - 26년 ROE 15% 이상
   - EPS 추정치(최근 1M) 1% 이상
   - EPS 추정치(최근 3M) 0% 이상
   - 외국인 순매수 금액(억원, 20일) >= 0
   - 정렬: 거래량 52주평균 대비 5일평균 변화율 내림차순

2. 한국주식 중소형 스크리너:
   - 시가총액: 2,000억원 이상 1조원 이하
   - 거래량 52주 평균 대비 5일 평균 200% 이상 (또는 변화율 200%+)
   - 트레일링 P/B: 5% 이하 (또는 PBR 0.5 이하 또는 하위 5%)
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

    # % 기호 제거
    s = s.replace('%', '').replace(',', '').replace(' ', '')
    try:
        return float(s)
    except ValueError:
        return None


def normalize_market_cap(val: Any) -> Optional[float]:
    """
    시가총액을 '억원' 단위의 float으로 표준화
    - 1조원 = 10,000억원
    - 만약 수치가 1,000,000,000,000 (원 단위)이면 10,000으로 변환
    - 만약 수치가 10000 (억 단위)이면 10000 유지
    - 만약 수치가 1.5 (조 단위)이면 15000으로 변환
    """
    num = to_float(val)
    if num is None:
        return None

    if num > 100_000_000: # 원 단위 (예: 1,000,000,000,000원 -> 10,000억)
        return num / 100_000_000.0
    elif num < 100: # 조 단위 (예: 1.2조 -> 12,000억)
        return num * 10_000.0
    else: # 이미 억원 단위
        return num


def normalize_vol_ratio(item: Dict[str, Any]) -> float:
    """거래량 변화율(%)을 산출"""
    # 1. 이미 변화율 컬럼이 있는 경우
    rate = to_float(item.get("vol_change_rate"))
    if rate is not None:
        return rate

    # 2. 5일 평균과 52주 평균 거래량이 있는 경우
    vol_5d = to_float(item.get("vol_5d"))
    vol_52w = to_float(item.get("vol_52w"))
    if vol_5d is not None and vol_52w is not None and vol_52w > 0:
        return round(((vol_5d / vol_52w) - 1.0) * 100.0, 2)

    return 0.0


def filter_growth_large_candidates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    한국주식 스크리너 - 성장주 후보
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
        # 시총 검사
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
        vol_change = normalize_vol_ratio(item)

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
    한국주식 중소형 스크리너
    - 시가총액: 2,000억원 이상 ~ 1조원 이하 (2,000 <= 시총 <= 10,000 억원)
    - 거래량: 52주 평균 대비 5일 평균 200% 이상 (변화율 >= +200% 또는 비율 >= 2.0배)
    - 트레일링 P/B: 5% 이하 (또는 PBR <= 0.5 또는 상위 5% 저평가)
    """
    passed = []

    for item in items:
        # 시총 검사
        marcap_eok = normalize_market_cap(item.get("market_cap"))
        if marcap_eok is None or marcap_eok < 2_000 or marcap_eok > 10_000:
            continue

        # 거래량 검사: 52주 대비 5일 평균이 200% 이상 (변화율 >= 200.0% 또는 비율 >= 2.0)
        vol_ratio = 0.0
        vol_5d = to_float(item.get("vol_5d"))
        vol_52w = to_float(item.get("vol_52w"))
        vol_change = to_float(item.get("vol_change_rate"))

        if vol_5d is not None and vol_52w is not None and vol_52w > 0:
            vol_ratio = (vol_5d / vol_52w) * 100.0 # 200%
        elif vol_change is not None:
            # 변화율이 100% 증가면 배율은 200%
            vol_ratio = vol_change + 100.0 if vol_change >= 0 else 0.0

        if vol_ratio < 200.0:
            continue

        # 트레일링 P/B (5% 이하 또는 저PBR)
        trailing_pb = to_float(item.get("trailing_pb"))
        # 엑셀의 트레일링 P/B 값이 5 이하이거나(P/B %가 5 이하인 경우),
        # 절대 PBR로 0.05 또는 0.5 이하인 경우를 모두 허용
        if trailing_pb is not None and trailing_pb > 5.0:
            continue

        passed_item = dict(item)
        passed_item["_marcap_eok"] = marcap_eok
        passed_item["_vol_ratio"] = vol_ratio
        passed_item["_trailing_pb"] = trailing_pb if trailing_pb is not None else 0.0
        passed.append(passed_item)

    # 거래량 비율 내림차순 정렬
    passed.sort(key=lambda x: x["_vol_ratio"], reverse=True)
    return passed
