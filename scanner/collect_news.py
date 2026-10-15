"""Headlines from public RSS feeds; tagged by theme keyword. Output: data/<date>/news.json"""
import sys, re
from common import load_config, save_json, today


def main():
    cfg = load_config()
    import feedparser
    items, errors = [], []
    for url in cfg['news_rss']:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:60]:
                items.append(dict(title=e.get('title', ''), link=e.get('link', ''), published=e.get('published', ''), source=url.split('/')[2]))
        except Exception as ex:
            errors.append(f'{url}: {ex}')
    tagged = {}
    for name, th in cfg['themes'].items():
        pats = [re.compile(r'\b' + re.escape(k.lower()) + r'\b') for k in th['keywords']]
        tagged[name] = [i for i in items if any(p.search(i['title'].lower()) for p in pats)][:8]
    narr = {}
    for key, nv in cfg.get('narratives', {}).items():
        pats = [re.compile(r'\b' + re.escape(ph) + r'\b') for ph in nv['phrases']]
        hit = [i for i in items if any(p.search(i['title'].lower()) for p in pats)]
        narr[key] = dict(count=len(hit), examples=hit[:4])
    if items:
        from common import append_history
        append_history('narratives_news', {'date': today(), 'n_posts': len(items), **{k: v['count'] for k, v in narr.items()}})
    save_json(dict(date=today(), n=len(items), errors=errors, by_theme=tagged, latest=items[:60], narratives=narr), 'news.json')
    print(f'news: {len(items)} headlines')


if __name__ == '__main__':
    sys.exit(main())
