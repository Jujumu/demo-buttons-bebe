#!/usr/bin/env python3
"""Bind only the reviewed PM2 receiving app to loopback after auth proxy proof.

Never changes env or invokes a business mutation. Source backups are private.
An explicit rollback acknowledgement is required because the old source may
reopen an unauthenticated financial service; failures never do that silently.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ORIGIN = 'https://support.buttonsbebe.com:8443'
BACKUPS = Path('/opt/buttonsbebe/backups')
OLD_BIND = 'app.listen(PORT, () => {'
NEW_BIND = 'app.listen(PORT, "127.0.0.1", () => {'


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode: raise RuntimeError('Reviewed operations command failed')
    return result.stdout


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def bind_local(source):
    if source.count(NEW_BIND) == 1 and OLD_BIND not in source: return source
    if source.count(OLD_BIND) != 1 or NEW_BIND in source:
        raise ValueError('Reviewed listen call changed')
    return source.replace(OLD_BIND, NEW_BIND)


def process(name, expected_pid=None):
    # PM2 JSON contains environment values. Keep it in memory and return only
    # the exact metadata necessary for this operation; never print the JSON.
    items = json.loads(run('pm2','jlist'))
    matched = [item for item in items if item.get('name') == name]
    if len(matched) != 1: raise ValueError('Named PM2 process is not unique')
    item = matched[0]
    pid = item.get('pid')
    if not isinstance(pid,int) or pid <= 0 or (expected_pid is not None and pid != expected_pid):
        raise ValueError('PM2 process changed since review')
    source = Path(item['pm2_env']['pm_exec_path'])
    if source.name != 'server.js' or source.is_symlink(): raise ValueError('Unexpected receiving entrypoint')
    stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    return {'pid':pid,'start_ticks':stat[19],'source':source}


def probe_proxy(cookie_file):
    if cookie_file.is_symlink() or cookie_file.stat().st_uid != 0 or cookie_file.stat().st_mode & 0o077:
        raise ValueError('Verification cookie must be in a private root-owned regular file')
    cookie = cookie_file.read_text().strip()
    if not cookie or '\n' in cookie or '\r' in cookie: raise ValueError('Invalid verification cookie file')
    url = ORIGIN + '/api/tracking-stats'  # reviewed aggregate-only GET
    try:
        urllib.request.urlopen(url,timeout=10)
    except urllib.error.HTTPError as error:
        if error.code != 401: raise RuntimeError('Proxy unauthenticated API gate not verified')
    else:
        raise RuntimeError('Proxy allowed unauthenticated aggregate request')
    request = urllib.request.Request(url, headers={'Cookie':cookie})
    with urllib.request.urlopen(request,timeout=10) as response:
        if response.status != 200 or 'application/json' not in response.headers.get('Content-Type',''):
            raise RuntimeError('Authenticated proxy aggregate probe failed')
        # Deliberately do not retrieve or log application response bodies.


def loopback_listener():
    rows = run('ss','-H','-ltnp').splitlines()
    addresses = [row.split()[3].rsplit(':',1)[0].strip('[]') for row in rows
                 if len(row.split())>3 and row.split()[3].rsplit(':',1)[-1]=='3210']
    return bool(addresses) and all(address in ('127.0.0.1','::1') for address in addresses)


def replace_file(source, content):
    fd, name = tempfile.mkstemp(prefix='.receiving-reviewed-',suffix='.js',dir=source.parent)
    candidate = Path(name)
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        candidate.chmod(source.stat().st_mode & 0o777)
        run('node','--check',str(candidate))
        os.replace(candidate,source)
    finally:
        candidate.unlink(missing_ok=True)


def apply(name,pid,start_ticks,expected_sha,cookie_file):
    info = process(name,pid)
    source = info['source']
    if info['start_ticks'] != start_ticks or sha(source) != expected_sha:
        raise ValueError('Process identity or source changed since review')
    rewritten = bind_local(source.read_text())
    probe_proxy(cookie_file)  # must succeed before changing the bind/restarting
    if rewritten == source.read_text():
        if not loopback_listener(): raise RuntimeError('Source is local but process still public; review restart')
        print('Receiving already contained; no changes')
        return
    backup = BACKUPS / ('receiving-bind-' + time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
    backup.mkdir(mode=0o700,parents=True,exist_ok=False)
    shutil.copy2(source,backup/'server.js')
    metadata = {'process_name':name,'source':str(source),'previous_sha256':expected_sha,
                'contained_sha256':hashlib.sha256(rewritten.encode()).hexdigest()}
    (backup/'metadata.json').write_text(json.dumps(metadata)+'\n')
    # Re-check after proxy requests/backup to refuse a concurrent replacement.
    if process(name,pid)['start_ticks'] != start_ticks or sha(source) != expected_sha:
        raise ValueError('Concurrent process/source change; service untouched')
    replace_file(source,rewritten)
    run('pm2','restart',name)  # deliberately omit --update-env; preserve existing env
    for attempt in range(30):
        if loopback_listener(): break
        if attempt == 29: raise RuntimeError('Loopback listener not ready; source retained contained')
        time.sleep(.5)
    probe_proxy(cookie_file)
    print(json.dumps({'status':'contained','backup':str(backup),'source_sha256':sha(source)}))


def rollback(backup,acknowledge_public_reopen):
    if not acknowledge_public_reopen:
        raise ValueError('Rollback may reopen unauthenticated service; require explicit alternative-containment review')
    if backup.parent != BACKUPS or not backup.name.startswith('receiving-bind-') or backup.is_symlink():
        raise ValueError('Invalid receiving backup')
    metadata = json.loads((backup/'metadata.json').read_text())
    info = process(metadata['process_name'])
    source = info['source']
    if str(source) != metadata['source'] or sha(source) != metadata['contained_sha256']:
        raise ValueError('Source changed after containment; refusing stale rollback')
    if sha(backup/'server.js') != metadata['previous_sha256']: raise ValueError('Backup checksum mismatch')
    replace_file(source,(backup/'server.js').read_text())
    run('pm2','restart',metadata['process_name'])
    print('Original binding restored under explicit operator acknowledgement')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    app=sub.add_parser('apply')
    app.add_argument('--process-name',required=True);app.add_argument('--expected-pid',required=True,type=int)
    app.add_argument('--expected-start-ticks',required=True);app.add_argument('--expected-source-sha256',required=True)
    app.add_argument('--proxy-cookie-file',required=True,type=Path)
    back=sub.add_parser('rollback');back.add_argument('--backup',required=True,type=Path)
    back.add_argument('--acknowledge-public-reopen',action='store_true')
    args=parser.parse_args();os.umask(0o077)
    if os.geteuid()!=0: raise SystemExit('Run only as root on the reviewed VPS')
    try:
        with open('/run/lock/buttonsbebe-receiving.lock','a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if args.command=='apply':apply(args.process_name,args.expected_pid,args.expected_start_ticks,args.expected_source_sha256,args.proxy_cookie_file)
            else:rollback(args.backup,args.acknowledge_public_reopen)
    except Exception as error:
        raise SystemExit(f'Receiving containment failed: {type(error).__name__}; no credentials printed') from None


if __name__=='__main__':main()
