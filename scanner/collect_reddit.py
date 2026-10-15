"""Reddit buzz: theme keyword counts and $TICKER mentions across configured subreddits.
Uses Reddit's official API (free personal 'script' app). Secrets: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET.
Output: data/<date>/reddit.json and a row in data/history/reddit_themes.csv (for week-over-week change)."""
import os, re, sys, time, collections
import requests
from common import load_config, save_json, append_history, today

UA = 'market-opportunity-scanner/0.1 (personal research)'
STOP = {'A', 'I', 'IT', 'ON', 'FOR', 'ALL', 'ARE', 'CEO', 'DD', 'YOLO', 'USA', 'US', 'AI', 'EPS', 'ATH', 'IMO', 'FYI', 'ETF', 'GDP',
        'CPI', 'FED', 'SEC', 'IPO', 'OTM', 'ITM', 'PE', 'EV', 'TA', 'OP', 'EDIT', 'TLDR', 'LOL', 'NEW', 'BUY', 'SELL', 'HOLD', 'NOW'}


def token():
    cid, sec = os.environ.get('REDDIT_CLIENT_ID'), os.environ.get('REDDIT_CLIENT_SECRET')
    if not (cid and sec):
        return None
    r = requests.post('https://www.reddit.com/api/v1/access_token', auth=(cid, sec),
                      data={'grant_type': 'client_credentials'}, headers={'User-Agent': UA}, timeout=20)
    r.raise_for_status()
    return r.json()['access_token']


def fetch(sub, tok, listing, limit):
    if tok:
        url, h = f'https://oauth.reddit.com/r/{sub}/{listing}', {'Authorization': f'bearer {tok}', 'User-Agent': UA}
    else:   # public fallback, often blocked from cloud servers
        url, h = f'https://www.reddit.com/r/{sub}/{listing}.json', {'User-Agent': UA}
    r = requests.get(url, headers=h, params={'limit': limit}, timeout=20)
    r.raise_for_status()
    return [c['data'] for c in r.json()['data']['children']]


def main():
    cfg = load_config(); rc = cfg['reddit']
    known = {s for lst in cfg['sector_candidates'].values() for s in lst} | {s for th in cfg['themes'].values() for s in th['tickers']} | set(cfg['mag7'])
    try:
        tok = token()
    except Exception as e:
        print('reddit auth failed:', e); tok = None
    posts, errors = [], []
    for sub in rc['subreddits'] + rc.get('ground_truth_subreddits', []):
        for listing in ('hot', 'new'):
            try:
                posts += [dict(sub=sub, title=p.get('title', ''), text=p.get('selftext', '')[:3000], score=p.get('score', 0),
                               comments=p.get('num_comments', 0), url='https://reddit.com' + p.get('permalink', ''))
                          for p in fetch(sub, tok, listing, rc['posts_per_sub'])]
            except Exception as e:
                errors.append(f'{sub}/{listing}: {e}')
            time.sleep(1)
    seen = set(); uniq = []
    for p in posts:
        if p['url'] not in seen:
            seen.add(p['url']); uniq.append(p)
    gt_only = set(rc.get('ground_truth_subreddits', []))
    inv = [p for p in uniq if p['sub'] not in gt_only]
    theme_counts, theme_top = {}, {}
    for name, th in cfg['themes'].items():
        pats = [re.compile(r'\b' + re.escape(k.lower()) + r'\b') for k in th['keywords']] + \
               [re.compile(r'\$?\b' + re.escape(t.lower()) + r'\b') for t in th['tickers'] if len(t) > 2]
        hits = [p for p in inv if any(pt.search((p['title'] + ' ' + p['text']).lower()) for pt in pats)]
        theme_counts[name] = len(hits)
        theme_top[name] = [dict(title=h['title'], sub=h['sub'], score=h['score'], url=h['url'])
                           for h in sorted(hits, key=lambda x: -x['score'])[:3]]
    # narrative meters (all subs) + ground-truth subs separately
    gt_subs = set(rc.get('ground_truth_subreddits', []))
    narr = {}
    for key, nv in cfg.get('narratives', {}).items():
        pats = [re.compile(r'\b' + re.escape(ph) + r'\b') for ph in nv['phrases']]
        hit = [p for p in uniq if any(pt.search((p['title'] + ' ' + p['text']).lower()) for pt in pats)]
        narr[key] = dict(all=len(hit), ground_truth=sum(p['sub'] in gt_subs for p in hit),
                         examples=[dict(title=h['title'][:140], sub=h['sub'], url=h['url']) for h in sorted(hit, key=lambda x: -x['score'])[:3]])
    tick = collections.Counter()
    for p in inv:
        txt = p['title'] + ' ' + p['text']
        found = set(re.findall(r'\$([A-Z]{1,5})\b', txt)) | {w for w in re.findall(r'\b([A-Z]{2,5})\b', txt) if w in known}
        for t in found - STOP:
            tick[t] += 1
    top_tickers = [(t, n) for t, n in tick.most_common(40) if n >= rc['min_ticker_mentions']]
    out = dict(date=today(), authed=bool(tok), n_posts=len(uniq), errors=errors, theme_counts=theme_counts,
               theme_top_posts=theme_top, top_tickers=top_tickers, narratives=narr,
               n_ground_truth_posts=sum(p['sub'] in gt_subs for p in uniq))
    save_json(out, 'reddit.json')
    if uniq:
        append_history('reddit_themes', {'date': today(), 'n_posts': len(inv), **theme_counts})
        append_history('narratives_reddit', {'date': today(), 'n_posts': len(uniq), **{k: v['all'] for k, v in narr.items()}})
        append_history('reddit_tickers', {'date': today(), **dict(tick.most_common(150))})
    print(f'reddit: {len(uniq)} posts, authed={bool(tok)}, errors={len(errors)}')


if __name__ == '__main__':
    sys.exit(main())
