"""Login supervision wiring and ownership, without touching system services."""
import fcntl
import os
from pathlib import Path
import plistlib
import sys
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts import run_btc_live as service
from trading_desk import btc_live,btc_data


def test_agent_boots_from_internal_home_and_retains_external_project():
    home=Path('/Users/example');external=Path('/Volumes/External Drive/repo')
    doc=service.agent_document(external,'/usr/local/bin/python3',home)
    assert doc['WorkingDirectory']==str(home)
    assert doc['ProgramArguments']==['/usr/local/bin/python3',str(external/'scripts/run_btc_live.py'),'--launchd-worker']
    assert doc['RunAtLoad'] and doc['KeepAlive'] and doc['ThrottleInterval']==15
    assert doc['StandardOutPath'].startswith(str(home/'Library/Logs'))


def prepare(monkeypatch,tmp_path):
    home=tmp_path/'home';root=tmp_path/'external-repo'
    monkeypatch.setattr(service.Path,'home',classmethod(lambda cls:home))
    monkeypatch.setattr(service,'ROOT',root)
    monkeypatch.setattr(service,'LIVE',root/'live')
    monkeypatch.setattr(service.sys,'platform','darwin')
    path=home/'Library/LaunchAgents'/(service.LABEL+'.plist')
    path.parent.mkdir(parents=True)
    expected=service.agent_document(root,sys.executable,home)
    return path,expected


def test_only_exact_previous_registration_is_migrated(monkeypatch,tmp_path):
    path,expected=prepare(monkeypatch,tmp_path)
    old=dict(expected,ProgramArguments=expected['ProgramArguments'][:-1])
    before=plistlib.dumps(old);path.write_bytes(before);calls=[]
    def run(args,**kwargs):
        calls.append(args)
        code=1 if args[1]=='print' and sum(c[1]=='print' for c in calls)>1 else 0
        return SimpleNamespace(returncode=code)
    monkeypatch.setattr(service.subprocess,'run',run)
    assert service.install()['installed']
    assert plistlib.loads(path.read_bytes())==expected
    assert path.with_suffix('.plist.before-launchd-worker').read_bytes()==before
    assert [a[1] for a in calls]==['print','bootout','enable','print','bootstrap']


def test_existing_current_registration_is_idempotent(monkeypatch,tmp_path):
    path,expected=prepare(monkeypatch,tmp_path);before=plistlib.dumps(expected);path.write_bytes(before)
    calls=[]
    monkeypatch.setattr(service.subprocess,'run',lambda args,**kw:(calls.append(args) or SimpleNamespace(returncode=0)))
    assert service.install()['installed']
    assert path.read_bytes()==before
    assert [a[1] for a in calls]==['enable','print']


def test_unrelated_registration_is_never_overwritten(monkeypatch,tmp_path):
    path,expected=prepare(monkeypatch,tmp_path)
    other=dict(expected,ProgramArguments=['/different/application'])
    before=plistlib.dumps(other);path.write_bytes(before)
    monkeypatch.setattr(service.subprocess,'run',lambda *a,**kw:pytest.fail('Must not touch unrelated service'))
    with pytest.raises(ValueError,match='differs'):service.install()
    assert path.read_bytes()==before


def test_supervision_is_published_only_after_exclusive_worker_ownership(tmp_path,monkeypatch):
    claimed=dict(mode='launchd',login_startup_verified=True)
    worker=btc_live.Worker(root=tmp_path,supervision=claimed)
    with (tmp_path/'worker.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(RuntimeError,match='already owns'):worker.run()
    assert not (tmp_path/'SUPERVISION.json').exists()
    monkeypatch.setattr(worker,'tick',lambda:None)
    def stop(seconds):raise KeyboardInterrupt
    monkeypatch.setattr(btc_live.time,'sleep',stop)
    with pytest.raises(KeyboardInterrupt):worker.run()
    actual=btc_data.read(tmp_path/'SUPERVISION.json')
    assert actual['mode']=='launchd' and actual['worker_pid']==os.getpid()
    assert actual['login_startup_verified'] is True


@pytest.mark.parametrize('shutdown',[KeyboardInterrupt,SystemExit])
def test_manual_supervisor_reaps_child_on_shutdown(tmp_path,monkeypatch,shutdown):
    monkeypatch.setattr(service,'LIVE',tmp_path)
    changes=[]
    monkeypatch.setattr(service.signal,'signal',lambda sig,handler:(changes.append(handler) or 'previous-handler'))
    class Child:
        stopped=False
        def wait(self,timeout=None):
            if timeout is None:raise shutdown
            assert self.stopped
            return 0
        def poll(self):return 0 if self.stopped else None
        def terminate(self):self.stopped=True
    child=Child()
    monkeypatch.setattr(service.subprocess,'Popen',lambda *a,**kw:child)
    with pytest.raises(shutdown):service.supervise()
    assert child.stopped and changes[-1]=='previous-handler'
