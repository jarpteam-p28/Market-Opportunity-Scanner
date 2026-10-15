"""Write the readable report: reports/<date>.md (+ reports/latest.md) and a short Telegram summary."""
import sys
from common import REPORTS, load_config, load_json, telegram, today


def yn(b):
    return '✅' if b else ('❌' if b is not None else '–')


def f(x, suffix='%'):
    return '–' if x is None else f'{x:+.1f}{suffix}'


def build(A, agents, cfg):
    R = A['regime']; M = A['mag7']; L = []
    L += [f"# {cfg['report']['title']} — {A['date']}", f"_Data through {A['last_bar']}. Research only, not investment advice._", '']
    if agents and agents.get('synthesizer'):
        L += ['## Thesis (agents)', agents['synthesizer'].split('```json')[0].strip(), '']
    L += ['## 1. Where are we? Market regime', f"**{R['label']}** (score {R['score_0_4']}/4)", '',
          '| | Last | 1 wk | 1 mo | 3 mo | YTD | >50d | >200d |', '|---|---|---|---|---|---|---|---|',
          f"| S&P 500 (SPY) | {R['spy']['last']} | {f(R['spy']['w'])} | {f(R['spy']['m'])} | {f(R['spy']['q'])} | {f(R['spy']['ytd'])} | {yn(R['spy']['above50'])} | {yn(R['spy']['above200'])} |", '']
    L += [f"- VIX {R.get('vix', {}).get('last', '–')} · 10-yr yield {R.get('ten_year', {}).get('last', '–')} · dollar 1-mo {f(R.get('dollar', {}).get('m_change'))}",
          f"- Equal-weight vs S&P (1 mo): {f(R['equal_vs_cap_1m'])} · small caps vs S&P: {f(R['small_vs_large_1m'])} · credit appetite (HYG/IEF): {f(R['credit_appetite_1m'])}",
          ("- ⚠️ **10-year yield at/above the 5% danger line**" if R.get('ten_year_alert') else "- 10-year yield below the 5% danger line"),
          f"- Breadth: {A['breadth']['pct_top10s_above_50d']}% of sector top-10 names above their 50-day, {A['breadth']['pct_top10s_above_200d']}% above 200-day", '']
    L += ['## 2. Is it only the Magnificent 7?', f"**{M['read']}**", '', '| | 1 wk | 1 mo | 3 mo | YTD |', '|---|---|---|---|---|',
          f"| Mag 7 (equal weight) | {f(M['mag7_w'])} | {f(M['mag7_m'])} | {f(M['mag7_q'])} | {f(M['mag7_ytd'])} |",
          f"| S&P 500 | {f(M['spy_w'])} | {f(M['spy_m'])} | {f(M['spy_q'])} | {f(M['spy_ytd'])} |",
          f"| Average stock (RSP) | {f(M['equal_weight_w'])} | {f(M['equal_weight_m'])} | {f(M['equal_weight_q'])} | {f(M['equal_weight_ytd'])} |", '',
          'Each: ' + ' · '.join(f"{t} {f(v['m'])} (1 mo)" for t, v in M['each'].items()),
          f"Mag 7 = {M['mag7_share_of_tracked_mcap']}% of the market cap of all tracked large caps.", '']
    L += ['## 3. Sector rotation (vs S&P, last month)', '| Rank | Sector | 1 wk | 1 mo | 3 mo | vs S&P 1 mo | Rank change vs last week | >50d | >200d |',
          '|---|---|---|---|---|---|---|---|---|']
    for s in A['sectors']:
        arrow = f"▲{s['rank_change']}" if s['rank_change'] > 0 else (f"▼{-s['rank_change']}" if s['rank_change'] < 0 else '=')
        L.append(f"| {s['rank_now']} | {s['sector']} ({s['etf']}) | {f(s['w'])} | {f(s['m'])} | {f(s['q'])} | {f(s['rs_m_now'])} | {arrow} | {yn(s['above50'])} | {yn(s['above200'])} |")
    L += ['', '## 4. Talk vs. tape: themes', '| Theme | 1 mo | 3 mo | vs S&P 1 mo | Reddit talk change | Google Trends change | X | Read |', '|---|---|---|---|---|---|---|---|']
    for t in A['themes']:
        L.append(f"| {t['theme']} | {f(t['m'])} | {f(t['q'])} | {f(t['rs_vs_spy_m'])} | {f(t['reddit_change'])} | {f(t['google_trends_change'])} | {t['x_volume'] or '–'} | {t['label']} |")
    L.append('')
    for t in A['themes']:
        ld = ', '.join(f'{c} {f(r)}' for c, r in t['leaders_m'])
        L.append(f"- **{t['theme']}** leaders (1 mo): {ld}" + (f" · top post: [{t['top_posts'][0]['title'][:80]}]({t['top_posts'][0]['url']})" if t['top_posts'] else ''))
    C = A.get('concentration') or {}
    if C.get('rows'):
        L += ['', '## 5a. AI concentration-risk watch', f"**{C['read']}** (chip index {C['benchmark']} 1 mo {f(C['bench_m'])})", '',
              '| Ticker | 1 mo | 3 mo | vs chips 1 mo | >50d | >200d |', '|---|---|---|---|---|---|']
        L += [f"| {r['ticker']} | {f(r['m'])} | {f(r['q'])} | {f(r['vs_chips_m'])} | {yn(r['above50'])} | {yn(r['above200'])} |" for r in C['rows']]
    if A.get('rising_tickers'):
        L += ['', '## 5b. Rising talk on Reddit (at least double the usual mentions)', '| Ticker | Mentions | Usual | Change | 1 mo price | >50d |', '|---|---|---|---|---|---|']
        L += [f"| {r['ticker']} | {r['mentions']} | {r['baseline']} | {f(r['change'])} | {f(r.get('m'))} | {yn(r.get('above50'))} |" for r in A['rising_tickers']]
    if A.get('consumer'):
        L += ['', '## 5c. Consumer social-arb watch (Google searches, last 4 weeks vs prior 12)', '| Search term | Ticker | Search change | At 12-mo high | 1 mo price | 3 mo price | vs rival 3 mo | Mkt cap $B | Short % | Read |', '|---|---|---|---|---|---|---|---|---|---|']
        L += [f"| {r['term']} | {r['ticker']} | {f(r['search_change'])} | {yn(r['at_12m_high'])} | {f(r.get('m'))} | {f(r.get('q'))} | {(r['vs'] + ' ' + f(r['vs_rival_q'])) if r.get('vs') else '–'} | {r.get('mcap_b') or '–'} | {f(r.get('short_pct'))} | {('🔥 ' + r['read']) if r['flag'] else ''} |" for r in A['consumer']]
    if A['reddit_tickers']:
        L += ['', '## 5d. Most-mentioned tickers on Reddit (this scan)', '| Ticker | Mentions | 1 mo | >50d |', '|---|---|---|---|']
        L += [f"| {r['ticker']} | {r['mentions']} | {f(r.get('m'))} | {yn(r.get('above50'))} |" for r in A['reddit_tickers']]
    L += ['', '## 6. Top 10 by market cap in each sector', '']
    for sec, rows in A['top10'].items():
        L.append(f"**{sec}:** " + ' · '.join(f"{r['ticker']} {f(r['m'])}{'' if r['above50'] else '↓'}" for r in rows))
    if agents:
        L += ['', '## Agent notes']
        for k, v in agents.items():
            if k != 'synthesizer':
                L += [f'### {k.title()}', v.strip(), '']
    src = A['sources']; L += ['', '---', 'Sources this run: ' + ', '.join(f"{k} {'✅' if v else '❌'}" for k, v in src.items()) + ', prices ✅']
    return '\n'.join(L)


