"""Turn raw data into the read: regime, sector rotation, Mag 7 vs the rest, top-10 per sector,
and the theme 'talk vs tape' matrix. Output: data/<date>/analysis.json"""
import sys, math, re
import numpy as np, pandas as pd
from common import ROOT, load_config, load_json, save_json, day_dir, HISTORY, today


def ret(s, n):
    s = s.dropna()
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None


def above(s, n):
    s = s.dropna()
    return bool(s.iloc[-1] > s.iloc[-n:].mean()) if len(s) >= n else None


def diff(a, b):
    return None if a is None or b is None else a - b


def ytd(s):
    s = s.dropna()
    if s.empty:
        return None
    y = s[s.index.year == s.index[-1].year]
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
        rs_now = diff(ret(s, L['month']), ret(spy, L['month']))
        s1, spy1 = s.dropna().iloc[:-L['week']], spy.dropna().iloc[:-L['week']]
        rs_prev = diff(ret(s1, L['month']), ret(spy1, L['month']))
        rows.append(dict(sector=name, etf=t, w=pct(ret(s, L['week'])), m=pct(ret(s, L['month'])), q=pct(ret(s, L['quarter'])),
                         rs_m_now=pct(rs_now), rs_m_last_week=pct(rs_prev), above50=above(s, 50), above200=above(s, 200)))
    df = pd.DataFrame(rows)
    df['rank_now'] = df.rs_m_now.rank(ascending=False).fillna(len(df)).astype(int)
    df['rank_last_week'] = df.rs_m_last_week.rank(ascending=False).fillna(len(df)).astype(int)
    df['rank_change'] = df.rank_last_week - df.rank_now          # + = moving up the leaderboard
    return df.sort_values('rank_now').to_dict('records')


