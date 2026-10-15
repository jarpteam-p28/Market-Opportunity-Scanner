"""Offline smoke test: fake prices/caps/reddit/trends for all configured tickers, then analyze + report."""
import os, sys, json, pathlib, numpy as np, pandas as pd
ROOT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / 'scanner'))
os.environ['SCAN_DATE'] = '2099-01-09'
import common
from collect_market import all_tickers
cfg = common.load_config(); rng = np.random.default_rng(1)
tick = all_tickers(cfg); idx = pd.bdate_range(end='2099-01-09', periods=260)
px = pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0.0005, 0.02, len(idx))) for t in tick}, index=idx)
d = common.day_dir(); px.to_csv(d / 'prices.csv')
common.save_json({t: float(rng.uniform(5e10, 4e12)) for t in tick}, 'market_caps.json')
for k, date in enumerate(['2099-01-01', '2098-12-25', '2098-12-18', '2099-01-09']):
    common.append_history('reddit_themes', {'date': date, 'n_posts': 800, **{th: int(rng.integers(5, 60)) for th in cfg['themes']}})
common.save_json({'n_posts': 800, 'theme_top_posts': {'Water': [{'title': 'Data centers are draining water', 'url': 'https://reddit.com/x', 'score': 900, 'sub': 'stocks'}]},
                  'top_tickers': [['NVDA', 40], ['OKLO', 22], ['VST', 9]]}, 'reddit.json')
common.save_json({'terms': {'uranium': {'theme': 'Nuclear', 'change': 0.35}}}, 'trends.json')
import analyze, report
analyze.main(); report.main()
print(open(ROOT / 'reports' / 'latest.md').read()[:3500])
