#!/usr/bin/env python3
"""Guarded containment for three reviewed listeners; never restores public binds."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

BACKUPS = Path('/opt/buttonsbebe/backups')
SERVICES = {
    'hermes': ('buttonsbebe-hermes-dashboard.service', 9119, 'https://hermes.buttonsbebe.com/'),
    'exchange': ('exchange-proxy.service', 4100, 'https://exchange.buttonsbebe.com/'),
}


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode: raise RuntimeError('Reviewed containment command failed')
    return result.stdout


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(pid):
    proc = Path('/proc') / str(pid)
    return (proc/'stat').read_text().rsplit(')',1)[1].split()[19]


def service_info(kind, expected_pid=None):
    unit = SERVICES[kind][0]
    props = dict(line.split('=',1) for line in run('systemctl','show',unit,'-p','MainPID','-p','FragmentPath','-p','DropInPaths').splitlines())
    pid = int(props['MainPID'])
    if pid <= 0 or (expected_pid is not None and pid != expected_pid) or props['DropInPaths']:
        raise ValueError('Service process or drop-ins changed')
    fragment = Path(props['FragmentPath'])
    if fragment.is_symlink() or not fragment.is_file(): raise ValueError('Unexpected unit file')
    source = fragment
    if kind == 'exchange':
        proc = Path('/proc') / str(pid)
        args = (proc/'cmdline').read_bytes().decode().split('\0')
        entries = [arg for arg in args if arg.endswith('.js')]
        if len(entries) != 1: raise ValueError('Unexpected exchange command')
        source = Path(entries[0])
        if not source.is_absolute(): source = (proc/'cwd').resolve()/source
        if source.name != 'server.js' or source.is_symlink() or not source.is_file():
            raise ValueError('Unexpected exchange source')
    return {'pid':pid, 'ticks':identity(pid), 'unit':fragment, 'source':source}


def rewrite(kind, content):
    old, new = ('--host 0.0.0.0', '--host 127.0.0.1') if kind == 'hermes' else (
        'server.listen(cfg.PORT, () => {', 'server.listen(cfg.PORT, "127.0.0.1", () => {')
    if content.count(old) != 1 or new in content: raise ValueError('Reviewed bind expression changed')
    if kind == 'hermes':
        lines = [line for line in content.splitlines() if old in line]
        if len(lines) != 1 or not lines[0].startswith('ExecStart='):
            raise ValueError('Host expression outside service ExecStart')
    return content.replace(old,new)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None


def probe(url, header_file=None):
    headers = {}
    if header_file:
        st = header_file.stat()
        if header_file.is_symlink() or not header_file.is_file() or st.st_uid != 0 or st.st_mode & 0o077:
            raise ValueError('Proxy authorization file must be private and root owned')
        value = header_file.read_text().strip()
        if not value or '\r' in value or '\n' in value: raise ValueError('Invalid authorization header')
        headers['Authorization'] = value
    request = urllib.request.Request(url, method='HEAD', headers=headers)
    try: response = urllib.request.build_opener(NoRedirect()).open(request, timeout=10)
    except urllib.error.HTTPError as error: response = error
    with response:
        if response.status >= 500: raise RuntimeError('Proxy unavailable before or after containment')
        # HEAD only, no body or credential output. Compare exact status/type.
        return response.status, response.headers.get('Content-Type','')


def listener(port, expected_pid=None):
    rows = [row for row in run('ss','-H','-ltnp').splitlines()
            if len(row.split()) > 3 and row.split()[3].rsplit(':',1)[-1] == str(port)]
    if not rows: return False
    for row in rows:
        host = row.split()[3].rsplit(':',1)[0].strip('[]')
        pids = set(map(int,re.findall(r'pid=(\d+)',row)))
        if host not in ('127.0.0.1','::1') or (expected_pid is not None and pids != {expected_pid}): return False
    return True


def replace(source, content, kind):
    with tempfile.TemporaryDirectory(prefix='.contained-',dir=source.parent) as folder:
        candidate = Path(folder)/source.name
        candidate.write_text(content)
        candidate.chmod(source.stat().st_mode & 0o777)
        if kind == 'hermes': run('systemd-analyze','verify',str(candidate))
        else: run('node','--check',str(candidate))
        with candidate.open('rb') as stream: os.fsync(stream.fileno())
        os.replace(candidate,source)
        fd = os.open(source.parent,os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)


def apply(kind,pid,ticks,unit_sha,source_sha,header_file=None):
    unit,port,url = SERVICES[kind]
    def checked():
        info = service_info(kind,pid)
        if info['ticks'] != ticks or sha(info['unit']) != unit_sha or sha(info['source']) != source_sha:
            raise ValueError('Reviewed process or file checksum changed')
        return info
    info = checked()
    content = rewrite(kind, info['source'].read_text())
    before = probe(url,header_file)
    local_before = probe(f'http://127.0.0.1:{port}/')
    backup = BACKUPS / (kind+'-bind-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
    backup.mkdir(parents=True,mode=0o700,exist_ok=False)
    backup.chmod(0o700)
    shutil.copy2(info['source'],backup/info['source'].name)
    (backup/'metadata.json').write_text(json.dumps({'unit':unit,'source':str(info['source']),
        'old_sha256':source_sha,'contained_sha256':hashlib.sha256(content.encode()).hexdigest(),
        'pid':pid,'start_ticks':ticks})+'\n')
    for file in backup.iterdir():
        with file.open('rb') as stream: os.fsync(stream.fileno())
    fd = os.open(backup,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
    checked() # Recheck after network I/O and backup, immediately before mutation.
    replace(info['source'],content,kind)
    if kind == 'hermes': run('systemctl','daemon-reload')
    run('systemctl','restart',unit)
    for attempt in range(40):
        current = service_info(kind)
        if listener(port,current['pid']): break
        if attempt == 39: raise RuntimeError('Local listener not ready; contained source retained')
        time.sleep(.5)
    if probe(url,header_file) != before or probe(f'http://127.0.0.1:{port}/') != local_before:
        raise RuntimeError('Proxy response changed; contained source retained for operator review')
    print(json.dumps({'status':'contained','service':unit,'backup':str(backup)}))


def stop_preview(pid,ticks):
    proc = Path('/proc') / str(pid)
    if identity(pid) != ticks: raise ValueError('Preview process identity changed')
    args = (proc/'cmdline').read_bytes().decode().split('\0')
    if args[-1] == '': args.pop()
    if len(args) != 4 or not Path(args[0]).name.startswith('python') or args[1:] != ['-m','http.server','8099']:
        raise ValueError('Not the exact reviewed Python preview command')
    if not str((proc/'cwd').readlink()).endswith(' (deleted)'):
        raise ValueError('Preview cwd is no longer deleted')
    rows = [line for line in run('ss','-H','-ltnp').splitlines()
            if len(line.split()) > 3 and line.split()[3].rsplit(':',1)[-1]=='8099']
    if not rows or any(set(map(int,re.findall(r'pid=(\d+)',line)))!={pid} for line in rows):
        raise ValueError('Preview listener owner changed')
    fd = os.pidfd_open(pid)
    try:
        if identity(pid) != ticks: raise ValueError('Preview PID reused')
        signal.pidfd_send_signal(fd,signal.SIGTERM)
    finally: os.close(fd)
    for attempt in range(40):
        rows = run('ss','-H','-ltnp').splitlines()
        if not any(len(row.split())>3 and row.split()[3].rsplit(':',1)[-1]=='8099' for row in rows):
            print('Reviewed deleted-directory preview stopped; no replacement launched');return
        time.sleep(.25)
    raise RuntimeError('Preview listener persists; no other process signaled')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind',choices=(*SERVICES,'preview'))
    parser.add_argument('--expected-pid',type=int,required=True)
    parser.add_argument('--expected-start-ticks',required=True)
    parser.add_argument('--expected-unit-sha256')
    parser.add_argument('--expected-source-sha256')
    parser.add_argument('--proxy-authorization-file',type=Path)
    args=parser.parse_args();os.umask(0o077)
    if os.geteuid()!=0: raise SystemExit('Run only as root on the reviewed VPS')
    try:
        with open('/run/lock/buttonsbebe-listeners.lock','a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if args.kind=='preview': stop_preview(args.expected_pid,args.expected_start_ticks)
            else:
                if not args.expected_unit_sha256 or not args.expected_source_sha256: raise ValueError('Both checksums required')
                apply(args.kind,args.expected_pid,args.expected_start_ticks,args.expected_unit_sha256,args.expected_source_sha256,args.proxy_authorization_file)
    except Exception as error:
        raise SystemExit(f'Containment failed: {type(error).__name__}; source retained, no automatic public reopen') from None


if __name__=='__main__': main()
