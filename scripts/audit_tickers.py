import sys
from pathlib import Path

BASE_DIR = Path("/Users/tothemoon/stock-supervisor")
sys.path.insert(0, str(BASE_DIR))

from core.etf_rotation_analyzer import GICS_11_SECTORS, INDUSTRY_THEMES, BROAD_MARKET_ASSETS, LEVERAGE_ETFS, ETFDataCollector

all_tickers = sorted(list(set(
    list(GICS_11_SECTORS.keys())
    + list(INDUSTRY_THEMES.keys())
    + list(BROAD_MARKET_ASSETS.keys())
    + list(LEVERAGE_ETFS.keys())
)))

print(f"Total tickers: {len(all_tickers)}")
missing = []
for t in all_tickers:
    info = ETFDataCollector.get_live_info(t)
    if not info or info.get("aum", 0) <= 0:
        print(f"❌ MISSING / ZERO AUM: {t} -> info={info}")
        missing.append(t)
    else:
        p = info["price"]
        aum = info["aum"] / 1e9
        shares = info["shares"] / 1e6
        sym = info["symbol_used"]
        print(f"✅ {t:6s} | Price: {p:8.2f} | AUM: ${aum:8.2f}B | Shares: {shares:8.2f}M | Sym: {sym}")

print(f"\nAudit Finished. Total missing: {len(missing)} -> {missing}")
