"""Create or update the dated report issue using the GitHub CLI."""
import csv, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from pipeline import DATA


def report(rows, day):
    dates = sorted({r['date'] for r in rows if r['date'] <= day})
    current = {r['item_id']: r for r in rows if r['date'] == day}
    earlier = [d for d in dates if d < day]
    old = {r['item_id']: r for r in rows if earlier and r['date'] == earlier[-1]}
    moves = []
    for key in current.keys() & old.keys():
        a, b = float(old[key]['close']), float(current[key]['close'])
        if a > 0 and b > 0:
            moves.append((abs(b/a-1), key, a, b, (b/a-1)*100))
    moves.sort(key=lambda x: (-x[0], x[1]))
    lines = ['## Largest movements', '', 'Ranked by absolute percentage change in close since the previous run; up to 10 items.', '']
    for _, key, a, b, pct in moves[:10]:
        lines.append(f'- {current[key]["item"]} ({key}): {a:.4f} → {b:.4f} {current[key]["unit"]} ({pct:+.2f}%)')
    if not moves:
        lines.append('No comparable movements yet.')
    lines += ['', '## Changes in coverage', '', 'Appeared: ' + (', '.join(sorted(current.keys()-old.keys())) or 'None'), 'Disappeared: ' + (', '.join(sorted(old.keys()-current.keys())) or 'None')]
    return '\n'.join(lines) + '\n'


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True).strip()


def main():
    day = datetime.now(timezone.utc).date().isoformat()
    title = f'Daily market report — {day}'
    with (DATA / 'history.csv').open() as f:
        body = report(list(csv.DictReader(f)), day)
    path = DATA / 'issue-body.tmp'
    path.write_text(body)
    try:
        issues = json.loads(gh('issue', 'list', '--state', 'all', '--limit', '200', '--json', 'number,title,state'))
        match = next((i for i in issues if i['title'] == title), None)
        if match:
            gh('issue', 'edit', str(match['number']), '--body-file', str(path))
            if match['state'] == 'CLOSED':
                gh('issue', 'reopen', str(match['number']))
        else:
            gh('issue', 'create', '--title', title, '--body-file', str(path))
        previous = sorted((i for i in issues if i['title'].startswith('Daily market report — ') and i['title'] < title and i['state'] == 'OPEN'), key=lambda x:x['title'])
        if previous:
            gh('issue', 'close', str(previous[-1]['number']))
    finally:
        path.unlink(missing_ok=True)

if __name__ == '__main__':
    main()
