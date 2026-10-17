"""Balance-sheet and popularity data for the Wealth Builder scan (Oliver Velez style): cash vs debt, free cash flow,
revenue growth, institutional ownership, analyst ratings. Yahoo Finance via yfinance, free. Only fetched for names that are
already beaten down on the monthly or weekly chart (plus your wealth watch list), to keep the run short. Fails soft.
Output: data/<date>/fundamentals.json"""
import sys, time
import pandas as pd
from common import load_config, save_json, day_dir, today

FIELDS = ['shortName', 'marketCap', 'totalCash', 'totalDebt', 'freeCashflow', 'operatingCashflow', 'revenueGrowth',
          'heldPercentInstitutions', 'recommendationMean', 'numberOfAnalystOpinions', 'sector', 'industry']


def beaten_down(px, mn=20, wn=200):
    out = []
    for t in px.columns:
        s = px[t].dropna()
        if len(s) < 300 or '-' in t or '=' in t or '^' in t:
            continue
        m = s.resample('ME').last(); w = s.resample('W-FRI').last(); p = s.iloc[-1]
        if (len(m) >= mn and p < m.iloc[-mn:].mean()) or (len(w) >= wn and p < w.iloc[-wn:].mean()):
            out.append(t)
    return out


def main():
    cfg = load_config(); wb = cfg.get('setups', {}).get('wealth_builder', {})
    if not wb.get('enabled', True):
        return
    out = {'date': today(), 'names': {}, 'errors': []}
    try:
        px = pd.read_csv(day_dir() / 'prices.csv', index_col=0, parse_dates=True).sort_index()
        names = list(dict.fromkeys(wb.get('watch', []) + beaten_down(px, cfg['setups'].get('monthly_sma', 20), cfg['setups'].get('weekly_sma', 200))))
    except Exception as e:
        out['errors'].append(f'prices: {e}'); names = list(wb.get('watch', []))
    names = names[:wb.get('max_fetch', 150)]
    try:
        import yfinance as yf
        for t in names:
            try:
                i = yf.Ticker(t).info or {}
                out['names'][t] = {k: i.get(k) for k in FIELDS}
            except Exception as e:
                out['errors'].append(f'{t}: {e}')
            time.sleep(0.25)
    except Exception as e:
        out['errors'].append(f'yfinance: {e}')
    save_json(out, 'fundamentals.json')
    print(f"fundamentals: {len(out['names'])} names, {len(out['errors'])} errors")


if __name__ == '__main__':
    sys.exit(main())
