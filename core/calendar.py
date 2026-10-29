#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/calendar.py
한국거래소(KRX) 및 미국증시(NYSE/NASDAQ) 개장 여부 판정 모듈
주말, 법정 공휴일, 대체 공휴일, 임시 공휴일 자동 감지
"""

import datetime
import zoneinfo
from typing import Tuple

# 한국 공휴일 및 주요 휴장일 (2024~2030)
KRX_HOLIDAYS = {
    # 2024
    datetime.date(2024, 1, 1): "신정",
    datetime.date(2024, 2, 9): "설날 연휴",
    datetime.date(2024, 2, 12): "설날 대체공휴일",
    datetime.date(2024, 3, 1): "삼일절",
    datetime.date(2024, 4, 10): "제22대 국회의원 선거",
    datetime.date(2024, 5, 1): "근로자의 날",
    datetime.date(2024, 5, 6): "어린이날 대체공휴일",
    datetime.date(2024, 5, 15): "부처님오신날",
    datetime.date(2024, 6, 6): "현충일",
    datetime.date(2024, 8, 15): "광복절",
    datetime.date(2024, 9, 16): "추석 연휴",
    datetime.date(2024, 9, 17): "추석",
    datetime.date(2024, 9, 18): "추석 연휴",
    datetime.date(2024, 10, 1): "국군의 날(임시공휴일)",
    datetime.date(2024, 10, 3): "개천절",
    datetime.date(2024, 10, 9): "한글날",
    datetime.date(2024, 12, 25): "크리스마스",
    datetime.date(2024, 12, 31): "연말 휴장일",
    # 2025
    datetime.date(2025, 1, 1): "신정",
    datetime.date(2025, 1, 27): "설날 연휴",
    datetime.date(2025, 1, 28): "설날 연휴",
    datetime.date(2025, 1, 29): "설날",
    datetime.date(2025, 1, 30): "설날 연휴",
    datetime.date(2025, 3, 3): "삼일절 대체공휴일",
    datetime.date(2025, 5, 1): "근로자의 날",
    datetime.date(2025, 5, 5): "어린이날",
    datetime.date(2025, 5, 6): "부처님오신날 대체공휴일",
    datetime.date(2025, 6, 6): "현충일",
    datetime.date(2025, 8, 15): "광복절",
    datetime.date(2025, 10, 3): "개천절",
    datetime.date(2025, 10, 6): "추석",
    datetime.date(2025, 10, 7): "추석 연휴",
    datetime.date(2025, 10, 8): "추석 대체공휴일",
    datetime.date(2025, 10, 9): "한글날",
    datetime.date(2025, 12, 25): "크리스마스",
    datetime.date(2025, 12, 31): "연말 휴장일",
    # 2026
    datetime.date(2026, 1, 1): "신정",
    datetime.date(2026, 2, 16): "설날 연휴",
    datetime.date(2026, 2, 17): "설날",
    datetime.date(2026, 2, 18): "설날 연휴",
    datetime.date(2026, 3, 2): "삼일절 대체공휴일",
    datetime.date(2026, 5, 1): "근로자의 날",
    datetime.date(2026, 5, 5): "어린이날",
    datetime.date(2026, 5, 25): "부처님오신날 대체공휴일",
    datetime.date(2026, 6, 3): "지방선거일",
    datetime.date(2026, 8, 17): "광복절 대체공휴일",
    datetime.date(2026, 9, 24): "추석 연휴",
    datetime.date(2026, 9, 25): "추석",
    datetime.date(2026, 9, 26): "추석 연휴",
    datetime.date(2026, 10, 5): "개천절 대체공휴일",
    datetime.date(2026, 10, 9): "한글날",
    datetime.date(2026, 12, 25): "크리스마스",
    datetime.date(2026, 12, 31): "연말 휴장일",
}

# 미국 주요 휴장일 (NYSE / NASDAQ)
US_HOLIDAYS = {
    # 2024
    datetime.date(2024, 1, 1): "New Year's Day",
    datetime.date(2024, 1, 15): "Martin Luther King, Jr. Day",
    datetime.date(2024, 2, 19): "Washington's Birthday",
    datetime.date(2024, 3, 29): "Good Friday",
    datetime.date(2024, 5, 27): "Memorial Day",
    datetime.date(2024, 6, 19): "Juneteenth",
    datetime.date(2024, 7, 4): "Independence Day",
    datetime.date(2024, 9, 2): "Labor Day",
    datetime.date(2024, 11, 28): "Thanksgiving Day",
    datetime.date(2024, 12, 25): "Christmas Day",
    # 2025
    datetime.date(2025, 1, 1): "New Year's Day",
    datetime.date(2025, 1, 20): "Martin Luther King, Jr. Day",
    datetime.date(2025, 2, 17): "Washington's Birthday",
    datetime.date(2025, 4, 18): "Good Friday",
    datetime.date(2025, 5, 26): "Memorial Day",
    datetime.date(2025, 6, 19): "Juneteenth",
    datetime.date(2025, 7, 4): "Independence Day",
    datetime.date(2025, 9, 1): "Labor Day",
    datetime.date(2025, 11, 27): "Thanksgiving Day",
    datetime.date(2025, 12, 25): "Christmas Day",
    # 2026
    datetime.date(2026, 1, 1): "New Year's Day",
    datetime.date(2026, 1, 19): "Martin Luther King, Jr. Day",
    datetime.date(2026, 2, 16): "Washington's Birthday",
    datetime.date(2026, 4, 3): "Good Friday",
    datetime.date(2026, 5, 25): "Memorial Day",
    datetime.date(2026, 6, 19): "Juneteenth",
    datetime.date(2026, 7, 3): "Independence Day (Observed)",
    datetime.date(2026, 9, 7): "Labor Day",
    datetime.date(2026, 11, 26): "Thanksgiving Day",
    datetime.date(2026, 12, 25): "Christmas Day",
}


def is_krx_open(dt: datetime.datetime = None) -> Tuple[bool, str]:
    """한국 거래소(KRX) 개장일 여부 확인"""
    if dt is None:
        dt = datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Seoul"))
    d = dt.date()

    if d.weekday() >= 5:
        return False, f"주말 휴장 ({['토요일', '일요일'][d.weekday()-5]})"

    if d in KRX_HOLIDAYS:
        return False, f"공휴일/휴장일 ({KRX_HOLIDAYS[d]})"

    return True, "정상 개장일"


def is_us_open(dt: datetime.datetime = None) -> Tuple[bool, str]:
    """미국 증시(NYSE/NASDAQ) 개장일 여부 확인 (미국 동부 시간 기준)"""
    if dt is None:
        dt = datetime.datetime.now(zoneinfo.ZoneInfo("America/New_York"))
    d = dt.date()

    if d.weekday() >= 5:
        return False, f"주말 휴장 ({['토요일', '일요일'][d.weekday()-5]})"

    if d in US_HOLIDAYS:
        return False, f"미국 공휴일/휴장일 ({US_HOLIDAYS[d]})"

    return True, "정상 개장일"


if __name__ == "__main__":
    kr_open, kr_reason = is_krx_open()
    us_open, us_reason = is_us_open()
    print(f"🇰🇷 KRX 개장 여부: {kr_open} ({kr_reason})")
    print(f"🇺🇸 US 개장 여부:  {us_open} ({us_reason})")
