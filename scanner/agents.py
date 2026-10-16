"""Research agents: each agent prompt in agents/<name>.md reads the day's data from its own angle; the synthesizer
combines them into a thesis + watch list. Runs only if ANTHROPIC_API_KEY is set (GitHub secret).
Output: data/<date>/agents.json, and the synthesizer's watch list is appended to journal/theses.csv for scoring."""
import os, sys, json, re
import requests
import pandas as pd
from common import ROOT, load_config, load_json, save_json, day_dir, today

API = 'https://api.anthropic.com/v1/messages'


def call(prompt, cfg, key):
    r = requests.post(API, timeout=300, headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
                      json={'model': cfg['agents']['model'], 'max_tokens': cfg['agents']['max_tokens'],
                            'messages': [{'role': 'user', 'content': prompt}]})
    r.raise_for_status()
    j = r.json(); txt = ''.join(c.get('text', '') for c in j.get('content', []) if c.get('type') == 'text')
    if not txt.strip():
        raise RuntimeError(f"empty reply (stop_reason={j.get('stop_reason')})")
    return txt


def context_for(name, A, extra):
    """Give each agent only the slice it needs (keeps cost down and the agents focused)."""
    slim_themes = [{k: v for k, v in t.items() if k != 'top_posts'} for t in A['themes']]
    pick = {
        'regime': {'regime': A['regime'], 'breadth': A['breadth'], 'mag7': A['mag7'], 'ai_concentration_watch': A.get('concentration')},
        'sectors': {'sectors': A['sectors'], 'top10': A['top10'], 'breadth': A['breadth']},
        'sentiment': {'themes': A['themes'], 'reddit_tickers': A['reddit_tickers'], 'rising_tickers': A.get('rising_tickers'), 'consumer_search_watch': A.get('consumer'), 'narratives': A.get('narratives'), 'big_movers': A.get('big_movers'), 'x': extra.get('x'), 'trends': extra.get('trends'),
                      'news': (extra.get('news') or {}).get('by_theme')},
        'themes': {'themes': slim_themes, 'sectors': A['sectors'], 'catalysts': A.get('catalysts'), 'news': (extra.get('news') or {}).get('by_theme')},
        'social_arb': {'regime': A['regime']['label'], 'consumer_search_watch': A.get('consumer'), 'rising_tickers': A.get('rising_tickers'),
                       'discovery': A.get('discovery'), 'narratives': A.get('narratives'), 'catalysts': A.get('catalysts'), 'big_movers': A.get('big_movers'),
                       'themes': [t for t in slim_themes if t['label'].startswith(('EARLY', 'STEALTH', 'CONFIRMED'))],
                       'headlines': [h['title'] for h in (extra.get('news') or {}).get('latest', [])[:40]]},
        'skeptic': {'regime': A['regime'], 'mag7': A['mag7'], 'themes': slim_themes, 'ai_concentration_watch': A.get('concentration'), 'narratives': A.get('narratives')},
        'regime_extra': None,
    }
    return json.dumps(pick.get(name, A), default=str)[:60000]


def main():
    cfg = load_config(); key = os.environ.get('ANTHROPIC_API_KEY')
    if not (cfg['agents'].get('enabled') and key):
        print('agents: skipped (disabled or no ANTHROPIC_API_KEY) — the data report still runs'); return
    A = load_json('analysis.json')
    extra = {'news': load_json('news.json'), 'trends': load_json('trends.json'), 'x': load_json('x_grok.json')}
    playbook = ''.join(p.read_text()[:8000] + '\n\n' for p in sorted((ROOT / 'playbook').glob('*.md')))
    outs = {}
    for name in cfg['agents']['order']:
        tmpl = (ROOT / 'agents' / f'{name}.md').read_text()
        if name == 'synthesizer':
            ctx = json.dumps({'agent_reports': outs, 'regime': A['regime']['label'], 'date': A['date']})
        else:
            ctx = context_for(name, A, extra)
        if name != 'synthesizer':
            tmpl = tmpl.replace('{{PLAYBOOK}}', '{{PLAYBOOK}}') if '{{PLAYBOOK}}' in tmpl else tmpl + '\n\nUser playbook notes (context, not data):\n{{PLAYBOOK}}'
        prompt = tmpl.replace('{{DATE}}', A['date']).replace('{{PLAYBOOK}}', playbook).replace('{{DATA}}', ctx)
        for attempt in (1, 2):   # one retry: an empty or failed reply shouldn't leave a hole in the report
            try:
                outs[name] = call(prompt, cfg, key); break
            except Exception as e:
                outs[name] = f'(agent failed: {e})'
        print(f'agent {name}: {len(outs[name])} chars')
    save_json(outs, 'agents.json')
    # watch list -> journal for later scoring
    m = re.search(r'```json\s*(\{.*?\})\s*```', outs.get('synthesizer', ''), re.S)
    if m:
        try:
            wl = json.loads(m.group(1)).get('watchlist', [])
            px = pd.read_csv(day_dir() / 'prices.csv', index_col=0, parse_dates=True)
            rows = [dict(date=today(), ticker=w.get('ticker'), theme=w.get('theme'), stance=w.get('stance'), conviction=w.get('conviction'), thesis_breaker=(w.get('thesis_breaker') or '')[:200],
                         idea=w.get('why', '')[:300], price=round(float(px[w['ticker']].dropna().iloc[-1]), 2) if w.get('ticker') in px else None,
                         spy=round(float(px[cfg['regime']['index']].dropna().iloc[-1]), 2)) for w in wl]
            j = ROOT / 'journal' / 'theses.csv'; j.parent.mkdir(exist_ok=True)
            old = pd.read_csv(j) if j.exists() else pd.DataFrame()
            if len(old):
                old = old[old.date != today()]
            pd.concat([old, pd.DataFrame(rows)], ignore_index=True).to_csv(j, index=False)
        except Exception as e:
            print('watchlist parse failed:', e)


if __name__ == '__main__':
    sys.exit(main())