def short(A):
    R = A['regime']; s = A['sectors']
    up = [x for x in s if x['rank_change'] > 0][:3]
    hot = [t for t in A['themes'] if t['label'].startswith(('CONFIRMED', 'EARLY'))]
    msg = [f"📊 Market scan {A['date']}: {R['label']}", f"SPY 1wk {f(R['spy']['w'])}, 1mo {f(R['spy']['m'])} | {A['mag7']['read']}",
           'Leading sectors: ' + ', '.join(f"{x['sector']} ({f(x['rs_m_now'])})" for x in s[:3]),
           'Moving up: ' + (', '.join(x['sector'] for x in up) or 'none'),
           ('⚠️ 10-yr yield at/above 5%' if R.get('ten_year_alert') else '10-yr below 5%') + ' | AI chain: ' + (A.get('concentration') or {}).get('read', 'n/a'),
           'Rising on Reddit: ' + (', '.join(r['ticker'] for r in A.get('rising_tickers', [])[:5]) or 'none yet'),
           'Search spikes: ' + (', '.join(f"{r['term']} ({r['ticker']})" for r in A.get('consumer', []) if r['flag']) or 'none'),
           'Themes: ' + ('; '.join(f"{t['theme']}: {t['label'].split(' - ')[0]}" for t in hot) or 'nothing confirmed by talk + price')]
    return '\n'.join(msg)


def main():
    cfg = load_config(); A = load_json('analysis.json'); agents = load_json('agents.json')
    md = build(A, agents, cfg)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"{today()}.md").write_text(md); (REPORTS / 'latest.md').write_text(md)
    telegram(short(A) + '\nFull report: reports/latest.md in the repo')
    print('report written', len(md), 'chars')


if __name__ == '__main__':
    sys.exit(main())
