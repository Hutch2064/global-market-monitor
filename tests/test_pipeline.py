import csv, gzip, json
from pathlib import Path
import pytest
import pipeline
from issue import report


def payload(closes=(10, 12), granularity='1d'):
    return json.dumps({'chart': {'result': [{'meta': {'exchangeTimezoneName': 'UTC', 'dataGranularity': granularity}, 'timestamp': [1609459200, 1609545600], 'indicators': {'quote': [{'close': list(closes), 'high': [11, 13], 'low': [9, 11]}]}}]}}).encode()


def test_yahoo_conversion_and_source_values():
    item = {'symbol':'ABC', 'name':'Example', 'category':'Bonds', 'unit':'USD', 'kind':'fund'}
    rows = pipeline.parse(payload(), item, '2026-01-01')
    assert rows[-1]['observation_date'] == '2021-01-02'
    assert (rows[-1]['close'], rows[-1]['high'], rows[-1]['low']) == (12, 13, 11)
    with pytest.raises(ValueError): pipeline.parse(payload(granularity='1mo'), item, '2026-01-01')


def test_rebuild_same_day_replaces_and_is_deterministic(tmp_path, monkeypatch):
    item = {'symbol':'ABC', 'name':'Example', 'category':'Bonds', 'unit':'USD', 'kind':'fund'}
    monkeypatch.setattr(pipeline, 'DATA', tmp_path)
    monkeypatch.setattr(pipeline, 'CATALOG', [item])
    folder = tmp_path / 'raw' / '2026-01-01'
    folder.mkdir(parents=True)
    path = folder / 'ABC.json.gz'
    path.write_bytes(gzip.compress(payload()))
    pipeline.build()
    first = (tmp_path/'history.csv').read_bytes()
    pipeline.build()
    assert (tmp_path/'history.csv').read_bytes() == first
    path.write_bytes(gzip.compress(payload((10, 14))))
    pipeline.build()
    rows = list(csv.DictReader((tmp_path/'history.csv').open()))
    assert len(rows) == 1 and float(rows[0]['close']) == 14
    path.unlink()
    pipeline.build()
    assert list(csv.DictReader((tmp_path/'history.csv').open())) == []


def test_issue_ranks_absolute_move_and_new_gone():
    rows = [dict(date='2026-01-01',item_id='A',item='Alpha',close='100',unit='USD'),dict(date='2026-01-01',item_id='B',item='Beta',close='20',unit='USD'),dict(date='2026-01-02',item_id='A',item='Alpha',close='110',unit='USD'),dict(date='2026-01-02',item_id='C',item='Gamma',close='50',unit='USD')]
    text = report(rows, '2026-01-02')
    assert 'Alpha' in text and '+10.00%' in text
    assert 'Appeared: C' in text and 'Disappeared: B' in text
