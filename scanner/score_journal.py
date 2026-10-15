"""Score past watch-list ideas: return after ~1, 3 and 6 months vs SPY, from the latest prices file.
Output: journal/scored.csv. This is the honest test of whether the agents add anything."""
import sys
import pandas as pd
from common import ROOT, DATA, load_config

def main():
    cfg = load_config(); j = ROOT / 'journal' / 'theses.csv'
    if not j.exists():
        print('no journal yet'); return
    days = sorted(p for p in DATA.iterdir() if p.is_dir() and (p / 'prices.csv').exists())
    if not days:
        return
    px = pd.read_csv(days[-1] / 'prices.csv', index_col=0, parse_dates=True); spy = px[cfg['regime']['index']]
    T = pd.read_csv(j, parse_dates=['date']); out = []
    for _, r in T.iterrows():
        row = r.to_dict()
        if r.ticker in px and pd.notna(r.price):
            s = px[r.ticker].dropna()
            for lab, n in (('1m', 21), ('3m', 63), ('6m', 126)):
                after = s[s.index > r.date]; sa = spy[spy.index > r.date].dropna()
                if len(after) >= n and len(sa) >= n:
                    row[f'ret_{lab}'] = round(after.iloc[n - 1] / r.price - 1, 4)
                    row[f'spy_{lab}'] = round(sa.iloc[n - 1] / r.spy - 1, 4)
                    row[f'excess_{lab}'] = round(row[f'ret_{lab}'] - row[f'spy_{lab}'], 4)
        out.append(row)
    pd.DataFrame(out).to_csv(ROOT / 'journal' / 'scored.csv', index=False)
    print('scored', len(out))

if __name__ == '__main__':
    sys.exit(main())
