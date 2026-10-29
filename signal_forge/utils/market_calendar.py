"""
Market Trading Calendar & Session Manager.
Enforces real-world market operating hours, weekends, and statutory public holidays
for Korean Stocks (KRX), US Stocks (NYSE/NASDAQ), and Crypto (Binance).
Prevents unrealistic off-hours/weekend order executions.
"""

from datetime import datetime, time, timezone, timedelta
from typing import Dict, Optional, Set, Tuple
import zoneinfo
from signal_forge.models.signal import AssetType
from signal_forge.observability.logger import get_logger

logger = get_logger("market_calendar")

# Timezones
KST = timezone(timedelta(hours=9))
US_EASTERN = zoneinfo.ZoneInfo("America/New_York")

# Korean Statutory & KRX Holidays (2025 - 2027)
KR_HOLIDAYS: Dict[str, str] = {
    # 2025
    "2025-01-01": "신정 (New Year)",
    "2025-01-28": "설날 연휴 (Lunar New Year)",
    "2025-01-29": "설날 (Lunar New Year)",
    "2025-01-30": "설날 연휴 (Lunar New Year)",
    "2025-03-01": "삼일절 (Independence Movement Day)",
    "2025-03-03": "삼일절 대체공휴일",
    "2025-05-05": "어린이날 (Children's Day)",
    "2025-05-06": "부처님오신날 대체공휴일",
    "2025-06-06": "현충일 (Memorial Day)",
    "2025-08-15": "광복절 (Liberation Day)",
    "2025-10-03": "개천절 (National Foundation Day)",
    "2025-10-05": "추석 연휴 (Chuseok)",
    "2025-10-06": "추석 (Chuseok)",
    "2025-10-07": "추석 연휴 (Chuseok)",
    "2025-10-08": "추석 대체공휴일",
    "2025-10-09": "한글날 (Hangul Day)",
    "2025-12-25": "성탄절 (Christmas)",
    "2025-12-31": "한국거래소 연말 휴장일 (KRX Year-End)",
    # 2026
    "2026-01-01": "신정 (New Year)",
    "2026-02-16": "설날 연휴 (Lunar New Year)",
    "2026-02-17": "설날 (Lunar New Year)",
    "2026-02-18": "설날 연휴 (Lunar New Year)",
    "2026-03-01": "삼일절 (Independence Movement Day)",
    "2026-03-02": "삼일절 대체공휴일",
    "2026-05-05": "어린이날 (Children's Day)",
    "2026-05-24": "부처님오신날 (Buddha's Birthday)",
    "2026-05-25": "부처님오신날 대체공휴일",
    "2026-06-06": "현충일 (Memorial Day)",
    "2026-08-15": "광복절 (Liberation Day)",
    "2026-08-17": "광복절 대체공휴일",
    "2026-09-24": "추석 연휴 (Chuseok)",
    "2026-09-25": "추석 (Chuseok)",
    "2026-09-26": "추석 연휴 (Chuseok)",
    "2026-10-03": "개천절 (National Foundation Day)",
    "2026-10-05": "개천절 대체공휴일",
    "2026-10-09": "한글날 (Hangul Day)",
    "2026-12-25": "성탄절 (Christmas)",
    "2026-12-31": "한국거래소 연말 휴장일 (KRX Year-End)",
}

# US Federal & NYSE/NASDAQ Holidays (2025 - 2027)
US_HOLIDAYS: Dict[str, str] = {
    # 2025
    "2025-01-01": "New Year's Day",
    "2025-01-20": "Martin Luther King Jr. Day",
    "2025-02-17": "Presidents' Day",
    "2025-04-18": "Good Friday",
    "2025-05-26": "Memorial Day",
    "2025-06-19": "Juneteenth National Independence Day",
    "2025-07-04": "Independence Day",
    "2025-09-01": "Labor Day",
    "2025-11-27": "Thanksgiving Day",
    "2025-12-25": "Christmas Day",
    # 2026
    "2026-01-01": "New Year's Day",
    "2026-01-19": "Martin Luther King Jr. Day",
    "2026-02-16": "Presidents' Day",
    "2026-04-03": "Good Friday",
    "2026-05-25": "Memorial Day",
    "2026-06-19": "Juneteenth National Independence Day",
    "2026-07-03": "Independence Day (Observed)",
    "2026-09-07": "Labor Day",
    "2026-11-26": "Thanksgiving Day",
    "2026-12-25": "Christmas Day",
}


