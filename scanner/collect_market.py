"""Collect daily prices (1 year) for regime, sectors, themes, Mag 7 and sector candidates, plus live market caps.
Source: Yahoo Finance via yfinance (free). Output: data/<date>/prices.csv, volumes.csv, market_caps.json"""
import sys, time
import pandas as pd
from common import load_config, day_dir, save_json


def all_tickers(cfg):
    t = {v for k, v in cfg['regime'].items() if k != 'ten_year_alert'} | set(cfg['sectors'].values()) | set(cfg['mag7'])
    for lst in cfg['sector_candidates'].values():
        t |= set(lst)
    for th in cfg['themes'].values():
        t |= set(th.get('etfs', [])) | set(th.get('tickers', []))
    t |= set(cfg.get('concentration_watch', {}).get('tickers', [])) | {cfg.get('concentration_watch', {}).get('benchmark', 'SMH')}
    t |= {c['ticker'] for c in cfg.get('consumer_watch', [])} | {c['vs'] for c in cfg.get('consumer_watch', []) if c.get('vs')}
    for c in cfg.get('catalysts', []):
        t |= set(c.get('primary', [])) | set(c.get('second_order_up', [])) | set(c.get('second_order_down', []))
    cr = cfg.get('crypto', {})
    t |= set(cr.get('coins', {}).values()) | set(cr.get('metals', {}).values()) | {x for l in cr.get('related', {}).values() for x in l}
    ex = cfg.get('extras', {})
    t |= set(ex.get('also_watch', [])) | {a['ticker'] for a in ex.get('app_watch', [])}
    t.discard(None); t.discard('ten_year_alert')
    return sorted(x for x in t if isinstance(x, str))


def download(tickers, period='5y'):   # 5 years: the weekly 200-SMA needs ~4 years
    import yfinance as yf
    closes, vols, typ = {}, {}, {}
    for i in range(0, len(tickers), 80):          # batches keep Yahoo happy
        chunk = tickers[i:i + 80]
        raw = yf.download(chunk, period=period, auto_adjust=True, group_by='ticker', progress=False, threads=True)
        for t in chunk:
            try:
                x = raw[t] if len(chunk) > 1 else raw
                x = x.dropna(subset=['Close'])
                if len(x):
                    closes[t] = x['Close']; vols[t] = x['Volume']; typ[t] = (x['High'] + x['Low'] + x['Close']) / 3
            except Exception:
                pass
        time.sleep(1)
    download.typical = pd.DataFrame(typ)   # (high+low+close)/3, what TradingView's VWAP uses
    return pd.DataFrame(closes), pd.DataFrame(vols)


def market_caps(tickers):
    import yfinance as yf
    out = {}
    for t in tickers:
        try:
            mc = yf.Ticker(t).fast_info.get('marketCap')
            if mc:
                out[t] = float(mc)
        except Exception:
            pass
    return out


def short_interest(tickers):
    """Short % of float + market cap for the consumer watch list (small list, so the slow .info call is fine)."""
    import yfinance as yf
    out = {}
    for t in tickers:
        try:
            i = yf.Ticker(t).info
            out[t] = dict(short_pct_float=i.get('shortPercentOfFloat'), mcap=i.get('marketCap'), name=i.get('shortName'))
        except Exception:
            pass
    return out


def main():
    cfg = load_config()
    tick = all_tickers(cfg)
    px, vol = download(tick)
    missing = [t for t in tick if t not in px.columns]
    d = day_dir()
    px.to_csv(d / 'prices.csv'); vol.to_csv(d / 'volumes.csv'); getattr(download, 'typical', pd.DataFrame()).to_csv(d / 'typical.csv')
    stocks = sorted({s for lst in cfg['sector_candidates'].values() for s in lst} |
                    {s for th in cfg['themes'].values() for s in th.get('tickers', [])} | set(cfg['mag7']))
    save_json(market_caps(stocks), 'market_caps.json')
    save_json(short_interest(sorted({c['ticker'] for c in cfg.get('consumer_watch', [])})), 'consumer_info.json')
    save_json({'n_tickers': len(tick), 'got': px.shape[1], 'missing': missing, 'last_bar': str(px.index.max())}, 'market_meta.json')
    print(f'prices: {px.shape}, missing {len(missing)}: {missing[:20]}')


if __name__ == '__main__':
    sys.exit(main())
