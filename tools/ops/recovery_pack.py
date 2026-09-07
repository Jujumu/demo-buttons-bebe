#!/usr/bin/env python3
"""Explicit encrypted recovery pack; no service stops, network transfer, or restores."""
from contextlib import closing
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import tarfile
import tempfile
import time
from urllib.parse import quote
from recovery_policy import (MAX_MEMBERS, MAX_FILE, MAX_DATABASE, MAX_TOTAL, MAX_MANIFEST,
    allowed, plan_entries, load_plan, open_parent, open_regular, hash_fd, fingerprint, private_directory)


def command(*args):
    result = subprocess.run(args, capture_output=True, timeout=180)
    if result.returncode: raise RuntimeError('Recovery cryptography command failed')
    return result.stdout


def metadata(path, kind, st):
    return {'path':path, 'kind':kind, 'mode':stat.S_IMODE(st.st_mode), 'uid':st.st_uid, 'gid':st.st_gid}


def file_snapshot(source, destination, attempts=3):
    for _ in range(attempts):
        fd = open_regular(source)
        try:
            before = os.fstat(fd)
            digest, size = hash_fd(fd)
            os.lseek(fd, 0, os.SEEK_SET)
            copied = hashlib.sha256(); count = 0
            with destination.open('wb') as output:
                os.chmod(destination, 0o600)
                while chunk := os.read(fd, 1024*1024):
                    count += len(chunk)
                    if count > MAX_FILE: raise ValueError('File exceeds size limit')
                    copied.update(chunk); output.write(chunk)
                output.flush(); os.fsync(output.fileno())
            after_digest, after_size = hash_fd(fd)
            check = open_regular(source)
            try: current = os.fstat(check)
            finally: os.close(check)
            if (fingerprint(before) == fingerprint(os.fstat(fd)) == fingerprint(current)
                    and digest == copied.hexdigest() == after_digest and size == count == after_size):
                return {**metadata(source,'file',before), 'sha256':digest, 'bytes':size, 'consistency':'stable-individual-file'}
        finally: os.close(fd)
        destination.unlink(missing_ok=True)
    raise RuntimeError('Source changed during bounded capture')


def tree_inventory(source):
    parent, name = open_parent(source)
    try: root_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    finally: os.close(parent)
    result = []
    def walk(fd, path):
        result.append(metadata(path, 'directory', os.fstat(fd)))
        if len(result) > MAX_MEMBERS: raise ValueError('Too many recovery members')
        for name in sorted(os.listdir(fd)):
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            child = path+'/'+name
            if stat.S_ISDIR(st.st_mode):
                sub = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try: walk(sub, child)
                finally: os.close(sub)
            elif stat.S_ISREG(st.st_mode):
                result.append(metadata(child, 'file', st))
                if len(result) > MAX_MEMBERS: raise ValueError('Too many recovery members')
            else: raise ValueError('Trees cannot contain links or special files')
    try: walk(root_fd, source)
    finally: os.close(root_fd)
    return result


def database_snapshot(source, destination):
    fd = open_regular(source)
    before = os.fstat(fd)
    if before.st_size > MAX_DATABASE: os.close(fd); raise ValueError('Database too large')
    deadline = time.monotonic()+120
    def progress(_status, _remaining, total):
        if time.monotonic() > deadline or total*page_size > MAX_DATABASE: raise TimeoutError('Database snapshot bounded limit')
    try:
        with closing(sqlite3.connect('file:'+quote(source,safe='/')+'?mode=ro', uri=True, timeout=1)) as reader:
            page_size = reader.execute('PRAGMA page_size').fetchone()[0]
            with closing(sqlite3.connect(destination)) as writer:
                reader.backup(writer, pages=128, progress=progress, sleep=.05)
                if writer.execute('PRAGMA integrity_check').fetchall() != [('ok',)]: raise ValueError('Database integrity failed')
        check = open_regular(source)
        try:
            current = os.fstat(check)
            if (before.st_dev,before.st_ino) != (current.st_dev,current.st_ino): raise ValueError('Database replaced during snapshot')
        finally: os.close(check)
        os.chmod(destination,0o600)
        output = open_regular(str(destination))
        try: os.fsync(output); digest,size = hash_fd(output,MAX_DATABASE)
        finally: os.close(output)
        return {**metadata(source,'sqlite',before), 'sha256':digest,'bytes':size,'integrity':'ok','consistency':'independent-sqlite-backup'}
    finally: os.close(fd)