def top10(px, caps, cfg, L):
    out = {}; breadth50 = []; breadth200 = []
    for sec, cands in cfg['sector_candidates'].items():
        etf = px.get(cfg['sectors'][sec])
        ranked = sorted([c for c in cands if caps.get(c) and c in px], key=lambda c: -caps[c])[:cfg['report']['top_n']]
        rows = []
        for c in ranked:
            s = px[c]; a50, a200 = above(s, 50), above(s, 200)
            breadth50.append(a50); breadth200.append(a200)
            rows.append(dict(ticker=c, mcap_b=round(caps[c] / 1e9), m=pct(ret(s, L['month'])), q=pct(ret(s, L['quarter'])),
                             ytd=pct(ytd(s)), vs_sector_m=pct(diff(ret(s, L['month']), ret(etf, L['month']) if etf is not None else 0)),
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


def extras(px, L):
    """Earnings soon, insider buying, unusual options, app-store ranks for the focus names."""
    E = load_json('extras.json', default=None)
    if not E:
        return None
    now = pd.Timestamp(today()); out = dict(earnings=[], insiders=[], options=[], apps=[])
    for t, r in E.get('names', {}).items():
        m = pct(ret(px[t], L['month'])) if t in px else None
        d = r.get('next_earnings')
        if d:
            days = (pd.Timestamp(d) - now).days
            if 0 <= days <= 30:
                out['earnings'].append(dict(ticker=t, date=d, days=days, m=m))
        ins = r.get('insiders_90d')
        if ins and ins.get('buys'):
            out['insiders'].append(dict(ticker=t, m=m, **ins))
        o = r.get('options')
        if o and (o.get('unusual') or (o.get('vol_vs_oi') or 0) >= 0.5):
            out['options'].append(dict(ticker=t, m=m, **o))
    hist = HISTORY / 'app_ranks.csv'
    prev = None
    if hist.exists():
        h = pd.read_csv(hist, parse_dates=['date']).sort_values('date')
        old = h[h.date <= h.date.max() - pd.Timedelta(days=5)]
        prev = old.iloc[-1] if len(old) else None
    for app, v in (E.get('apps') or {}).get('charts', {}).items():
        was = prev.get(app) if prev is not None and app in prev and pd.notna(prev.get(app)) else None
        out['apps'].append(dict(app=app, ticker=v['ticker'], free_rank=v.get('top-free'), paid_rank=v.get('top-paid'),
                                free_rank_last_week=int(was) if was is not None else None,
                                m=pct(ret(px[v['ticker']], L['month'])) if v['ticker'] in px else None))
    out['earnings'].sort(key=lambda r: r['days']); out['insiders'].sort(key=lambda r: -r['buy_value'])
    out['options'].sort(key=lambda r: -(r['unusual'][0]['volume'] if r['unusual'] else 0)); out['apps'].sort(key=lambda r: r['free_rank'] or 999)
    return out


def crypto(px, cfg, L):
    c = cfg.get('crypto', {}); J = load_json('crypto.json', default={}) or {}
    def row(name, t):
        if t not in px:
            return None
        s = px[t].dropna()
        # crypto trades 7 days a week: use calendar windows so a "week" is 7 days for coins and stocks alike
        def r(days):
            past = s[s.index <= s.index[-1] - pd.Timedelta(days=days)]
            return pct(float(s.iloc[-1] / past.iloc[-1] - 1)) if len(past) else None
        return dict(name=name, ticker=t, last=round(float(s.iloc[-1]), 6 if s.iloc[-1] < 1 else 2), w=r(7), m=r(30), q=r(91), ytd=pct(ytd(s)),
                    above50=above(s, 50), above200=above(s, 200))
    coins = [x for x in (row(n, t) for n, t in c.get('coins', {}).items()) if x]
    metals = [x for x in (row(n, t) for n, t in c.get('metals', {}).items()) if x]
    related = {g: [x for x in (row(t, t) for t in lst) if x] for g, lst in c.get('related', {}).items()}
    btc = next((x for x in coins if x['ticker'] == 'BTC-USD'), None)
    trend = None
    if btc:
        trend = ('UPTREND (above 50 and 200-day)' if btc['above50'] and btc['above200'] else
                 'DOWNTREND (below 50 and 200-day)' if btc['above50'] is False and btc['above200'] is False else 'MIXED')
    gold = next((x for x in metals if x['ticker'] == 'GC=F'), None); silver = next((x for x in metals if x['ticker'] == 'SI=F'), None)
    gs = None
    if 'GC=F' in px and 'SI=F' in px:
        rr = (px['GC=F'] / px['SI=F']).dropna()
        if len(rr):
            gs = dict(now=round(float(rr.iloc[-1]), 1), avg_1y=round(float(rr.iloc[-252:].mean()), 1))
    # Reddit crypto talk vs its own usual level
    rising = []
    p = HISTORY / 'crypto_mentions.csv'
    if p.exists():
        h = pd.read_csv(p, parse_dates=['date']).sort_values('date').set_index('date').fillna(0)
        base = h[h.index <= h.index[-1] - pd.Timedelta(days=5)].tail(4)
        if len(base):
            for t, n in h.iloc[-1].items():
                b = base[t].mean() if t in base else 0
                if n >= 10 and (n + 1) / (b + 1) >= 2:
                    rising.append(dict(ticker=t, mentions=int(n), usual=round(float(b), 1)))
    return dict(btc_trend=trend, coins=coins, metals=metals, related=related, gold_silver_ratio=gs,
                fear_greed=J.get('fear_greed'), trending=J.get('trending', []), memes=J.get('memes', []),
                reddit=J.get('reddit', [])[:15], reddit_rising=rising, errors=J.get('errors', []))


def setups(px, cfg, L):
    """Yearly VWAP (anchored Jan 1, typical price x volume) + monthly 20-SMA + weekly 200-SMA, on daily data."""
    c = cfg.get('setups', {}); d = day_dir()
    if not c.get('enabled', True):
        return None
    try:
        vol = pd.read_csv(d / 'volumes.csv', index_col=0, parse_dates=True).sort_index()
    except Exception:
        return None
    try:
        typ = pd.read_csv(d / 'typical.csv', index_col=0, parse_dates=True).sort_index()
    except Exception:
        typ = px
    names = sorted({t for l in cfg['sector_candidates'].values() for t in l} | {t for th in cfg['themes'].values() for t in th.get('tickers', []) + th.get('etfs', [])}
                   | {x['ticker'] for x in cfg.get('consumer_watch', [])} | set(cfg.get('extras', {}).get('also_watch', [])) | set(cfg.get('sectors', {}).values()))
    band = c.get('yearly_vwap_band', 0.02); side = c.get('vwap_side', 'any'); mn, wn = c.get('monthly_sma', 20), c.get('weekly_sma', 200)
    rows = []
    for t in names:
        if t not in px or t not in vol or '.' in t:
            continue
        s = px[t].dropna()
        if len(s) < 300:
            continue
        last = s.index[-1]; price = float(s.iloc[-1])
        yr = s.index[s.index.year == last.year]
        tp = (typ[t] if t in typ else px[t]).reindex(yr); v = vol[t].reindex(yr)
        ok = tp.notna() & v.notna()
        if v[ok].sum() <= 0:
            continue
        vwap = float((tp[ok] * v[ok]).sum() / v[ok].sum())
        m = s.resample('ME').last(); w = s.resample('W-FRI').last()
        m_sma = float(m.iloc[-mn:].mean()) if len(m) >= mn else None
        w_sma = float(w.iloc[-wn:].mean()) if len(w) >= wn else None
        dist = price / vwap - 1
        on = abs(dist) <= band and (side == 'any' or (side == 'below' and dist <= 0) or (side == 'above' and dist >= 0))
        um = m_sma is not None and price < m_sma; uw = w_sma is not None and price < w_sma
        hits = int(on) + int(um) + int(uw)
        if hits >= 2:
            rows.append(dict(ticker=t, price=round(price, 2), yearly_vwap=round(vwap, 2), vs_vwap=pct(dist), on_vwap=bool(on),
                             monthly_sma=round(m_sma, 2) if m_sma else None, vs_monthly_sma=pct(price / m_sma - 1) if m_sma else None, under_monthly=bool(um),
                             weekly_sma=round(w_sma, 2) if w_sma else None, vs_weekly_sma=pct(price / w_sma - 1) if w_sma else None, under_weekly=bool(uw),
                             hits=hits, m=pct(ret(s, L['month']))))
    full = sorted([r for r in rows if r['hits'] == 3], key=lambda r: abs(r['vs_vwap'] or 0))
    near = sorted([r for r in rows if r['hits'] == 2], key=lambda r: abs(r['vs_vwap'] or 0))[:c.get('show_near_misses', 15)]
    log_setup('vwap', full, px, cfg)
    return dict(rules=dict(band=band, side=side, monthly_sma=mn, weekly_sma=wn), all_three=full, two_of_three=near, scanned=len(names))


def log_setup(name, rows, px, cfg):
    """Every hit goes to journal/setups.csv so the rule gets scored vs the S&P and a random pick."""
    j = ROOT / 'journal' / 'setups.csv'; j.parent.mkdir(exist_ok=True)
    old = pd.read_csv(j) if j.exists() else pd.DataFrame()
    if len(old):
        if 'setup' not in old:
            old['setup'] = 'vwap'
        old = old[~((old.date == today()) & (old.setup == name))]
    spy = round(float(px[cfg['regime']['index']].dropna().iloc[-1]), 2)
    new = pd.DataFrame([dict(date=today(), setup=name, ticker=r['ticker'], price=r['price'], spy=spy) for r in rows])
    pd.concat([old, new], ignore_index=True).to_csv(j, index=False)


def entry_scans(px, cfg, L, sectors_rows):
    """Rule B (deep drawdown in a weak market, buy in thirds) and momentum (leaders in a strong market)."""
    c = cfg.get('setups', {}); d = day_dir()
    try:
        vol = pd.read_csv(d / 'volumes.csv', index_col=0, parse_dates=True).sort_index()
    except Exception:
        vol = pd.DataFrame()
    spy = px[cfg['regime']['index']]; spy_up = above(spy, 200)
    sec_of = {t: sec for sec, l in cfg['sector_candidates'].items() for t in l}
    names = sorted(set(sec_of) | {t for th in cfg['themes'].values() for t in th.get('tickers', [])} | {x['ticker'] for x in cfg.get('consumer_watch', [])})
    names = [t for t in names if t in px and '.' not in t]
    out = {'spy_above_200d': spy_up}
    rb = c.get('rule_b', {})
    if rb.get('enabled', True):
        rows = []
        for t in names:
            s = px[t].dropna()
            if len(s) < 260:
                continue
            hi = float(s.iloc[-252:].max()); price = float(s.iloc[-1]); dd = price / hi - 1
            dv = float((s.iloc[-20:] * vol[t].reindex(s.index[-20:])).mean()) / 1e6 if t in vol else None
            if dd <= -rb.get('min_drawdown', 0.5) and (dv is None or dv >= rb.get('min_dollar_volume_m', 20)):
                rows.append(dict(ticker=t, price=round(price, 2), off_high=pct(dd), high_252d=round(hi, 2), dollar_vol_m=round(dv) if dv else None,
                                 buy_levels=[round(price * (1 + x), 2) for x in rb.get('tranches', [0, -0.1, -0.2])], m=pct(ret(s, L['month']))))
        rows.sort(key=lambda r: r['off_high'])
        out['rule_b'] = dict(active=spy_up is False, rows=rows)
        if spy_up is False and rows:
            log_setup('rule_b', rows, px, cfg)
    mo = c.get('momentum', {})
    if mo.get('enabled', True):
        top_secs = {r['sector'] for r in sectors_rows[:mo.get('top_sectors', 5)]} if sectors_rows else set()
        sc = []
        for t in names:
            s = px[t].dropna()
            if len(s) < 260:
                continue
            r121 = float(s.iloc[-22] / s.iloc[-253] - 1)
            sc.append((t, r121, s))
        if sc:
            cut = pd.Series([x[1] for x in sc]).quantile(1 - mo.get('top_pct', 0.10))
            rows = [dict(ticker=t, price=round(float(s.iloc[-1]), 2), r12_1=pct(r), sector=sec_of.get(t, 'theme'), m=pct(ret(s, L['month'])))
                    for t, r, s in sc if r >= cut and above(s, 200) and (not top_secs or sec_of.get(t) in top_secs or t not in sec_of)]
            rows.sort(key=lambda r: -r['r12_1'])
            rows = rows[:mo.get('max_show', 20)]
            out['momentum'] = dict(active=bool(spy_up), sectors=sorted(top_secs), rows=rows)
            if spy_up and rows:
                log_setup('momentum', rows, px, cfg)
    return out


def wealth_builder(px, cfg, L):
    """Under the monthly 20-SMA and weekly 200-SMA, ideally daily 20-SMA rising above the 200-SMA,
    in a company with more money than its problems: net cash, free cash flow, growth, analyst and institutional love."""
    c = cfg.get('setups', {}); wb = c.get('wealth_builder', {})
    F = (load_json('fundamentals.json', default={}) or {}).get('names', {})
    if not wb.get('enabled', True) or not F:
        return None
    mn, wn = c.get('monthly_sma', 20), c.get('weekly_sma', 200); watch = set(wb.get('watch', []))
    rows = []
    for t, f in F.items():
        if t not in px:
            continue
        s = px[t].dropna()
        if len(s) < 300:
            continue
        p = float(s.iloc[-1]); m = s.resample('ME').last(); w = s.resample('W-FRI').last()
        m_sma = float(m.iloc[-mn:].mean()) if len(m) >= mn else None; w_sma = float(w.iloc[-wn:].mean()) if len(w) >= wn else None
        d20 = s.rolling(20).mean(); d200 = s.rolling(200).mean()
        daily_ok = bool(d20.iloc[-1] > d200.iloc[-1] and d20.iloc[-1] > d20.iloc[-6]) if len(s) >= 206 else False
        cash, debt = f.get('totalCash') or 0, f.get('totalDebt') or 0
        mc = (f.get('marketCap') or 0) / 1e9
        checks = {
            'net cash or little debt': bool(cash) and debt <= wb.get('max_debt_to_cash', 1.0) * cash,
            'free cash flow positive': (f.get('freeCashflow') or 0) > 0,
            'revenue growing': (f.get('revenueGrowth') or 0) > 0,
            'analysts like it': (f.get('recommendationMean') or 9) <= 2.5 and (f.get('numberOfAnalystOpinions') or 0) >= 10,
            'big institutions own it': (f.get('heldPercentInstitutions') or 0) >= 0.6,
            'large cap': mc >= wb.get('min_market_cap_b', 10),
        }
        score = sum(checks.values())
        under_m = m_sma is not None and p < m_sma; under_w = w_sma is not None and p < w_sma
        rows.append(dict(ticker=t, name=f.get('shortName'), price=round(p, 2), under_monthly=under_m, vs_monthly=pct(p / m_sma - 1) if m_sma else None,
                         under_weekly=under_w, vs_weekly=pct(p / w_sma - 1) if w_sma else None, daily_20_rising_above_200=daily_ok,
                         money_score=score, missing=[k for k, v in checks.items() if not v], mcap_b=round(mc), cash_b=round(cash / 1e9, 1),
                         debt_b=round(debt / 1e9, 1), fcf_b=round((f.get('freeCashflow') or 0) / 1e9, 1),
                         rev_growth=pct(f.get('revenueGrowth')) if f.get('revenueGrowth') is not None else None,
                         analyst=f.get('recommendationMean'), on_watch=t in watch, m=pct(ret(s, L['month']))))
    good = lambda r: r['money_score'] >= wb.get('min_money_score', 4) and r['mcap_b'] >= wb.get('min_market_cap_b', 10)
    full = sorted([r for r in rows if r['under_monthly'] and r['under_weekly'] and good(r)], key=lambda r: (not r['daily_20_rising_above_200'], -r['money_score']))
    one = sorted([r for r in rows if (r['under_monthly'] != r['under_weekly']) and good(r)], key=lambda r: -r['money_score'])[:15]
    if full:
        log_setup('wealth_builder', full, px, cfg)
    return dict(full=full, one_timeframe=one, watch_status=sorted([r for r in rows if r['on_watch']], key=lambda r: r['ticker']))


def setup_scorecards():
    p = ROOT / 'journal' / 'setups_scored.csv'
    if not p.exists():
        return None
    d = pd.read_csv(p)
    if 'setup' not in d:
        d['setup'] = 'vwap'
    out = {}
    for name, g in d.groupby('setup'):
        res = {}
        for lab in ('1m', '3m', '6m'):
            c = f'excess_{lab}'
            if c in g and g[c].notna().any():
                x = g[g[c].notna()]
                res[lab] = dict(ideas=len(x), avg_vs_spy=pct(x[c].mean()), hit_rate=pct((x[c] > 0).mean()),
                                avg_vs_universe=pct(x[f'edge_vs_universe_{lab}'].mean()) if f'edge_vs_universe_{lab}' in x else None)
        out[name] = res
    return out


def scorecard(name='scored.csv'):
    p = ROOT / 'journal' / name
    if not p.exists():
        return None
    d = pd.read_csv(p); res = {}
    for lab in ('1m', '3m', '6m'):
        c = f'excess_{lab}'
        if c in d and d[c].notna().any():
            x = d[d[c].notna()]
            res[lab] = dict(ideas=len(x), avg_vs_spy=pct(x[c].mean()), hit_rate=pct((x[c] > 0).mean()),
                            avg_vs_universe=pct(x[f'edge_vs_universe_{lab}'].mean()) if f'edge_vs_universe_{lab}' in x else None)
    return dict(total_ideas=len(d), windows=res)


def main():
    cfg = load_config(); L = cfg['report']['lookbacks_days']; d = day_dir()
    px = pd.read_csv(d / 'prices.csv', index_col=0, parse_dates=True).sort_index()
    caps = load_json('market_caps.json', default={})
    reddit, trends, xg, news = (load_json(f, default=None) for f in ('reddit.json', 'trends.json', 'x_grok.json', 'news.json'))
    errors = []
    def safe(name, fn, default=None):
        """One broken section must not kill the whole report."""
        try:
            return fn()
        except Exception as e:
            import traceback; traceback.print_exc()
            errors.append(f'{name}: {type(e).__name__}: {e}'); return default
    t10, breadth = safe('top10', lambda: top10(px, caps, cfg, L), default=({}, {'pct_top10s_above_50d': None, 'pct_top10s_above_200d': None}))
    A = dict(date=today(), last_bar=str(px.index.max().date()), regime=safe('regime', lambda: regime(px, cfg, L), {'label': 'UNKNOWN', 'spy': {}}), breadth=breadth,
             sectors=safe('sectors', lambda: sectors(px, cfg, L), []), mag7=safe('mag7', lambda: mag7(px, caps, cfg, L), {}), top10=t10,
             themes=safe('themes', lambda: themes(px, cfg, L, reddit, trends, xg, news), []), reddit_tickers=safe('reddit_tickers', lambda: reddit_tickers(px, reddit, L), []),
             rising_tickers=safe('rising_tickers', lambda: rising_tickers(px, cfg, L), []), narratives=safe('narratives', lambda: narratives(cfg, reddit, news), {}),
             catalysts=safe('catalysts', lambda: catalysts(px, cfg, L), []), big_movers=safe('big_movers', lambda: big_movers(px, cfg, L, news), []),
             concentration=safe('concentration', lambda: concentration(px, cfg, L), {}),
             consumer=safe('consumer', lambda: consumer(px, trends, L, cfg, load_json('consumer_info.json', default={}), news, reddit, load_json('youtube.json', default=None)), []),
             discovery=dict(reddit=(reddit or {}).get('discovery', [])[:15], search_rising=(trends or {}).get('discovery', {})),
             sources=dict(reddit=bool(reddit and reddit.get('n_posts')), reddit_via_apewisdom=bool(reddit and reddit.get('apewisdom')), youtube=bool((load_json('youtube.json', default=None) or {}).get('terms')), trends=bool(trends and trends.get('terms')),
                          x=bool(xg and xg.get('themes')), news=bool(news and news.get('n'))))
    A['extras'] = safe('extras', lambda: extras(px, L))
    A['scorecard'] = safe('scorecard', scorecard)
    A['setup_scorecard'] = safe('setup_scorecard', setup_scorecards)
    A['crypto'] = safe('crypto', lambda: crypto(px, cfg, L))
    A['setups'] = safe('setups', lambda: setups(px, cfg, L))
    A['wealth_builder'] = safe('wealth_builder', lambda: wealth_builder(px, cfg, L))
    A['entry_scans'] = safe('entry_scans', lambda: entry_scans(px, cfg, L, A.get('sectors') or []))
    A['sources']['crypto_talk'] = bool(A['crypto'] and (A['crypto']['trending'] or A['crypto']['reddit']))
    A['sources']['earnings_insiders_options'] = bool(A['extras'] and (A['extras']['earnings'] or A['extras']['insiders'] or A['extras']['options']))
    A['sources']['app_store'] = bool(A['extras'] and A['extras']['apps'])
    A['errors'] = errors
    save_json(A, 'analysis.json')
    print('analysis saved:', A['regime']['label'], '| themes:', len(A['themes']))


if __name__ == '__main__':
    sys.exit(main())
