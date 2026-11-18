"""Operate independent SOL E1 comparison and human-review alerts, never orders."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.sol_live import HOME,CONTROLLER,OUTBOX,Worker,snapshot

LABEL='com.renshangh.sol-e1-live-comparison'


def agent_document(root,python,home):
    logs=home/'Library/Logs/TradingDeskSOL'
    return dict(Label=LABEL,ProgramArguments=[python,str(root/'scripts/run_sol_live.py'),'--launchd-worker'],
        WorkingDirectory=str(home),RunAtLoad=True,KeepAlive=True,ThrottleInterval=15,
        StandardOutPath=str(logs/'COMPARISON.log'),StandardErrorPath=str(logs/'COMPARISON.log'),
        EnvironmentVariables={'PYTHONUNBUFFERED':'1'})


def install():
    if sys.platform!='darwin':raise ValueError('Use a local process supervisor on this platform')
    (Path.home()/'Library/Logs/TradingDeskSOL').mkdir(parents=True,exist_ok=True)
    plist=Path.home()/'Library/LaunchAgents'/(LABEL+'.plist');plist.parent.mkdir(parents=True,exist_ok=True)
    document=agent_document(ROOT,sys.executable,Path.home())
    if plist.exists() and plistlib.loads(plist.read_bytes())!=document:
        raise ValueError('Existing SOL worker registration differs; review before replacing')
    if not plist.exists():plist.write_bytes(plistlib.dumps(document))
    domain='gui/'+str(os.getuid())
    subprocess.run(['launchctl','enable',domain+'/'+LABEL],check=True,capture_output=True)
    if subprocess.run(['launchctl','print',domain+'/'+LABEL],capture_output=True).returncode:
        subprocess.run(['launchctl','bootstrap',domain,str(plist)],check=True,capture_output=True)
    return dict(installed=True,label=LABEL,orders_enabled=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--enable',action='store_true');p.add_argument('--status',action='store_true')
    p.add_argument('--install-agent',action='store_true');p.add_argument('--launchd-worker',action='store_true')
    p.add_argument('--alerts',action='store_true',help='Read undelivered proposals without marking them delivered')
    p.add_argument('--notified',nargs='+',help='Mark exact proposal IDs only after notifying the owner')
    p.add_argument('--decision',metavar='ID');p.add_argument('--approve',action='store_true');p.add_argument('--reject',action='store_true')
    a=p.parse_args()
    if a.decision:
        if a.approve==a.reject:p.error('Choose exactly one paper-review decision')
        OUTBOX.decide(a.decision,'approved' if a.approve else 'rejected')
        print(json.dumps(dict(recorded=True,orders_enabled=False,fill_created=False)));return
    if a.approve or a.reject:p.error('A proposal ID is required')
    if a.notified:OUTBOX.acknowledge(a.notified);print(json.dumps(dict(recorded=True)));return
    if a.alerts:
        d=snapshot();d['proposals']=OUTBOX.list(unnotified=True)
        # Keep heartbeat context bounded; full state remains on the dashboard.
        d={k:({x:v for x,v in d[k].items() if x in ('health','error','approval_error','minute_end','heartbeat','enabled','session','quote_fresh','orders_enabled')} if k in ('btc','sol') else d[k]) for k in d}
        for name in ('btc','sol'):
            d[name]['session']={k:v for k,v in (d[name].get('session') or {}).items() if k in ('id','start')}
        print(json.dumps(d));return
    if a.status:print(json.dumps(snapshot()));return
    if a.enable:OUTBOX.open().close();CONTROLLER.control('start')
    if a.install_agent:print(json.dumps(install()));return
    supervision=None
    if a.launchd_worker:
        if sys.platform!='darwin' or os.getppid()!=1:raise ValueError('Login worker requires launchd ownership')
        supervision=dict(mode='launchd',label=LABEL,login_startup_verified=True,note='Launchd owned; logout/reboot not tested')
    Worker(supervision=supervision).run()


if __name__=='__main__':main()
