"""Crypto talk: CoinGecko trending coins (most searched on CoinGecko), top meme coins by volume, the Crypto Fear & Greed
index, and ApeWisdom crypto mentions on Reddit. All free, no keys, every piece fails soft. Prices come from collect_market.
Output: data/<date>/crypto.json"""
import sys
import requests
from common import load_config, save_json, append_history, today

H = {'User-Agent': 'market-scanner/1.0 (personal research)', 'accept': 'application/json'}


def get(url, **params):
    r = requests.get(url, params=params, headers=H, timeout=25); r.raise_for_status(); return r.json()


def main():
    cfg = load_config(); c = cfg.get('crypto', {})
    if not c.get('enabled', True):
        return
    out = {'date': today(), 'errors': []}
    try:   # what people are searching for on CoinGecko right now
        j = get('https://api.coingecko.com/api/v3/search/trending')
        out['trending'] = [dict(name=x['item']['name'], symbol=x['item']['symbol'].upper(), mcap_rank=x['item'].get('market_cap_rank'),
                                chg_24h=(x['item'].get('data') or {}).get('price_change_percentage_24h', {}).get('usd'))
                           for x in j.get('coins', [])][:15]
    except Exception as e:
        out['errors'].append(f'coingecko trending: {e}')
    try:   # meme coins with the most trading volume
        j = get('https://api.coingecko.com/api/v3/coins/markets', vs_currency='usd', category='meme-token', order='volume_desc',
                per_page=c.get('meme_top_n', 15), page=1, price_change_percentage='24h,7d,30d')
        out['memes'] = [dict(name=x['name'], symbol=x['symbol'].upper(), mcap_b=round((x.get('market_cap') or 0) / 1e9, 2),
                             vol_b=round((x.get('total_volume') or 0) / 1e9, 2), chg_24h=x.get('price_change_percentage_24h_in_currency'),
                             chg_7d=x.get('price_change_percentage_7d_in_currency'), chg_30d=x.get('price_change_percentage_30d_in_currency')) for x in j]
    except Exception as e:
        out['errors'].append(f'coingecko memes: {e}')
    try:   # crowd mood, 0 = extreme fear, 100 = extreme greed
        j = get('https://api.alternative.me/fng/', limit=31)['data']
        out['fear_greed'] = dict(now=int(j[0]['value']), label=j[0]['value_classification'],
                                 week_ago=int(j[7]['value']) if len(j) > 7 else None, month_ago=int(j[30]['value']) if len(j) > 30 else None)
    except Exception as e:
        out['errors'].append(f'fear & greed: {e}')
    try:   # Reddit crypto mentions (r/CryptoCurrency, r/SatoshiStreetBets, ...) via ApeWisdom
        rows = get('https://apewisdom.io/api/v1.0/filter/all-crypto/page/1').get('results', [])
        def num(x, k):
            try: return int(float(x.get(k) or 0))
            except (TypeError, ValueError): return 0
        out['reddit'] = [dict(ticker=str(x.get('ticker', '')).upper(), name=x.get('name'), mentions=num(x, 'mentions'),
                              mentions_24h_ago=num(x, 'mentions_24h_ago')) for x in rows[:25]]
        if out['reddit']:
            append_history('crypto_mentions', {'date': today(), **{r['ticker']: r['mentions'] for r in out['reddit']}})
    except Exception as e:
        out['errors'].append(f'apewisdom crypto: {e}')
    save_json(out, 'crypto.json')
    print(f"crypto: trending {len(out.get('trending', []))}, memes {len(out.get('memes', []))}, reddit {len(out.get('reddit', []))}, errors {len(out['errors'])}")


if __name__ == '__main__':
    sys.exit(main())
