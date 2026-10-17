"""Extra evidence for the names we care about (watchlist + consumer + AI concentration + catalysts + Mag 7):
earnings dates, insider buying, options activity (Yahoo Finance via yfinance), and Apple App Store top-chart ranks.
All free, no keys. Every piece fails soft. Output: data/<date>/extras.json"""
import sys, time
import pandas as pd
import requests
from common import ROOT, load_config, save_json, append_history, today


def focus_list(cfg):
    ex = cfg.get('extras', {}); names = []
    j = ROOT / 'journal' / 'theses.csv'
    if j.exists():
        try:
            t = pd.read_csv(j); names += list(t[t.date == t.date.max()].ticker.dropna())
        except Exception:
            pass
    names += cfg.get('concentration_watch', {}).get('tickers', []) + cfg.get('mag7', [])
    names += [c['ticker'] for c in cfg.get('consumer_watch', [])]
    for c in cfg.get('catalysts', []):
        names += c.get('primary', []) + c.get('second_order_up', [])
    names += ex.get('also_watch', [])
    out = []
    for n in names:   # US-listed only (options/insider data), keep order, no duplicates
        if isinstance(n, str) and n and '.' not in n and n not in out:
            out.append(n)
    return out[:ex.get('max_names', 70)]


def earnings(tk):
    try:
        cal = tk.calendar
        d = (cal or {}).get('Earnings Date') if isinstance(cal, dict) else None
        if d:
            return str(pd.Timestamp(d[0] if isinstance(d, (list, tuple)) else d).date())
    except Exception:
        pass
    try:
        ed = tk.get_earnings_dates(limit=6)
        fut = [i for i in ed.index if i.tz_localize(None) >= pd.Timestamp.now().normalize()]
        return str(min(fut).date()) if fut else None
    except Exception:
        return None


def insiders(tk, days):
    try:
        df = tk.insider_transactions
        if df is None or not len(df):
            return None
        col = 'Start Date' if 'Start Date' in df else df.columns[0]
        df = df[pd.to_datetime(df[col], errors='coerce') >= pd.Timestamp.now() - pd.Timedelta(days=days)]
        txt = df.get('Text', pd.Series('', index=df.index)).fillna('').str.lower()
        buys, sells = df[txt.str.contains('purchase')], df[txt.str.contains('sale')]
        val = lambda d: float(pd.to_numeric(d.get('Value'), errors='coerce').fillna(0).sum()) if len(d) else 0.0
        return dict(buys=len(buys), buy_value=round(val(buys)), sells=len(sells), sell_value=round(val(sells)),
                    buyers=sorted({f"{r.get('Insider', '')} ({r.get('Position', '')})".strip() for _, r in buys.iterrows()})[:4])
    except Exception:
        return None


def options(tk, n_exp=2, min_vol=500):
    try:
        exps = tk.options[:n_exp]
        if not exps:
            return None
        cv = pv = coi = poi = 0; hot = []
        for e in exps:
            ch = tk.option_chain(e)
            for side, df in (('call', ch.calls), ('put', ch.puts)):
                v = df['volume'].fillna(0); oi = df['openInterest'].fillna(0)
                if side == 'call':
                    cv += v.sum(); coi += oi.sum()
                else:
                    pv += v.sum(); poi += oi.sum()
                spikes = df[(v >= min_vol) & (v > 3 * oi.clip(lower=1))]   # far more traded today than were open: new positioning
                hot += [dict(side=side, exp=e, strike=float(r.strike), volume=int(r.volume), oi=int(r.openInterest or 0)) for _, r in spikes.iterrows()]
        hot = sorted(hot, key=lambda h: -h['volume'])[:3]
        return dict(call_vol=int(cv), put_vol=int(pv), put_call=round(pv / cv, 2) if cv else None,
                    vol_vs_oi=round((cv + pv) / (coi + poi), 2) if (coi + poi) else None, unusual=hot)
    except Exception:
        return None


def app_ranks(cfg):
    watch = cfg.get('extras', {}).get('app_watch', [])
    out = {'charts': {}, 'errors': []}
    for chart in ('top-free', 'top-paid'):
        try:
            r = requests.get(f'https://rss.applemarketingtools.com/api/v2/us/apps/{chart}/100/apps.json', timeout=20)
            r.raise_for_status()
            res = r.json()['feed']['results']
            for w in watch:
                for i, a in enumerate(res, 1):
                    if w['app'].lower() in a.get('name', '').lower():
                        out['charts'].setdefault(w['app'], dict(ticker=w['ticker']))[chart] = i; break
        except Exception as e:
            out['errors'].append(f'{chart}: {e}')
    if out['charts']:
        append_history('app_ranks', {'date': today(), **{k: v.get('top-free') for k, v in out['charts'].items()}})
    return out


def main():
    cfg = load_config(); ex = cfg.get('extras', {})
    if not ex.get('enabled', True):
        return
    out = {'date': today(), 'names': {}, 'errors': []}
    try:
        import yfinance as yf
        for t in focus_list(cfg):
            tk = yf.Ticker(t); row = {}
            if ex.get('earnings', True):
                row['next_earnings'] = earnings(tk)
            if ex.get('insiders', True):
                row['insiders_90d'] = insiders(tk, ex.get('insider_days', 90))
            if ex.get('options', True):
                row['options'] = options(tk)
            out['names'][t] = row
            time.sleep(0.3)
    except Exception as e:
        out['errors'].append(f'yfinance: {e}')
    out['apps'] = app_ranks(cfg) if ex.get('app_ranks', True) else {}
    save_json(out, 'extras.json')
    print(f"extras: {len(out['names'])} names, apps found {len(out['apps'].get('charts', {}))}, errors {len(out['errors'])}")


if __name__ == '__main__':
    sys.exit(main())
