#!/usr/bin/env python3
"""Decrypt to an isolated private directory and validate; never start services."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tarfile
import tempfile
from recovery_pack import command
from recovery_policy import (MAX_MEMBERS,MAX_MANIFEST,MAX_FILE,MAX_DATABASE,MAX_TOTAL,
    allowed,plan_entries,load_plan,open_regular,hash_fd,private_directory,canonical)


def approved_record(record, entries):
    if not isinstance(record,dict): raise ValueError('Invalid record')
    path = canonical(record.get('path'))
    kind = record.get('kind')
    if kind not in {'file','sqlite','directory','symlink'}: raise ValueError('Invalid record kind')
    for key in ('mode','uid','gid'):
        if type(record.get(key)) is not int or record[key]<0: raise ValueError('Invalid ownership metadata')
    if record['mode']>0o7777: raise ValueError('Invalid mode')
    for entry in entries:
        if entry['kind']=='tree' and kind in {'file','directory'} and (path==entry['path'] or path.startswith(entry['path']+'/')): return
        if path==entry['path'] and kind==entry['kind']:
            if kind=='symlink' and record.get('target')!=entry['target']: raise ValueError('Link target mismatch')
            return
    raise ValueError('Record outside exact approved plan')


def bounded_tar_headers(archive):
    """Reject extensions/links before tarfile can allocate PAX or GNU metadata."""
    count=0; total=0
    with archive.open('rb') as stream:
        while True:
            block=stream.read(512)
            if len(block)!=512: raise ValueError('Truncated tar header')
            if block==b'\0'*512:
                remainder=stream.read(32*1024+1)
                if len(remainder)>32*1024 or len(remainder)<512 or any(remainder): raise ValueError('Invalid tar trailer')
                return
            info=tarfile.TarInfo.frombuf(block,'utf-8','strict')
            if info.type not in {tarfile.REGTYPE,tarfile.AREGTYPE} or not re.fullmatch(r'manifest\.json|payload-[0-9]{6}',info.name):
                raise ValueError('Unsupported tar header')
            count+=1;total+=info.size
            limit=MAX_MANIFEST if info.name=='manifest.json' else MAX_DATABASE
            if info.size<0 or info.size>limit or count>MAX_MEMBERS+1 or total>MAX_TOTAL+MAX_MANIFEST:
                raise ValueError('Tar header limits exceeded')
            stream.seek(((info.size+511)//512)*512,1)


def validate_archive(archive, destination, expected_plan, policy=allowed):
    private_directory(destination)
    if any(destination.iterdir()): raise ValueError('Restore directory must be empty')
    entries = plan_entries(expected_plan,policy)
    if archive.stat().st_size > MAX_TOTAL+MAX_MANIFEST+32*1024*1024: raise ValueError('Archive too large')
    bounded_tar_headers(archive)
    with tarfile.open(archive,'r:') as tar:
        members = {}; total = 0
        for member in tar:
            if (not member.isfile() or not re.fullmatch(r'manifest\.json|payload-[0-9]{6}',member.name)
                    or member.name in members or member.size<0): raise ValueError('Unexpected archive member')
            maximum = MAX_MANIFEST if member.name=='manifest.json' else MAX_DATABASE
            if member.size>maximum: raise ValueError('Member too large')
            members[member.name]=member;total+=member.size
            if len(members)>MAX_MEMBERS+1 or total>MAX_TOTAL+MAX_MANIFEST: raise ValueError('Archive limits exceeded')
        if 'manifest.json' not in members: raise ValueError('Manifest missing')
        stream = tar.extractfile(members['manifest.json'])
        manifest_bytes = stream.read(MAX_MANIFEST+1)
        manifest = json.loads(manifest_bytes)
        if not isinstance(manifest,dict) or manifest.get('schema')!=1 or manifest.get('plan')!=expected_plan: raise ValueError('Manifest plan mismatch')
        records = manifest.get('records')
        if not isinstance(records,list) or not 1<=len(records)<=MAX_MEMBERS: raise ValueError('Invalid record count')
        wanted = {'manifest.json'}; paths = set()
        for record in records:
            approved_record(record,entries)
            if record['path'] in paths: raise ValueError('Duplicate restored path')
            paths.add(record['path'])
            if record['kind'] in {'directory','symlink'}:
                if 'payload' in record: raise ValueError('Unexpected link/directory payload')
                continue
            name = record.get('payload')
            if not isinstance(name,str) or not re.fullmatch(r'payload-[0-9]{6}',name) or name in wanted: raise ValueError('Invalid payload reference')
            if not isinstance(record.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',record['sha256']): raise ValueError('Invalid hash')
            if type(record.get('bytes')) is not int or record['bytes']<0: raise ValueError('Invalid payload size')
            maximum = MAX_DATABASE if record['kind']=='sqlite' else MAX_FILE
            if record['bytes']>maximum or name not in members or members[name].size!=record['bytes']: raise ValueError('Payload size mismatch')
            wanted.add(name)
        if wanted!=set(members): raise ValueError('Unexpected or missing archive payload')
        for entry in entries:
            if entry['path'] not in paths: raise ValueError('Required entry missing')
        # Validate the complete structure before writing any payload. Neutral
        # filenames retain owner-private modes; recorded original modes are not applied.
        for record in records:
            if 'payload' not in record: continue
            output = destination/record['payload'];digest=hashlib.sha256();written=0
            with tar.extractfile(members[record['payload']]) as source, output.open('xb') as target:
                os.chmod(output,0o600)
                while chunk:=source.read(1024*1024):
                    written+=len(chunk)
                    if written>record['bytes']: raise ValueError('Unexpected payload growth')
                    digest.update(chunk);target.write(chunk)
                target.flush();os.fsync(target.fileno())
            if written!=record['bytes'] or digest.hexdigest()!=record['sha256']: raise ValueError('Payload hash mismatch')
            if record['kind']=='sqlite':
                with closing(sqlite3.connect(output.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
                    db.execute('PRAGMA query_only=ON')
                    if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]: raise ValueError('Restored SQLite integrity failed')
        with (destination/'manifest.json').open('xb') as output:
            os.chmod(destination/'manifest.json',0o600);output.write(manifest_bytes);output.flush();os.fsync(output.fileno())
    return {'verification':'isolated-files-and-sqlite-validated','members':len(records),
            'services_started':False,'global_point_in_time':False}


def restore(ciphertext, private_key, certificate, expected_sha256, plan, destination, policy=allowed):
    private_directory(destination)
    if any(destination.iterdir()): raise ValueError('Restore directory must be empty')
    if not re.fullmatch('[0-9a-f]{64}',expected_sha256): raise ValueError('Trusted ciphertext digest required')
    # Copy all cryptographic inputs through checked descriptors into private
    # space; OpenSSL must not reopen a replaceable external pathname.
    with tempfile.TemporaryDirectory(prefix='.decrypt-',dir=destination) as tmp:
        root=Path(tmp)
        for original,name,maximum in ((private_key,'key.pem',MAX_FILE),(certificate,'cert.pem',MAX_FILE),
                                      (ciphertext,'cipher.cms',MAX_TOTAL+MAX_MANIFEST+32*1024*1024)):
            fd=open_regular(original)
            try:
                st=os.fstat(fd)
                if name=='key.pem' and (st.st_uid!=os.geteuid() or st.st_mode&0o077): raise ValueError('Private key must be owner-private')
                digest=hashlib.sha256();size=0
                with (root/name).open('xb') as output:
                    os.chmod(root/name,0o600)
                    while chunk:=os.read(fd,1024*1024):
                        size+=len(chunk)
                        if size>maximum: raise ValueError('Cryptographic input too large')
                        digest.update(chunk);output.write(chunk)
                if name=='cipher.cms' and digest.hexdigest()!=expected_sha256: raise ValueError('Ciphertext digest mismatch')
            finally: os.close(fd)
        der=command('openssl','x509','-in',str(root/'cert.pem'),'-outform','DER')
        if hashlib.sha256(der).hexdigest()!=plan['recipient_sha256']: raise ValueError('Recipient fingerprint mismatch')
        archive=root/'archive.tar'
        command('openssl','cms','-decrypt','-binary','-inform','DER','-in',str(root/'cipher.cms'),
                '-recip',str(root/'cert.pem'),'-inkey',str(root/'key.pem'),'-out',str(archive))
        payload=Path(tmp)/'validated';payload.mkdir(mode=0o700)
        result=validate_archive(archive,payload,plan,policy)
        for path in payload.iterdir(): os.link(path,destination/path.name)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ciphertext','private-key','certificate','plan','destination'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--ciphertext-sha256',required=True)
    args=parser.parse_args();os.umask(0o077)
    try:
        print(json.dumps(restore(args.ciphertext,args.private_key,args.certificate,args.ciphertext_sha256,load_plan(args.plan),args.destination)))
    except Exception as error: raise SystemExit(f'Isolated restore failed: {type(error).__name__}; no private contents printed') from None

if __name__=='__main__': main()
