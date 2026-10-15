"""Optional: comment 'buzz' for each consumer-watch term from YouTube (official YouTube Data API, free daily quota).
Camillo's edge is reading comments (mostly TikTok, which has no open API). YouTube comments are the closest legal,
automatable stand-in. Secret: YOUTUBE_API_KEY. Uses ~2-3k of the 10k free daily quota units.
Per term: recent videos (last 30 days), their views, and ~100 top comments each -> buying-intent and scare-word counts."""
import os, sys, re, datetime as dt
import requests
from common import load_config, save_json, append_history, today

API = 'https://www.googleapis.com/youtube/v3/'
INTENT = ['need this', 'need it', 'want this', 'want one', 'buying', 'bought', 'ordered', 'sold out', 'obsessed', 'where can i get',
          'where do i get', 'take my money', 'add to cart', 'restock', 'line', 'waited', 'just got mine', 'love mine']
SCARE = ['recall', 'lawsuit', 'toxic', 'cancer', 'arsenic', 'cyanide', 'banned', 'boycott', 'scam', 'fake', 'poison', 'contaminated',
         'sick', 'lead in', 'microplastics', 'satanic', 'cursed']


def get(ep, key, **p):
    r = requests.get(API + ep, params={**p, 'key': key}, timeout=30); r.raise_for_status(); return r.json()


def main():
    key = os.environ.get('YOUTUBE_API_KEY'); cfg = load_config()
    if not key:
        print('youtube: skipped (no YOUTUBE_API_KEY)'); return
    since = (dt.datetime.utcnow() - dt.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    out = {'date': today(), 'terms': {}, 'errors': []}; hist = {'date': today()}
    for c in cfg.get('consumer_watch', []):
        term = c['term']
        try:
            s = get('search', key, part='snippet', q=term, type='video', order='relevance', publishedAfter=since, maxResults=5, regionCode='US')
            ids = [i['id']['videoId'] for i in s.get('items', [])]
            views = 0; n = 0; intent = 0; scare = 0; examples = []
            if ids:
                v = get('videos', key, part='statistics', id=','.join(ids))
                views = sum(int(i['statistics'].get('viewCount', 0)) for i in v.get('items', []))
            for vid in ids:
                try:
                    cm = get('commentThreads', key, part='snippet', videoId=vid, maxResults=100, order='relevance', textFormat='plainText')
                except Exception:
                    continue
                for it in cm.get('items', []):
                    t = it['snippet']['topLevelComment']['snippet']['textDisplay'].lower(); n += 1
                    hi = any(w in t for w in INTENT); hs = any(re.search(r'\b' + re.escape(w) + r'\b', t) for w in SCARE)
                    intent += hi; scare += hs
                    if (hi or hs) and len(examples) < 3:
                        examples.append(t[:160])
            out['terms'][term] = dict(ticker=c['ticker'], videos=len(ids), views_30d_top5=views, comments_read=n,
                                      intent_per_100=round(100 * intent / n, 1) if n else None, scare_per_100=round(100 * scare / n, 1) if n else None,
                                      examples=examples)
            hist[term + '|views'] = views; hist[term + '|intent'] = intent; hist[term + '|scare'] = scare; hist[term + '|n'] = n
        except Exception as e:
            out['errors'].append(f'{term}: {e}')
    save_json(out, 'youtube.json'); append_history('youtube_terms', hist)
    print(f"youtube: {len(out['terms'])} terms, {len(out['errors'])} errors")


if __name__ == '__main__':
    sys.exit(main())
