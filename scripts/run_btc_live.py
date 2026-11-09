"""Run or install the supervised BTC/USD comparison-only worker."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_live import CONTROLLER,LIVE,Worker

LABEL='com.renshangh.btc-live-comparison'


def supervise():
    LIVE.mkdir(parents=True,exist_ok=True)
    with (LIVE/'supervisor.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('A comparison supervisor already exists') from None
        def stop(signum,frame):raise SystemExit(0)
        previous=signal.signal(signal.SIGTERM,stop)
        try:
            while True:
                child=subprocess.Popen([sys.executable,str(ROOT/'scripts/run_btc_live.py')])
                try:child.wait()
                finally:
                    # Both SIGTERM and Ctrl-C must release the child's writer
                    # lock so the next supervisor can start cleanly.
                    if child.poll() is None:
                        child.terminate()
                        try:child.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            child.kill();child.wait(timeout=10)
                time.sleep(15)
        finally:signal.signal(signal.SIGTERM,previous)


def agent_document(root,python,home):
    logs=home/'Library/Logs/TradingDeskBTC'
    return dict(Label=LABEL,ProgramArguments=[python,str(root/'scripts/run_btc_live.py'),'--launchd-worker'],
        WorkingDirectory=str(home),RunAtLoad=True,KeepAlive=True,ThrottleInterval=15,
        StandardOutPath=str(logs/'COMPARISON.log'),StandardErrorPath=str(logs/'COMPARISON.log'),
        EnvironmentVariables={'PYTHONUNBUFFERED':'1'})


def install():
    if sys.platform!='darwin':raise ValueError('Use the worker directly under your process supervisor on this platform')
    LIVE.mkdir(parents=True,exist_ok=True)
    log_folder=Path.home()/'Library/Logs/TradingDeskBTC'
    log_folder.mkdir(parents=True,exist_ok=True)
    plist=Path.home()/'Library/LaunchAgents'/(LABEL+'.plist');plist.parent.mkdir(parents=True,exist_ok=True)
    document=agent_document(ROOT,sys.executable,Path.home())
    domain='gui/'+str(os.getuid())
    if plist.exists():
        previous=plistlib.loads(plist.read_bytes())
        if previous!=document:
            legacy=dict(document,ProgramArguments=document['ProgramArguments'][:-1])
            if previous!=legacy:raise ValueError('An existing worker registration differs; review before replacing')
            # Migrate only the exact registration installed by this script.
            backup=plist.with_suffix('.plist.before-launchd-worker')
            if not backup.exists():backup.write_bytes(plist.read_bytes())
            loaded=subprocess.run(['launchctl','print',domain+'/'+LABEL],capture_output=True)
            if loaded.returncode==0:
                subprocess.run(['launchctl','bootout',domain+'/'+LABEL],check=True,capture_output=True)
            plist.write_bytes(plistlib.dumps(document))
    else:plist.write_bytes(plistlib.dumps(document))
    subprocess.run(['launchctl','enable',domain+'/'+LABEL],check=True,capture_output=True)
    current=subprocess.run(['launchctl','print',domain+'/'+LABEL],capture_output=True)
    if current.returncode:
        result=subprocess.run(['launchctl','bootstrap',domain,str(plist)],capture_output=True,text=True)
        if result.returncode:raise RuntimeError('Worker registration failed; launchctl exit '+str(result.returncode))
    return dict(installed=True,label=LABEL,plist=str(plist))


def main():
    p=argparse.ArgumentParser();p.add_argument('--install-agent',action='store_true')
    p.add_argument('--enable',action='store_true');p.add_argument('--status',action='store_true')
    p.add_argument('--supervise',action='store_true')
    p.add_argument('--launchd-worker',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args()
    if args.enable:CONTROLLER.control('start')
    if args.install_agent:print(json.dumps(install()));return
    if args.status:print(json.dumps(CONTROLLER.status()));return
    if args.supervise:
        supervise();return
    supervision=None
    if args.launchd_worker:
        if sys.platform!='darwin' or os.getppid()!=1:
            raise ValueError('The launchd worker must be started by the registered login service')
        supervision=dict(mode='launchd',label=LABEL,login_startup_verified=True,
            note='Launchd started and owns the worker; no logout/reboot was performed for verification')
    Worker(supervision=supervision).run()


if __name__=='__main__':main()
