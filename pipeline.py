"""Fetch, archive and reproduce the daily tracker and source histories."""
import argparse, csv, gzip, json, os, shutil, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
CATALOG = json.loads((ROOT / 'catalog.json').read_text())
BY_ID = {x['symbol']: x for x in CATALOG}
COLUMNS = ['date', 'item_id', 'item', 'source', 'category', 'unit', 'kind', 'observation_date', 'close', 'high', 'low']


def safe_id(symbol):
    return quote(symbol, safe='')


def parse(raw, item, run_date):
    payload = json.loads(raw)
    result = payload['chart']['result'][0]
    if result['meta'].get('dataGranularity') != '1d':
        raise ValueError('source did not return daily data')
    timestamps = result['timestamp']
    quote_data = result['indicators']['quote'][0]
    zone = ZoneInfo(result['meta'].get('exchangeTimezoneName', 'UTC'))
    rows = []
    for i, timestamp in enumerate(timestamps):
        close = quote_data['close'][i]
        if close is None:
            continue
        values = {k: (quote_data.get(k) or [None] * len(timestamps))[i] for k in ('high', 'low')}
        if item['symbol'] == '^MOVE':
            values = {k: value if value is not None and value > 0 else None for k, value in values.items()}
        obs = datetime.fromtimestamp(timestamp, zone).date().isoformat()
        rows.append(dict(date=run_date, item_id=item['symbol'], item=item['name'], source='Yahoo Finance', category=item['category'], unit=item['unit'], kind=item['kind'], observation_date=obs, close=close, **values))
    if not rows:
        raise ValueError('no valid observations')
    return rows


def fetch(item, full_history=False):
    symbol = safe_id(item['symbol'])
    query = f'period1=0&period2={int(time.time()) + 86400}' if full_history else 'range=1mo'
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}&interval=1d&events=history'
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0 GlobalMarketMonitor/1.0'})
    last = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=35) as response:
                raw = response.read()
            parse(raw, item, '2000-01-01')
            return raw
        except Exception as exc:
            last = exc
            time.sleep(attempt + 1)
    raise last


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def build():
    history, observations = [], {}
    for folder in sorted((DATA / 'raw').glob('????-??-??')):
        for item in CATALOG:
            path = folder / (safe_id(item['symbol']) + '.json.gz')
            if not path.exists():
                continue
            rows = parse(gzip.decompress(path.read_bytes()), item, folder.name)
            history.append(rows[-1])
            for row in rows:
                observations[(row['item_id'], row['observation_date'])] = row
    history.sort(key=lambda row: (row['date'], row['item_id']))
    write_csv(DATA / 'history.csv', history)
    full = []
    for row in observations.values():
        row = dict(row)
        row['date'] = row['observation_date']
        full.append(row)
    full.sort(key=lambda row: (row['date'], row['item_id']))
    write_csv(DATA / 'source-history.csv', full)
    return history


def run():
    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    folder = DATA / 'raw' / day
    # A new symbol needs a full historical baseline. Check before replacing today.
    has_history = {item['symbol']: any((old / (safe_id(item['symbol']) + '.json.gz')).exists() for old in (DATA / 'raw').glob('????-??-??') if old.name != day) for item in CATALOG}
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch, item, not has_history[item['symbol']]): item for item in CATALOG}
        for future in as_completed(futures):
            item = futures[future]
            try:
                raw = future.result()
                (folder / (safe_id(item['symbol']) + '.json.gz')).write_bytes(gzip.compress(raw, mtime=0))
                results[item['symbol']] = {'name': item['symbol'], 'ok': True, 'count': 1}
            except Exception as exc:
                print('Source failed:', item['symbol'], str(exc), flush=True)
                results[item['symbol']] = {'name': item['symbol'], 'ok': False, 'count': 0}
    history = build()
    dates = sorted({x['date'] for x in history})
    today = {x['item_id'] for x in history if x['date'] == day}
    previous_dates = [d for d in dates if d < day]
    previous = {x['item_id'] for x in history if previous_dates and x['date'] == previous_dates[-1]}
    status = {'run_time': now.isoformat(), 'trigger': os.environ.get('GITHUB_EVENT_NAME', 'local'), 'first_run_date': dates[0] if dates else None, 'days_with_success': len(dates), 'items': len(today), 'new_today': sorted(today - previous), 'gone_today': sorted(previous - today), 'sources': [results[item['symbol']] for item in CATALOG]}
    (DATA / 'status.json').write_text(json.dumps(status, indent=2) + '\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['run', 'build'])
    args = parser.parse_args()
    DATA.mkdir(exist_ok=True)
    (DATA / 'raw').mkdir(exist_ok=True)
    run() if args.command == 'run' else build()