def capture(plan, directory, policy=allowed):
    entries = plan_entries(plan,policy)
    records = []; paths = set(); total = 0
    for entry in entries:
        source, kind = entry['path'], entry['kind']
        inventory = tree_inventory(source) if kind == 'tree' else [entry]
        for item in inventory:
            path = item['path']
            if path in paths: raise ValueError('Overlapping recovery entries')
            paths.add(path)
            if len(paths) > MAX_MEMBERS: raise ValueError('Too many recovery members')
            current_kind = item['kind']
            if current_kind == 'directory': record = dict(item)
            elif current_kind == 'symlink':
                parent,name = open_parent(path)
                try:
                    st = os.stat(name,dir_fd=parent,follow_symlinks=False)
                    target = os.readlink(name,dir_fd=parent)
                    canonical_target = os.path.normpath(os.path.join(os.path.dirname(path),target))
                    if not stat.S_ISLNK(st.st_mode) or canonical_target != item['target']: raise ValueError('Link target changed')
                    record = {**metadata(path,'symlink',st),'target':item['target'],'link_text':target}
                finally: os.close(parent)
            else:
                payload = 'payload-'+str(len(records)).zfill(6)
                destination = directory/payload
                record = database_snapshot(path,destination) if current_kind == 'sqlite' else file_snapshot(path,destination)
                record['payload'] = payload
                total += record['bytes']
                if total > MAX_TOTAL: raise ValueError('Recovery total size exceeded')
            record['captured_at'] = datetime.now(timezone.utc).isoformat()
            records.append(record)
        if kind == 'tree' and tree_inventory(source) != inventory:
            raise RuntimeError('Tree membership or metadata changed during capture')
    manifest = {'schema':1,'plan':plan,'records':records,
                'consistency':'Independent SQLite snapshots and stable individual files; not a global point-in-time snapshot.',
                'recovery_warning':'Do not replay uncertain sends, queued jobs, or start services automatically. WhatsApp auth may require re-pairing.'}
    encoded = json.dumps(manifest,sort_keys=True).encode()
    if len(encoded) > MAX_MANIFEST: raise ValueError('Manifest too large')
    (directory/'manifest.json').write_bytes(encoded)
    return manifest


def pack(plan, destination, certificate, policy=allowed):
    private_directory(destination)
    cert_fd = open_regular(certificate)
    try:
        cert_st = os.fstat(cert_fd)
        if cert_st.st_uid != os.geteuid() or cert_st.st_mode & 0o022: raise ValueError('Unprotected recipient certificate')
        cert_data = os.read(cert_fd, MAX_FILE+1)
        if len(cert_data)>MAX_FILE: raise ValueError('Recipient certificate too large')
    finally: os.close(cert_fd)
    with tempfile.TemporaryDirectory(prefix='.recovery-private-',dir=destination) as tmp:
        root = Path(tmp); cert = root/'recipient.pem'; cert.write_bytes(cert_data)
        command('openssl','x509','-in',str(cert),'-noout','-checkend','86400')
        der = command('openssl','x509','-in',str(cert),'-outform','DER')
        if hashlib.sha256(der).hexdigest() != plan['recipient_sha256']: raise ValueError('Recipient fingerprint mismatch')
        content = root/'content'; content.mkdir(mode=0o700)
        manifest = capture(plan,content,policy)
        archive = root/'recovery.tar'
        with tarfile.open(archive,'w',format=tarfile.USTAR_FORMAT) as tar:
            for path in sorted(content.iterdir()): tar.add(path,arcname=path.name,recursive=False)
        encrypted = root/'recovery.cms'
        command('openssl','cms','-encrypt','-binary','-aes-256-gcm','-outform','DER','-in',str(archive),'-out',str(encrypted),str(cert))
        fd = open_regular(str(encrypted))
        try: os.fsync(fd); digest,size = hash_fd(fd,MAX_TOTAL+MAX_MANIFEST+32*1024*1024)
        finally: os.close(fd)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        target = destination/('recovery-'+stamp+'-'+digest[:12]+'.cms')
        os.link(encrypted,target)  # exclusive publish, no overwrite
        receipt = {'created_at':stamp,'class':'independent-recovery-pack','members':len(manifest['records']),
                   'ciphertext_sha256':digest,'ciphertext_bytes':size,'verification':'encrypted-not-yet-restored'}
        with target.with_suffix('.json').open('x') as stream:
            json.dump(receipt,stream);stream.flush();os.fsync(stream.fileno())
        fd = os.open(destination,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
        return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--destination',type=Path,default=Path('/opt/buttonsbebe/backups/recovery'))
    parser.add_argument('--certificate',type=Path,default=Path('/etc/buttonsbebe-backup-recipient.pem'))
    args = parser.parse_args();os.umask(0o077)
    if os.geteuid()!=0: raise SystemExit('Run pack as root on the reviewed VPS')
    try: print(json.dumps(pack(load_plan(args.plan),args.destination,args.certificate)))
    except Exception as error: raise SystemExit(f'Recovery pack failed: {type(error).__name__}; no private contents printed') from None

if __name__ == '__main__': main()
