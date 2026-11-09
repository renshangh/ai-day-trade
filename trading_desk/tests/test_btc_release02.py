"""Release integrity, independent alternatives and GET-only credentials."""
import hashlib
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk import btc_data,btc_lab


def test_read_only_credentials_keep_paper_requirement(monkeypatch,tmp_path):
    monkeypatch.setattr(btc_data,'ROOT',tmp_path)
    for key in ('ALPACA_API_KEY','ALPACA_API_SECRET','ALPACA_IS_PAPER'):monkeypatch.delenv(key,raising=False)
    with pytest.raises(ValueError,match='must be true'):btc_data.credentials()
    monkeypatch.setenv('ALPACA_IS_PAPER','true')
    with pytest.raises(ValueError,match='missing'):btc_data.credentials()
    (tmp_path/'.env').write_text('ALPACA_API_KEY="test-key"\nALPACA_API_SECRET="test-secret"\n')
    assert btc_data.credentials()=={'APCA-API-KEY-ID':'test-key','APCA-API-SECRET-KEY':'test-secret'}
    assert 'alpaca_range_paper' not in Path(btc_data.__file__).read_text()


def test_release02_preserves_baseline_and_verified_three_sequences():
    folder=btc_data.STORE/'releases/0.2'
    manifest=btc_data.read(folder/'MANIFEST.json')
    assert manifest['version']=='0.2' and manifest['baseline_version']=='0.1'
    assert set(manifest['run_ids'])=={'0.1','E1','E2'} and not manifest['orders_enabled']
    for name,digest in manifest['files_sha256'].items():
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,name
    proof=btc_data.read(folder/'REPRODUCTION.json')
    assert proof['reproduced'] and all(x['reproduced'] for x in proof['sequences'].values())
    assert proof['sequences']['E2']['net']==pytest.approx(4195.148015005418)
    baseline=btc_data.STORE/'releases/0.1/BTC_STRUCTURE_RELEASE_0.1.zip'
    assert baseline.read_bytes()==(folder/'baseline_release'/baseline.name).read_bytes()
    lab=btc_lab.Lab();s=lab.status()
    assert s['review_release']['version']=='0.2' and s['active_release']['version']=='0.1'
    for run in manifest['run_ids'].values():
        assert lab.release_for(run) is None or lab.release_for(run)['version']=='0.1'
        assert 'BTC_STRUCTURE_RELEASE_0.2.zip' in lab.detail(run)['exports']
        assert lab.export(run,'BTC_STRUCTURE_RELEASE_0.2.zip')==folder/'BTC_STRUCTURE_RELEASE_0.2.zip'
    with pytest.raises(ValueError):lab.export('20261109T122648Z-30-ab','BTC_STRUCTURE_RELEASE_0.2.zip')
