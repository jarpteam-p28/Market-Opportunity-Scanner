"""Optional X (Twitter) read through xAI's Grok API with its X Search tool. Needs secret XAI_API_KEY and
config x_grok.enabled: true. Paid per use (about $5 per 1,000 posts fetched as of Sept 2026 — check console.x.ai).
Grok is asked for counts, tone and LINKS to real posts so its summary can be checked."""
import os, sys, json
import requests
from common import load_config, save_json, today

PROMPT = ("Search X posts from the last 7 days about: {q}. Return JSON only with keys: "
          "'volume' (low/medium/high vs the prior month), 'tone' (-1 to 1), 'top_tickers' (list of [ticker, mentions]), "
          "'key_claims' (3 short bullet strings), 'post_links' (up to 5 URLs of the most-engaged real posts).")


def main():
    cfg = load_config(); xc = cfg['x_grok']; key = os.environ.get('XAI_API_KEY')
    if not (xc.get('enabled') and key):
        print('x/grok: skipped (disabled or no XAI_API_KEY)'); return
    out = {'date': today(), 'themes': {}, 'errors': []}
    for theme in list(cfg['themes'])[:xc['max_queries']]:
        q = theme + ' stocks (' + ', '.join(cfg['themes'][theme]['keywords'][:3]) + ')'
        try:
            r = requests.post('https://api.x.ai/v1/responses', timeout=120,
                              headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                              json={'model': xc['model'], 'tools': [{'type': 'x_search'}],
                                    'input': [{'role': 'user', 'content': PROMPT.format(q=q)}]})
            r.raise_for_status(); j = r.json()
            txt = ''.join(c.get('text', '') for o in j.get('output', []) if o.get('type') == 'message' for c in o.get('content', []))
            try:
                out['themes'][theme] = json.loads(txt[txt.find('{'): txt.rfind('}') + 1])
            except Exception:
                out['themes'][theme] = {'raw': txt[:2000]}
        except Exception as e:
            out['errors'].append(f'{theme}: {e}')
    save_json(out, 'x_grok.json')
    print(f"x/grok: {len(out['themes'])} themes, {len(out['errors'])} errors")


if __name__ == '__main__':
    sys.exit(main())