def is_kr_stock_market_open(dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """Evaluates whether the Korean Stock Exchange (KRX: KOSPI/KOSDAQ) is currently open.
    
    Rules:
    - Trading days: Monday to Friday.
    - Closed on weekends (Saturday, Sunday).
    - Closed on statutory public holidays & KRX year-end closing day.
    - Regular trading session: 09:00:00 to 15:30:00 KST.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    kst_dt = dt.astimezone(KST)

    # 1. Weekend check
    weekday = kst_dt.weekday()
    if weekday == 5:
        return False, "주말 휴장 (토요일)"
    if weekday == 6:
        return False, "주말 휴장 (일요일)"

    # 2. Public / Exchange holiday check
    date_key = kst_dt.strftime("%Y-%m-%d")
    if date_key in KR_HOLIDAYS:
        return False, f"공휴일/거래소 휴장일 ({KR_HOLIDAYS[date_key]})"

    # 3. Regular market hours (09:00 ~ 15:30 KST)
    cur_time = kst_dt.time()
    open_time = time(9, 0, 0)
    close_time = time(15, 30, 0)

    if cur_time < open_time:
        return False, f"장 시작 전 (현재 {cur_time.strftime('%H:%M:%S')} KST / 개장 시각: 09:00 KST)"
    if cur_time >= close_time:
        return False, f"장 마감 (현재 {cur_time.strftime('%H:%M:%S')} KST / 마감 시각: 15:30 KST)"

    return True, "정규장 거래 시간 (09:00 ~ 15:30 KST)"


def is_us_stock_market_open(dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """Evaluates whether the US Stock Exchanges (NYSE/NASDAQ) are currently open.
    
    Rules:
    - Trading days: Monday to Friday.
    - Closed on weekends (Saturday, Sunday).
    - Closed on US federal/market holidays.
    - Regular trading session: 09:30:00 to 16:00:00 US Eastern Time.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    et_dt = dt.astimezone(US_EASTERN)

    # 1. Weekend check
    weekday = et_dt.weekday()
    if weekday == 5:
        return False, "US Weekend Closed (Saturday)"
    if weekday == 6:
        return False, "US Weekend Closed (Sunday)"

    # 2. Holiday check
    date_key = et_dt.strftime("%Y-%m-%d")
    if date_key in US_HOLIDAYS:
        return False, f"US Market Holiday ({US_HOLIDAYS[date_key]})"

    # 3. Regular market hours (09:30 ~ 16:00 ET)
    cur_time = et_dt.time()
    open_time = time(9, 30, 0)
    close_time = time(16, 0, 0)

    if cur_time < open_time:
        return False, f"Pre-market Closed (Current {cur_time.strftime('%H:%M:%S')} ET / Open: 09:30 ET)"
    if cur_time >= close_time:
        return False, f"Post-market Closed (Current {cur_time.strftime('%H:%M:%S')} ET / Close: 16:00 ET)"

    return True, "US Regular Trading Session (09:30 ~ 16:00 ET)"


def is_crypto_market_open(dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """Crypto markets trade 24/7/365 without closures or holidays."""
    return True, "Crypto 24/7 Continuous Trading"


def is_market_open(asset_type: AssetType, dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """Unified entry point to verify market operating session for any asset type."""
    if asset_type == AssetType.COIN:
        return is_crypto_market_open(dt)
    elif asset_type == AssetType.STOCK_KR:
        return is_kr_stock_market_open(dt)
    elif asset_type == AssetType.STOCK_US:
        return is_us_stock_market_open(dt)
    return True, "Market Open"
