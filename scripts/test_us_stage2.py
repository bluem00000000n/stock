import urllib.request, json

def get_us_basic_stats(ticker):
    for suffix in ['.O', '.N', '.K', '']:
        url = f'https://api.stock.naver.com/stock/{ticker}{suffix}/basic'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if not data or 'closePrice' not in data:
                    continue
                cur_str = str(data.get('closePrice', '0')).replace(',', '')
                cur = float(cur_str)
                if cur <= 0:
                    continue
                h52 = 0.0
                l52 = 0.0
                for item in data.get('stockItemTotalInfos', []):
                    code = item.get('code', '')
                    val = str(item.get('value', '0')).replace(',', '').replace('$', '')
                    if code == 'highPriceOf52Weeks':
                        try: h52 = float(val)
                        except: pass
                    elif code == 'lowPriceOf52Weeks':
                        try: l52 = float(val)
                        except: pass
                
                pct_h = ((cur - h52) / h52 * 100) if h52 > 0 else 0.0
                pct_l = ((cur - l52) / l52 * 100) if l52 > 0 else 0.0
                
                is_stage2 = (pct_h >= -20.0) and (pct_l >= 20.0)
                return {
                    'cur': cur,
                    'h52': h52,
                    'l52': l52,
                    'pct_h': round(pct_h, 1),
                    'pct_l': round(pct_l, 1),
                    'is_stage2': is_stage2
                }
        except Exception:
            pass
    return None

test_pool = [
    'TQQQ', 'CRWD', 'AXON', 'NOW', 'PANW', 'FTNT', 'CAT', 'WMT', 'NFLX', 'SPOT',
    'ORCL', 'IBM', 'ISRG', 'BKNG', 'UBER', 'MCK', 'COR', 'CAH', 'PWR', 'EME'
]

print('| Ticker | Price | 52W High | 52W Low | High Diff | Low Diff | Stage 2 |')
for t in test_pool:
    m = get_us_basic_stats(t)
    if m:
        c = m['cur']
        h = m['h52']
        l = m['l52']
        ph = m['pct_h']
        pl = m['pct_l']
        verdict = '✅ OK' if m['is_stage2'] else '❌ FAIL'
        print(f'| {t} | {c} | {h} | {l} | {ph}% | {pl}% | {verdict} |')
