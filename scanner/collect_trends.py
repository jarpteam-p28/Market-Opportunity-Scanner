"""Google Trends interest for each theme's search terms (unofficial pytrends; can be rate-limited — fails soft).
Output: data/<date>/trends.json — per term: last-week average vs the prior 4 weeks (0-100 scale)."""
import sys, time
from common import load_config, save_json, today


def main():
    cfg = load_config(); gt = cfg['google_trends']
    if not gt.get('enabled'):
        return
    out = {'date': today(), 'terms': {}, 'consumer': {}, 'errors': []}
    try:
        from pytrends.request import TrendReq
        py = TrendReq(hl='en-US', tz=300, timeout=(10, 30), retries=2, backoff_factor=1)
    except Exception as e:
        out['errors'].append(f'pytrends unavailable: {e}'); save_json(out, 'trends.json'); return
    for theme, th in cfg['themes'].items():
        for term in th.get('trends', []):
            try:
                py.build_payload([term], timeframe=gt['timeframe'], geo=gt['geo'])
                s = py.interest_over_time()[term]
                last = float(s.iloc[-7:].mean()); prior = float(s.iloc[-35:-7].mean())
                out['terms'][term] = dict(theme=theme, last_week=last, prior_4w=prior,
                                          change=(last / prior - 1) if prior else None, peak_3m=float(s.max()))
            except Exception as e:
                out['errors'].append(f'{term}: {e}')
            time.sleep(4)
    for c in cfg.get('consumer_watch', []):
        term = c['term']
        try:
            py.build_payload([term], timeframe='today 12-m', geo=gt['geo'])
            s = py.interest_over_time()[term]
            last = float(s.iloc[-4:].mean()); prior = float(s.iloc[-16:-4].mean()); year = float(s.mean())
            out['consumer'][term] = dict(ticker=c['ticker'], last_4w=last, prior_12w=prior, year_avg=year,
                                         change=(last / prior - 1) if prior else None, at_12m_high=bool(s.iloc[-4:].max() >= s.max()))
        except Exception as e:
            out['errors'].append(f'{term}: {e}')
        time.sleep(4)
    save_json(out, 'trends.json')
    print(f"trends: {len(out['terms'])} terms, {len(out['errors'])} errors")


if __name__ == '__main__':
    sys.exit(main())
