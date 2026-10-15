"""Turn raw data into the read: regime, sector rotation, Mag 7 vs the rest, top-10 per sector,
and the theme 'talk vs tape' matrix. Output: data/<date>/analysis.json"""
import sys, math, re
import numpy as np, pandas as pd
from common import load_config, load_json, save_json, day_dir, HISTORY, today


def ret(s, n):
    s = s.dropna()
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None


def above(s, n):
    s = s.dropna()
    return bool(s.iloc[-1] > s.iloc[-n:].mean()) if len(s) >= n else None


def ytd(s):
    s = s.dropna(); y = s[s.index.year == s.index[-1].year]
    prev = s[s.index.year < s.index[-1].year]
    base = prev.iloc[-1] if len(prev) else y.iloc[0]
    return float(s.iloc[-1] / base - 1)


def basket(px, tickers):
    cols = [t for t in tickers if t in px.columns]
    if not cols:
        return None, []
    r = px[cols].pct_change().mean(axis=1, skipna=True).fillna(0)
    return (1 + r).cumprod(), cols


def pct(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(100 * x, 1)


def regime(px, cfg, L):
    g = cfg['regime']; out = {}
    spy = px[g['index']]
    out['spy'] = dict(last=round(float(spy.dropna().iloc[-1]), 2), w=pct(ret(spy, L['week'])), m=pct(ret(spy, L['month'])),
                      q=pct(ret(spy, L['quarter'])), ytd=pct(ytd(spy)), above50=above(spy, 50), above200=above(spy, 200))
    def ratio(a, b):
        if a in px and b in px:
            r = (px[a] / px[b]).dropna(); return pct(ret(r, L['month']))
    out['equal_vs_cap_1m'] = ratio(g['equal_weight'], g['index'])
    out['small_vs_large_1m'] = ratio(g['small_caps'], g['index'])
    out['credit_appetite_1m'] = ratio(g['credit_risk_on'], g['credit_safe'])
    for k in ('vix', 'ten_year', 'dollar'):
        t = g[k]
        if t in px:
            s = px[t].dropna(); out[k] = dict(last=round(float(s.iloc[-1]), 2), m_change=pct(ret(s, L['month'])))
    score = sum([bool(out['spy']['above200']), bool(out['spy']['above50']),
                 (out.get('vix', {}).get('last') or 99) < 20, (out['credit_appetite_1m'] or 0) > 0])
    ty = out.get('ten_year', {}).get('last')
    out['ten_year_alert'] = bool(ty is not None and ty >= g.get('ten_year_alert', 99))
    out['label'] = {4: 'RISK-ON', 3: 'RISK-ON (some caution)', 2: 'MIXED', 1: 'RISK-OFF (some support)', 0: 'RISK-OFF'}[score]
    out['score_0_4'] = score
    return out


def sectors(px, cfg, L):
    spy = px[cfg['regime']['index']]; rows = []
    for name, t in cfg['sectors'].items():
        if t not in px:
            continue
        s = px[t]
        rs_now = ret(s, L['month']) - ret(spy, L['month'])
        s1, spy1 = s.dropna().iloc[:-L['week']], spy.dropna().iloc[:-L['week']]
        rs_prev = ret(s1, L['month']) - ret(spy1, L['month'])
        rows.append(dict(sector=name, etf=t, w=pct(ret(s, L['week'])), m=pct(ret(s, L['month'])), q=pct(ret(s, L['quarter'])),
                         rs_m_now=pct(rs_now), rs_m_last_week=pct(rs_prev), above50=above(s, 50), above200=above(s, 200)))
    df = pd.DataFrame(rows)
    df['rank_now'] = df.rs_m_now.rank(ascending=False).astype(int)
    df['rank_last_week'] = df.rs_m_last_week.rank(ascending=False).astype(int)
    df['rank_change'] = df.rank_last_week - df.rank_now          # + = moving up the leaderboard
    return df.sort_values('rank_now').to_dict('records')


def top10(px, caps, cfg, L):
    out = {}; breadth50 = []; breadth200 = []
    for sec, cands in cfg['sector_candidates'].items():
        etf = px.get(cfg['sectors'][sec])
        ranked = sorted([c for c in cands if c in caps and c in px], key=lambda c: -caps[c])[:cfg['report']['top_n']]
        rows = []
        for c in ranked:
            s = px[c]; a50, a200 = above(s, 50), above(s, 200)
            breadth50.append(a50); breadth200.append(a200)
            rows.append(dict(ticker=c, mcap_b=round(caps[c] / 1e9), m=pct(ret(s, L['month'])), q=pct(ret(s, L['quarter'])),
                             ytd=pct(ytd(s)), vs_sector_m=pct(ret(s, L['month']) - (ret(etf, L['month']) if etf is not None else 0)),
                             above50=a50, above200=a200))
        out[sec] = rows
    b50 = [x for x in breadth50 if x is not None]; b200 = [x for x in breadth200 if x is not None]
    return out, dict(pct_top10s_above_50d=pct(np.mean(b50)) if b50 else None, pct_top10s_above_200d=pct(np.mean(b200)) if b200 else None)


def mag7(px, caps, cfg, L):
    g = cfg['regime']; m7 = [t for t in cfg['mag7'] if t in px]
    b, _ = basket(px, m7); out = {'members': m7}
    for k, n in (('w', L['week']), ('m', L['month']), ('q', L['quarter'])):
        out[f'mag7_{k}'] = pct(ret(b, n)); out[f'spy_{k}'] = pct(ret(px[g['index']], n))
        out[f'equal_weight_{k}'] = pct(ret(px[g['equal_weight']], n)) if g['equal_weight'] in px else None
    out['mag7_ytd'] = pct(ytd(b)); out['spy_ytd'] = pct(ytd(px[g['index']]))
    out['equal_weight_ytd'] = pct(ytd(px[g['equal_weight']])) if g['equal_weight'] in px else None
    tot = sum(caps.get(t, 0) for lst in cfg['sector_candidates'].values() for t in set(lst))
    out['mag7_share_of_tracked_mcap'] = pct(sum(caps.get(t, 0) for t in m7) / tot) if tot else None
    out['each'] = {t: dict(m=pct(ret(px[t], L['month'])), q=pct(ret(px[t], L['quarter'])), ytd=pct(ytd(px[t]))) for t in m7}
    gap = (out['mag7_q'] or 0) - (out['equal_weight_q'] or 0)
    out['read'] = ('Narrow market: Mag 7 is carrying it' if gap > 5 else
                   'Broadening: the average stock is keeping up or leading' if gap < -2 else 'Roughly balanced')
    return out


def buzz_change(name, col):
    p = HISTORY / f'{name}.csv'
    if not p.exists():
        return None, None
    h = pd.read_csv(p, parse_dates=['date']).sort_values('date')
    if col not in h:
        return None, None
    now = h[h.date == h.date.max()][col].iloc[0]
    base = h[h.date <= h.date.max() - pd.Timedelta(days=5)].tail(4)[col]
    if 'n_posts' in h:   # normalise by sample size so a bigger scrape is not 'more talk'
        n_now = h[h.date == h.date.max()]['n_posts'].iloc[0]; n_base = h.loc[base.index, 'n_posts']
        now = now / max(n_now, 1) * 1000; base = base / n_base.clip(lower=1) * 1000
    if len(base) == 0 or base.mean() == 0:
        return float(now), None
    return float(now), float(now / base.mean() - 1)


def themes(px, cfg, L, reddit, trends, xg, news):
    spy = px[cfg['regime']['index']]; rows = []
    for name, th in cfg['themes'].items():
        b, cols = basket(px, th.get('etfs', []) + th.get('tickers', []))
        if b is None:
            continue
        rs_m = ret(b, L['month']) - ret(spy, L['month']); rs_q = ret(b, L['quarter']) - ret(spy, L['quarter'])
        r_now, r_chg = buzz_change('reddit_themes', name)
        tr = [v['change'] for v in (trends or {}).get('terms', {}).values() if v.get('theme') == name and v.get('change') is not None]
        tr_chg = float(np.mean(tr)) if tr else None
        xv = ((xg or {}).get('themes', {}).get(name) or {}).get('volume')
        n_news = len((news or {}).get('by_theme', {}).get(name, []))
        talk_up = (r_chg is not None and r_chg >= 0.30) or (tr_chg is not None and tr_chg >= 0.20) or xv == 'high'
        talk_down = (r_chg is not None and r_chg <= -0.30) and (tr_chg is None or tr_chg <= 0)
        price_up = rs_m > 0 and bool(above(b, 50))
        hot_run = ret(b, L['quarter']) > 0.40
        if talk_up and price_up:
            label = 'CONFIRMED - talk and price both rising' + (' (extended: up >40% in 3 months, crowded risk)' if hot_run else '')
        elif talk_up and not price_up:
            label = 'EARLY - talk rising, price not yet (social-arbitrage watch)'
        elif price_up and not talk_up:
            label = 'STEALTH - price leading, talk quiet'
        elif talk_down and rs_m < 0 and not above(b, 50):
            label = 'FADING - talk and price cooling'
        else:
            label = 'NEUTRAL'
        leaders = sorted([(c, ret(px[c], L['month'])) for c in th.get('tickers', []) if c in px and ret(px[c], L['month']) is not None],
                         key=lambda x: -x[1])
        rows.append(dict(theme=name, basket=cols, w=pct(ret(b, L['week'])), m=pct(ret(b, L['month'])), q=pct(ret(b, L['quarter'])),
                         rs_vs_spy_m=pct(rs_m), rs_vs_spy_q=pct(rs_q), above50=above(b, 50),
                         reddit_mentions_per_1k_posts=None if r_now is None else round(r_now, 1), reddit_change=pct(r_chg),
                         google_trends_change=pct(tr_chg), x_volume=xv, news_headlines=n_news, label=label,
                         leaders_m=[(c, pct(r)) for c, r in leaders[:3]], laggards_m=[(c, pct(r)) for c, r in leaders[-2:]],
                         top_posts=(reddit or {}).get('theme_top_posts', {}).get(name, [])))
    return sorted(rows, key=lambda r: -(r['rs_vs_spy_m'] or -999))


def reddit_tickers(px, reddit, L):
    out = []
    for t, n in (reddit or {}).get('top_tickers', [])[:20]:
        row = dict(ticker=t, mentions=n)
        if t in px:
            row.update(m=pct(ret(px[t], L['month'])), above50=above(px[t], 50))
        out.append(row)
    return out


def concentration(px, cfg, L):
    cw = cfg.get('concentration_watch') or {}
    b = cw.get('benchmark', 'SMH'); rows = []
    if b not in px:
        return {}
    bm, bq = ret(px[b], L['month']), ret(px[b], L['quarter'])
    for t in cw.get('tickers', []):
        if t in px:
            rows.append(dict(ticker=t, m=pct(ret(px[t], L['month'])), q=pct(ret(px[t], L['quarter'])),
                             vs_chips_m=pct(ret(px[t], L['month']) - bm), above50=above(px[t], 50), above200=above(px[t], 200)))
    weak = [r['ticker'] for r in rows if r['above200'] is False or (r['vs_chips_m'] or 0) < -10]
    return dict(benchmark=b, bench_m=pct(bm), bench_q=pct(bq), rows=rows, warning_names=weak,
                read=('Stress in the AI chain: ' + ', '.join(weak)) if weak else 'No obvious cracks in the AI chain leaders')


def consumer(px, trends, L, cfg, info, news, reddit=None, youtube=None):
    """Camillo-style checks on each search spike: needle mover (size), fuel (short interest), already priced? already in the news?"""
    out = []; vs = {c['ticker']: c.get('vs') for c in cfg.get('consumer_watch', [])}
    heads = ' '.join(h['title'].lower() for h in (news or {}).get('latest', []))
    for term, v in ((trends or {}).get('consumer') or {}).items():
        t = v.get('ticker'); row = dict(term=term, ticker=t, search_change=pct(v.get('change')), at_12m_high=v.get('at_12m_high'),
                                        yoy_same_season=pct(v.get('yoy_same_season')), at_5y_high=v.get('at_5y_high'))
        rb = ((reddit or {}).get('brands') or {}).get(term, {}); yt = ((youtube or {}).get('terms') or {}).get(term, {})
        row.update(reddit_mentions=rb.get('mentions'), scare_posts=rb.get('scare'), scare_examples=rb.get('scare_examples', []),
                   yt_views=yt.get('views_30d_top5'), yt_intent_per_100=yt.get('intent_per_100'), yt_scare_per_100=yt.get('scare_per_100'))
        scare_flag = (rb.get('scare') or 0) >= 2 or (yt.get('scare_per_100') or 0) >= 5
        row['scare_flag'] = scare_flag
        if t in px:
            row.update(m=pct(ret(px[t], L['month'])), q=pct(ret(px[t], L['quarter'])))
        if vs.get(t) and vs[t] in px and t in px:
            row['vs'] = vs[t]; row['vs_rival_q'] = pct(ret(px[t], L['quarter']) - ret(px[vs[t]], L['quarter']))
        inf = (info or {}).get(t, {})
        row['mcap_b'] = round(inf['mcap'] / 1e9, 1) if inf.get('mcap') else None
        row['short_pct'] = pct(inf['short_pct_float']) if inf.get('short_pct_float') else None
        row['in_headlines'] = term.split()[0] in heads
        row['flag'] = bool((v.get('change') or 0) >= 0.5 or v.get('at_12m_high') or (v.get('yoy_same_season') or 0) >= 0.5)
        if row['flag']:
            moved = (row.get('q') or 0) > 30
            big = (row['mcap_b'] or 0) > 100
            row['read'] = ('CAUTION - scare/negative-virality talk rising: check if it is true' if scare_flag else
                           'LATE - price already ran / in the news' if moved or row['in_headlines'] else
                           'WATCH - spike at a giant, may not move the needle' if big else
                           'EARLY - search spike, price and news not there yet: verify (stores, reviews, analyst coverage)')
        else:
            row['read'] = 'CAUTION - scare/negative-virality talk' if scare_flag else ''
        out.append(row)
    return sorted(out, key=lambda r: -(r['search_change'] or -999))


def rising_tickers(px, cfg, L):
    p = HISTORY / 'reddit_tickers.csv'
    if not p.exists():
        return []
    h = pd.read_csv(p, parse_dates=['date']).sort_values('date').set_index('date').fillna(0)
    if len(h) < 2:
        return []
    now = h.iloc[-1]; base = h[h.index <= h.index[-1] - pd.Timedelta(days=5)].tail(4)
    if not len(base):
        return []
    b = base.mean(); out = []
    for t in now.index:
        if now[t] >= cfg['reddit'].get('rising_min_mentions', 5):
            ch = (now[t] + 1) / (b.get(t, 0) + 1) - 1
            if ch >= 1.0:   # at least double the usual talk
                row = dict(ticker=t, mentions=int(now[t]), baseline=round(float(b.get(t, 0)), 1), change=pct(ch))
                if t in px:
                    row.update(m=pct(ret(px[t], L['month'])), above50=above(px[t], 50))
                out.append(row)
    return sorted(out, key=lambda r: -r['change'])[:15]


def narratives(cfg, reddit, news):
    out = []
    for key, nv in cfg.get('narratives', {}).items():
        r_now, r_chg = buzz_change('narratives_reddit', key)
        n_now, n_chg = buzz_change('narratives_news', key)
        rn = ((reddit or {}).get('narratives') or {}).get(key, {})
        chg = [c for c in (r_chg, n_chg) if c is not None]
        accel = max(chg) if chg else None
        out.append(dict(key=key, label=nv['label'], reddit_per_1k=None if r_now is None else round(r_now, 1), reddit_change=pct(r_chg),
                        news_per_1k=None if n_now is None else round(n_now, 1), news_change=pct(n_chg),
                        ground_truth_posts=rn.get('ground_truth'), examples=rn.get('examples', [])[:2] + ((news or {}).get('narratives', {}).get(key, {}).get('examples', [])[:2]),
                        accelerating=bool(accel is not None and accel >= 0.5)))
    return out


def catalysts(px, cfg, L):
    out = []; today_ = pd.Timestamp(today())
    for c in cfg.get('catalysts', []):
        try:
            days = (pd.Timestamp(c['date']) - today_).days
        except Exception:
            days = None
        def rows(lst, side):
            return [dict(ticker=t, side=side, w=pct(ret(px[t], L['week'])), m=pct(ret(px[t], L['month'])), q=pct(ret(px[t], L['quarter'])))
                    for t in lst if t in px]
        out.append(dict(name=c['name'], date=c['date'], days_to_event=days, benchmarks=c.get('benchmarks', ''),
                        tickers=rows(c.get('primary', []), 'main') + rows(c.get('second_order_up', []), '2nd-order +') + rows(c.get('second_order_down', []), '2nd-order -')))
    return out


def big_movers(px, cfg, L, news, threshold=0.08):
    """Watch-list names that moved a lot this week; agents must judge if the reason is material or noise."""
    watch = {s for th in cfg['themes'].values() for s in th.get('tickers', [])} | {c['ticker'] for c in cfg.get('consumer_watch', [])} | set(cfg['mag7'])
    heads = (news or {}).get('latest', [])
    out = []
    for t in sorted(watch):
        if t in px:
            w = ret(px[t], L['week'])
            if w is not None and abs(w) >= threshold:
                hl = [h['title'] for h in heads if re.search(r'\b' + re.escape(t) + r'\b', h['title'])][:3]
                out.append(dict(ticker=t, w=pct(w), m=pct(ret(px[t], L['month'])), headlines=hl))
    return sorted(out, key=lambda r: -abs(r['w']))[:20]


def main():
    cfg = load_config(); L = cfg['report']['lookbacks_days']; d = day_dir()
    px = pd.read_csv(d / 'prices.csv', index_col=0, parse_dates=True).sort_index()
    caps = load_json('market_caps.json', default={})
    reddit, trends, xg, news = (load_json(f, default=None) for f in ('reddit.json', 'trends.json', 'x_grok.json', 'news.json'))
    t10, breadth = top10(px, caps, cfg, L)
    A = dict(date=today(), last_bar=str(px.index.max().date()), regime=regime(px, cfg, L), breadth=breadth,
             sectors=sectors(px, cfg, L), mag7=mag7(px, caps, cfg, L), top10=t10,
             themes=themes(px, cfg, L, reddit, trends, xg, news), reddit_tickers=reddit_tickers(px, reddit, L),
             rising_tickers=rising_tickers(px, cfg, L), narratives=narratives(cfg, reddit, news), catalysts=catalysts(px, cfg, L), big_movers=big_movers(px, cfg, L, news), concentration=concentration(px, cfg, L), consumer=consumer(px, trends, L, cfg, load_json('consumer_info.json', default={}), news, reddit, load_json('youtube.json', default=None)),
             discovery=dict(reddit=(reddit or {}).get('discovery', [])[:15], search_rising=(trends or {}).get('discovery', {})),
             sources=dict(reddit=bool(reddit and reddit.get('n_posts')), trends=bool(trends and trends.get('terms')),
                          x=bool(xg and xg.get('themes')), news=bool(news and news.get('n'))))
    save_json(A, 'analysis.json')
    print('analysis saved:', A['regime']['label'], '| themes:', len(A['themes']))


if __name__ == '__main__':
    sys.exit(main())
