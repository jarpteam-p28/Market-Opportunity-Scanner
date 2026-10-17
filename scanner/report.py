"""Write the readable report: reports/<date>.md (+ reports/latest.md) and a short Telegram summary."""
import os, sys
from common import REPORTS, load_config, load_json, telegram, today


def yn(b):
    return '✅' if b else ('❌' if b is not None else '–')


def f(x, suffix='%'):
    return '–' if x is None else f'{x:+.1f}{suffix}'


def unusual_txt(u):
    if not u:
        return '–'
    u = u[0]
    return f"{u['side']} {u['strike']:g} exp {u['exp']}: {u['volume']:,} vs OI {u['oi']:,}"


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
    if A.get('narratives'):
        L += ['', '## 5e. Narrative meters (talk vs its own usual level)', '| Narrative | Reddit per 1k posts | Change | Headlines per 1k | Change | Dev/IT posts | Accelerating? |', '|---|---|---|---|---|---|---|']
        L += [f"| {n['label']} | {n['reddit_per_1k'] if n['reddit_per_1k'] is not None else '–'} | {f(n['reddit_change'])} | {n['news_per_1k'] if n['news_per_1k'] is not None else '–'} | {f(n['news_change'])} | {n['ground_truth_posts'] if n['ground_truth_posts'] is not None else '–'} | {'⚠️ yes' if n['accelerating'] else 'no'} |" for n in A['narratives']]
        for n in A['narratives']:
            ex = [e for e in n['examples'] if e.get('title')][:2]
            if ex:
                L.append(f"- {n['label']} examples: " + ' · '.join(f"[{e['title'][:90]}]({e.get('url') or e.get('link', '')})" for e in ex))
    if A.get('rising_tickers'):
        L += ['', '## 5b. Rising talk on Reddit (at least double the usual mentions)', '| Ticker | Mentions | Usual | Change | 1 mo price | >50d |', '|---|---|---|---|---|---|']
        L += [f"| {r['ticker']} | {r['mentions']} | {r['baseline']} | {f(r['change'])} | {f(r.get('m'))} | {yn(r.get('above50'))} |" for r in A['rising_tickers']]
    if A.get('consumer'):
        L += ['', '## 5c. Consumer social-arb watch (Google searches, last 4 weeks vs prior 12)', '| Search term | Ticker | Search vs prior 12 wks | vs same weeks last year | 12-mo high | YouTube buying-intent /100 comments | Scare posts | 1 mo price | 3 mo price | vs rival 3 mo | Mkt cap $B | Short % | Read |', '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
        L += [f"| {r['term']} | {r['ticker']} | {f(r['search_change'])} | {f(r.get('yoy_same_season'))} | {yn(r['at_12m_high'])} | {r.get('yt_intent_per_100') if r.get('yt_intent_per_100') is not None else '–'} | {r.get('scare_posts') if r.get('scare_posts') is not None else '–'} | {f(r.get('m'))} | {f(r.get('q'))} | {(r['vs'] + ' ' + f(r['vs_rival_q'])) if r.get('vs') else '–'} | {r.get('mcap_b') or '–'} | {f(r.get('short_pct'))} | {(('⚠️ ' if r.get('scare_flag') else '🔥 ') + r['read']) if r['read'] else ''} |" for r in A['consumer']]
    D = A.get('discovery') or {}
    if D.get('reddit') or D.get('search_rising'):
        L += ['', '## 5h. Discovery: new things people are talking about (wide funnel, not yet on any list)']
        for p in D.get('reddit', [])[:10]:
            L.append(f"- r/{p['sub']} ({p['phrase']}): [{p['title'][:100]}]({p['url']}) · {p['score']} upvotes, {p['comments']} comments")
        for seed, rows in (D.get('search_rising') or {}).items():
            L.append(f"- Google rising searches for '{seed}': " + ', '.join(f"{r.get('query')} (+{r.get('value')}%)" for r in rows[:6]))
    if A.get('catalysts'):
        L += ['', '## 5f. Catalyst calendar']
        for c in A['catalysts']:
            L += [f"**{c['name']}** — {c['date']} ({c['days_to_event']} days away). Benchmarks: {c['benchmarks']}", '',
                  '| Ticker | Role | 1 wk | 1 mo | 3 mo |', '|---|---|---|---|---|']
            L += [f"| {r['ticker']} | {r['side']} | {f(r['w'])} | {f(r['m'])} | {f(r['q'])} |" for r in c['tickers']]
    if A.get('big_movers'):
        L += ['', '## 5g. Big movers on the watch list this week (is the reason material or noise?)', '| Ticker | 1 wk | 1 mo | Headlines found |', '|---|---|---|---|']
        L += [f"| {r['ticker']} | {f(r['w'])} | {f(r['m'])} | {'; '.join(h[:80] for h in r['headlines']) or '–'} |" for r in A['big_movers']]
    if A['reddit_tickers']:
        L += ['', '## 5d. Most-mentioned tickers on Reddit (this scan)', '| Ticker | Mentions | 1 mo | >50d |', '|---|---|---|---|']
        L += [f"| {r['ticker']} | {r['mentions']} | {f(r.get('m'))} | {yn(r.get('above50'))} |" for r in A['reddit_tickers']]
    X = A.get('extras') or {}
    if X.get('earnings'):
        L += ['', '## 5i. Earnings in the next 30 days (watch names)', '| Ticker | Date | Days away | 1 mo price |', '|---|---|---|---|']
        L += [f"| {r['ticker']} | {r['date']} | {r['days']} | {f(r['m'])} |" for r in X['earnings']]
    if X.get('insiders'):
        L += ['', '## 5j. Insider buying, last 90 days (open-market purchases)', '| Ticker | Buys | $ bought | Sells | $ sold | Who bought | 1 mo price |', '|---|---|---|---|---|---|---|']
        L += [f"| {r['ticker']} | {r['buys']} | {r['buy_value']:,} | {r['sells']} | {r['sell_value']:,} | {'; '.join(r['buyers'])[:90] or '–'} | {f(r['m'])} |" for r in X['insiders']]
    if X.get('options'):
        L += ['', '## 5k. Options activity (nearest 2 expirations, last session)', 'Unusual = a contract traded at least 3x its open interest and 500+ contracts: new money positioning. Not direction-proof: it can be a hedge.', '',
              '| Ticker | Call vol | Put vol | Put/call | Volume vs open interest | Biggest unusual contract | 1 mo price |', '|---|---|---|---|---|---|---|']
        L += [f"| {r['ticker']} | {r['call_vol']:,} | {r['put_vol']:,} | {r['put_call'] if r['put_call'] is not None else '–'} | {r['vol_vs_oi'] if r['vol_vs_oi'] is not None else '–'} | {unusual_txt(r['unusual'])} | {f(r['m'])} |" for r in X['options'][:20]]
    if X.get('apps'):
        L += ['', '## 5l. App Store rank (US top 100)', '| App | Ticker | Free rank | Last week | Paid rank | 1 mo price |', '|---|---|---|---|---|---|']
        L += [f"| {r['app']} | {r['ticker']} | {r['free_rank'] or '–'} | {r['free_rank_last_week'] or '–'} | {r['paid_rank'] or '–'} | {f(r['m'])} |" for r in X['apps']]
    S = A.get('scorecard')
    L += ['', '## 7. Scorecard: are the agents beating the S&P?']
    if S and S.get('windows'):
        L += ['| Window | Ideas scored | Avg vs S&P | Hit rate vs S&P | Avg vs random pick from our list |', '|---|---|---|---|---|']
        L += [f"| {k} | {v['ideas']} | {f(v['avg_vs_spy'])} | {v['hit_rate']}% | {f(v['avg_vs_universe'])} |" for k, v in S['windows'].items()]
        L += ['', '_"Random pick" is the average of every stock the scanner tracks over the same days: the placebo. Beating the S&P but not the placebo means the market did the work, not the agents._']
    else:
        L += [f"No idea is a month old yet ({(S or {}).get('total_ideas', 0)} logged). First 1-month scores appear about four weeks after the first watchlist."]
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
           'Narratives: ' + (', '.join(n['label'] + ' accelerating' for n in A.get('narratives', []) if n['accelerating']) or 'nothing accelerating'),
           'Rising on Reddit: ' + (', '.join(r['ticker'] for r in A.get('rising_tickers', [])[:5]) or 'none yet'),
           'Search spikes: ' + (', '.join(f"{r['term']} ({r['ticker']})" for r in A.get('consumer', []) if r['flag']) or 'none'),
           'Themes: ' + ('; '.join(f"{t['theme']}: {t['label'].split(' - ')[0]}" for t in hot) or 'nothing confirmed by talk + price')]
    try:
        import pandas as pd
        from common import ROOT
        j = pd.read_csv(ROOT / 'journal' / 'theses.csv'); j = j[j.date == A['date']]
        if len(j):
            msg.append('Ideas: ' + '; '.join(f"{r.ticker} ({r.stance}, {r.get('conviction', '')})" for _, r in j.head(5).iterrows()))
    except Exception:
        pass
    return '\n'.join(msg)


def main():
    cfg = load_config(); A = load_json('analysis.json'); agents = load_json('agents.json')
    md = build(A, agents, cfg)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"{today()}.md").write_text(md); (REPORTS / 'latest.md').write_text(md)
    repo = os.environ.get('GITHUB_REPOSITORY', 'jarpteam-p28/Market-Opportunity-Scanner')   # set automatically on GitHub
    telegram(short(A) + f'\nFull report: https://github.com/{repo}/blob/main/reports/latest.md')
    print('report written', len(md), 'chars')


if __name__ == '__main__':
    sys.exit(main())
