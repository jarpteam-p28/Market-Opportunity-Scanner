"""Shared helpers: config, dated folders, JSON/CSV io, Telegram."""
import os, json, datetime as dt
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
REPORTS = ROOT / 'reports'
HISTORY = DATA / 'history'


def load_config(path=None):
    with open(path or ROOT / 'config.yaml') as f:
        return yaml.safe_load(f)


def today():
    return os.environ.get('SCAN_DATE') or dt.date.today().isoformat()


def day_dir(date=None):
    d = DATA / (date or today())
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_json(obj, name, date=None):
    p = day_dir(date) / name
    with open(p, 'w') as f:
        json.dump(obj, f, indent=2, default=str)
    return p


def load_json(name, date=None, default=None):
    p = DATA / (date or today()) / name
    if not p.exists():
        return default
    with open(p) as f:
        return json.load(f)


def append_history(name, row: dict):
    """Append one dated row to data/history/<name>.csv (used for week-over-week buzz baselines)."""
    import pandas as pd
    HISTORY.mkdir(parents=True, exist_ok=True)
    p = HISTORY / f'{name}.csv'
    df = pd.DataFrame([row])
    if p.exists():
        old = pd.read_csv(p)
        old = old[old['date'] != row['date']]
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(p, index=False)
    return p


def telegram(msg):
    tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not (tok and chat):
        print('[telegram not configured]\n' + msg)
        return
    import requests
    for cid in [c.strip() for c in chat.split(',') if c.strip()]:   # several people: "111,222"
        for i in range(0, len(msg), 3900):   # Telegram limit 4096 chars
            try:
                r = requests.post(f'https://api.telegram.org/bot{tok}/sendMessage',
                                  data={'chat_id': cid, 'text': msg[i:i + 3900], 'disable_web_page_preview': True}, timeout=20)
                if not r.ok:
                    print(f'telegram to ...{cid[-3:]} failed: {r.status_code}')
            except Exception as e:
                print(f'telegram to ...{cid[-3:]} failed: {e}')
