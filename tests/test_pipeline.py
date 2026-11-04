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


def test_failed_source_still_writes_status_and_empty_history(tmp_path, monkeypatch):
    items = [{'symbol':'ABC', 'name':'Example', 'category':'Bonds', 'unit':'USD', 'kind':'fund'}]
    monkeypatch.setattr(pipeline, 'DATA', tmp_path)
    monkeypatch.setattr(pipeline, 'CATALOG', items)
    (tmp_path / 'raw').mkdir()
    def failed(item, full_history=False):
        raise RuntimeError('unavailable')
    monkeypatch.setattr(pipeline, 'fetch', failed)
    pipeline.run()
    status = json.loads((tmp_path / 'status.json').read_text())
    assert status['items'] == 0
    assert status['sources'] == [{'name':'ABC', 'ok':False, 'count':0}]
    assert not list((tmp_path / 'raw').glob('*/*.gz'))
    assert list(csv.DictReader((tmp_path / 'history.csv').open())) == []


def test_incremental_raw_retains_earlier_source_history(tmp_path, monkeypatch):
    item = {'symbol':'ABC', 'name':'Example', 'category':'Bonds', 'unit':'USD', 'kind':'fund'}
    monkeypatch.setattr(pipeline, 'DATA', tmp_path)
    monkeypatch.setattr(pipeline, 'CATALOG', [item])
    for day in ('2026-01-01', '2026-01-02'):
        (tmp_path/'raw'/day).mkdir(parents=True)
    (tmp_path/'raw'/'2026-01-01'/'ABC.json.gz').write_bytes(gzip.compress(payload()))
    new = json.loads(payload())
    result = new['chart']['result'][0]
    result['timestamp'] = [1609632000]
    result['indicators']['quote'][0] = {'close':[15], 'high':[16], 'low':[14]}
    (tmp_path/'raw'/'2026-01-02'/'ABC.json.gz').write_bytes(gzip.compress(json.dumps(new).encode()))
    pipeline.build()
    history = list(csv.DictReader((tmp_path/'history.csv').open()))
    source = list(csv.DictReader((tmp_path/'source-history.csv').open()))
    assert [float(x['close']) for x in history] == [12, 15]
    assert [float(x['close']) for x in source] == [10, 12, 15]


def test_committed_history_is_reproducible_from_raw(tmp_path, monkeypatch):
    import shutil
    repository_data = pipeline.DATA
    expected = {name: (repository_data/name).read_bytes() for name in ('history.csv', 'source-history.csv')}
    shutil.copytree(repository_data/'raw', tmp_path/'raw')
    monkeypatch.setattr(pipeline, 'DATA', tmp_path)
    pipeline.build()
    for name, contents in expected.items():
        assert (tmp_path/name).read_bytes() == contents


def test_move_rejects_unusable_daily_high_low():
    item = {'symbol':'^MOVE', 'name':'U.S. Treasury volatility (MOVE)', 'category':'Market gauges', 'unit':'index points', 'kind':'index'}
    source = json.loads(payload())
    source['chart']['result'][0]['indicators']['quote'][0]['high'] = [0, 13]
    source['chart']['result'][0]['indicators']['quote'][0]['low'] = [0, None]
    rows = pipeline.parse(json.dumps(source).encode(), item, '2026-01-01')
    assert (rows[0]['high'], rows[0]['low'], rows[0]['close']) == (None, None, 10)
    assert (rows[1]['high'], rows[1]['low']) == (13, None)
