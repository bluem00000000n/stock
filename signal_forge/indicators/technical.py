"""
High-performance pure Python technical indicators and feature engineering.
Strict zero-dependency implementation for maximum portability and deterministic tests.
"""

import math
from typing import Dict, List, Optional, Tuple


def calculate_sma(data: List[float], period: int) -> List[Optional[float]]:
    """Simple Moving Average (SMA)."""
    if period <= 0:
        raise ValueError("Period must be positive")
    result: List[Optional[float]] = [None] * len(data)
    if len(data) < period:
        return result

    window_sum = sum(data[:period])
    result[period - 1] = window_sum / period

    for i in range(period, len(data)):
        window_sum += data[i] - data[i - period]
        result[i] = window_sum / period

    return result


def calculate_ema(data: List[float], period: int) -> List[Optional[float]]:
    """Exponential Moving Average (EMA)."""
    if period <= 0:
        raise ValueError("Period must be positive")
    result: List[Optional[float]] = [None] * len(data)
    if len(data) < period:
        return result

    multiplier = 2.0 / (period + 1.0)
    sma_first = sum(data[:period]) / period
    result[period - 1] = sma_first

    current_ema = sma_first
    for i in range(period, len(data)):
        current_ema = (data[i] - current_ema) * multiplier + current_ema
        result[i] = current_ema

    return result


def calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """Wilder's Relative Strength Index (0 to 100)."""
    if period <= 0:
        raise ValueError("Period must be positive")
    n = len(prices)
    result: List[Optional[float]] = [None] * n
    if n <= period:
        return result

    gains = []
    losses = []
    for i in range(1, n):
        change = prices[i] - prices[i - 1]
        gains.append(max(0.0, change))
        losses.append(max(0.0, -change))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0.0:
        result[period] = 100.0 if avg_gain > 0 else 50.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, n):
        gain = gains[i - 1]
        loss = losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0.0:
            result[i] = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))

    return result


def calculate_bollinger_bands(
    prices: List[float], period: int = 20, num_std: float = 2.0
) -> Dict[str, List[Optional[float]]]:
    """Bollinger Bands (Upper, Middle/SMA, Lower, Bandwidth)."""
    sma = calculate_sma(prices, period)
    upper: List[Optional[float]] = [None] * len(prices)
    lower: List[Optional[float]] = [None] * len(prices)
    bandwidth: List[Optional[float]] = [None] * len(prices)

    for i in range(period - 1, len(prices)):
        mean = sma[i]
        if mean is None:
            continue
        window = prices[i - period + 1 : i + 1]
        variance = sum((x - mean) ** 2 for x in window) / period
        std_dev = math.sqrt(variance)

        up = mean + num_std * std_dev
        dn = mean - num_std * std_dev
        upper[i] = up
        lower[i] = dn
        bandwidth[i] = (up - dn) / mean if mean != 0 else 0.0

    return {
        "upper": upper,
        "middle": sma,
        "lower": lower,
        "bandwidth": bandwidth,
    }


def calculate_atr(
    highs: List[float], lows: List[float], closes: List[float], period: int = 14
) -> List[Optional[float]]:
    """Average True Range (ATR)."""
    n = len(closes)
    result: List[Optional[float]] = [None] * n
    if n <= period or len(highs) != n or len(lows) != n:
        return result

    tr = [highs[0] - lows[0]]
    for i in range(1, n):
        h = highs[i]
        l = lows[i]
        prev_c = closes[i - 1]
        tr.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))

    atr = sum(tr[:period]) / period
    result[period - 1] = atr

    for i in range(period, n):
        atr = (atr * (period - 1) + tr[i]) / period
        result[i] = atr

    return result


def calculate_vwap(
    highs: List[float], lows: List[float], closes: List[float], volumes: List[float]
) -> List[Optional[float]]:
    """Cumulative Volume Weighted Average Price (VWAP)."""
    n = len(closes)
    result: List[Optional[float]] = [None] * n
    if n == 0 or len(highs) != n or len(lows) != n or len(volumes) != n:
        return result

    cum_pv = 0.0
    cum_vol = 0.0
    for i in range(n):
        typical_price = (highs[i] + lows[i] + closes[i]) / 3.0
        v = volumes[i]
        cum_pv += typical_price * v
        cum_vol += v
        result[i] = (cum_pv / cum_vol) if cum_vol > 0 else typical_price

    return result


def calculate_rvol(volumes: List[float], period: int = 20) -> List[Optional[float]]:
    """Relative Volume (RVOL) compared to rolling average volume."""
    n = len(volumes)
    result: List[Optional[float]] = [None] * n
    if n <= period:
        return result

    for i in range(period, n):
        window = volumes[i - period : i]
        avg_vol = sum(window) / period
        result[i] = (volumes[i] / avg_vol) if avg_vol > 0 else 1.0

    return result


def calculate_volume_z_score(
    volumes: List[float], period: int = 20
) -> List[Optional[float]]:
    """Volume Z-score."""
    n = len(volumes)
    result: List[Optional[float]] = [None] * n
    if n <= period:
        return result

    for i in range(period, n):
        window = volumes[i - period : i]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = math.sqrt(variance)
        result[i] = ((volumes[i] - mean) / std) if std > 0 else 0.0

    return result


def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Dict[str, List[Optional[float]]]:
    """Moving Average Convergence Divergence (MACD, Signal, Histogram)."""
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)
    n = len(prices)

    macd_line: List[Optional[float]] = [None] * n
    valid_macd_indices = []
    valid_macd_values = []

    for i in range(n):
        if fast_ema[i] is not None and slow_ema[i] is not None:
            val = fast_ema[i] - slow_ema[i]
            macd_line[i] = val
            valid_macd_indices.append(i)
            valid_macd_values.append(val)

    signal_line: List[Optional[float]] = [None] * n
    histogram: List[Optional[float]] = [None] * n

    if len(valid_macd_values) >= signal_period:
        sub_signal = calculate_ema(valid_macd_values, signal_period)
        for idx, s_val in zip(valid_macd_indices, sub_signal):
            signal_line[idx] = s_val
            if macd_line[idx] is not None and s_val is not None:
                histogram[idx] = macd_line[idx] - s_val

    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }


def calculate_highest(data: List[float], period: int) -> List[Optional[float]]:
    """Highest value over rolling period."""
    result: List[Optional[float]] = [None] * len(data)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = max(data[i - period + 1 : i + 1])
    return result


def calculate_lowest(data: List[float], period: int) -> List[Optional[float]]:
    """Lowest value over rolling period."""
    result: List[Optional[float]] = [None] * len(data)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = min(data[i - period + 1 : i + 1])
    return result
