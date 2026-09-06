"""Synthetic recovery tests: no production files, credentials, or service calls."""
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent/'ops'))
import recovery_pack as pack
import recovery_policy as policy
import recovery_restore as restore


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();os.chmod(self.root,0o700)
        self.source=self.root/'source';self.source.mkdir(mode=0o700)
        self.secret=self.source/'config';self.secret.write_text('synthetic-private-value');os.chmod(self.secret,0o600)
        self.tree=self.source/'corpora';self.tree.mkdir();(self.tree/'policy.md').write_text('Synthetic policy')
        (self.tree/'empty-auth').mkdir()
        self.db=self.source/'state.sqlite3'
        with closing(sqlite3.connect(self.db)) as db:
            db.execute('create table actions(id integer primary key, status text)');db.execute("insert into actions values(1,'uncertain')");db.commit()
        self.plan={'schema':1,'release_commit':'a'*40,'recipient_sha256':'b'*64,'entries':[
            {'path':str(self.secret),'kind':'file'}, {'path':str(self.tree),'kind':'tree'}, {'path':str(self.db),'kind':'sqlite'}]}
        self.allow=lambda path,kind: path.startswith(str(self.source)+'/') and kind in {'file','tree','sqlite','symlink'}
    def directory(self,name):
        path=self.root/name;path.mkdir(mode=0o700);return path
    def archive(self,manifest,content,name='archive.tar',mutate=None):
        path=self.root/name
        with tarfile.open(path,'w',format=tarfile.USTAR_FORMAT) as tar:
            raw=json.dumps(manifest).encode();info=tarfile.TarInfo('manifest.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
            for record in manifest['records']:
                if 'payload' not in record:continue
                value=(content/record['payload']).read_bytes()
                if mutate:value=mutate(record,value)
                info=tarfile.TarInfo(record['payload']);info.size=len(value);tar.addfile(info,io.BytesIO(value))
        return path
    def test_file_sqlite_empty_directory_and_private_restore(self):
        content=self.directory('content');manifest=pack.capture(self.plan,content,self.allow)
        self.assertIn('not a global',manifest['consistency'])
        self.assertTrue(any(r['path'].endswith('empty-auth') and r['kind']=='directory' for r in manifest['records']))
        target=self.directory('restore');result=restore.validate_archive(self.archive(manifest,content),target,self.plan,self.allow)
        self.assertFalse(result['services_started']);self.assertFalse(result['global_point_in_time'])
        dbrecord=next(r for r in manifest['records'] if r['kind']=='sqlite')
        with closing(sqlite3.connect(target/dbrecord['payload'])) as db:self.assertEqual(db.execute('select status from actions').fetchone()[0],'uncertain')
        self.assertTrue(all(p.stat().st_mode&0o077==0 for p in target.iterdir()))
    def test_symlink_parent_leaf_tree_and_fifo_rejected(self):
        link=self.source/'link';link.symlink_to(self.secret)
        with self.assertRaises(OSError):pack.file_snapshot(str(link),self.root/'output')
        parent=self.root/'linked';parent.symlink_to(self.source,target_is_directory=True)
        with self.assertRaises(OSError):pack.file_snapshot(str(parent/'config'),self.root/'output')
        (self.tree/'link').symlink_to(self.secret)
        with self.assertRaises(ValueError):pack.tree_inventory(str(self.tree))
        fifo=self.source/'fifo';os.mkfifo(fifo)
        with self.assertRaises(ValueError):policy.open_regular(str(fifo))
    def test_unstable_file_retries_then_fails(self):
        real=pack.hash_fd
        def changed(fd,*args):
            value=real(fd,*args)
            with self.secret.open('a') as stream:stream.write('changed')
            return value
        with patch.object(pack,'hash_fd',side_effect=changed) as call:
            with self.assertRaises(RuntimeError):pack.file_snapshot(str(self.secret),self.root/'output')
            self.assertEqual(call.call_count,6)
    def test_tree_membership_change_fails_capture(self):
        real=pack.file_snapshot
        def changed(source,destination):
            result=real(source,destination)
            if source.endswith('policy.md'):(self.tree/'new.md').write_text('new generation')
            return result
        with patch.object(pack,'file_snapshot',side_effect=changed):
            with self.assertRaises(RuntimeError):pack.capture(self.plan,self.directory('content'),self.allow)
    def test_size_and_count_limits(self):
        with patch.object(pack,'MAX_TOTAL',1):
            with self.assertRaises(ValueError):pack.capture(self.plan,self.directory('small'),self.allow)
        with patch.object(pack,'MAX_MEMBERS',1):
            with self.assertRaises(ValueError):pack.tree_inventory(str(self.tree))
    def test_tampered_hash_and_missing_required_record(self):
        content=self.directory('content');manifest=pack.capture(self.plan,content,self.allow)
        archive=self.archive(manifest,content,mutate=lambda r,v: b'X'+v[1:] if r['kind']=='file' else v)
        with self.assertRaises(ValueError):restore.validate_archive(archive,self.directory('restore'),self.plan,self.allow)
        manifest['records']=manifest['records'][1:]
        with self.assertRaises(ValueError):restore.validate_archive(self.archive(manifest,content,'missing.tar'),self.directory('missing'),self.plan,self.allow)
    def test_tar_traversal_links_duplicates_and_extensions_rejected(self):
        for i,(name,kind) in enumerate([('../escape',tarfile.REGTYPE),('payload-000000',tarfile.SYMTYPE),('payload-000000',tarfile.XHDTYPE)]):
            path=self.root/f'bad{i}.tar'
            with tarfile.open(path,'w',format=tarfile.USTAR_FORMAT) as tar:
                info=tarfile.TarInfo(name);info.type=kind;info.linkname='/etc/passwd';tar.addfile(info)
            with self.assertRaises(ValueError):restore.validate_archive(path,self.directory(f'out{i}'),self.plan,self.allow)
        content=self.directory('content');manifest=pack.capture(self.plan,content,self.allow)
        archive=self.archive(manifest,content)
        with tarfile.open(archive,'a',format=tarfile.USTAR_FORMAT) as tar:
            info=tarfile.TarInfo('manifest.json');tar.addfile(info)
        with self.assertRaises(ValueError):restore.validate_archive(archive,self.directory('duplicate'),self.plan,self.allow)
    def test_sqlite_wal_snapshot_excludes_uncommitted_work_and_preserves_source(self):
        with closing(sqlite3.connect(self.db)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute("insert into actions values(2,'pending')")
            snapshot=self.root/'wal-backup.sqlite3'
            pack.database_snapshot(str(self.db),snapshot)
            with closing(sqlite3.connect(snapshot)) as reader:
                self.assertEqual(reader.execute('select count(*) from actions').fetchone()[0],1)
            writer.commit()
            self.assertEqual(writer.execute('select count(*) from actions').fetchone()[0],2)

    def test_scope_and_private_plan(self):
        for path,kind in [('/root/.hermes/history','tree'),('/root/.hermes/cache/file','file'),('/etc/caddy','tree'),('/root/Buttonsbebe Agent/KB/lancedb','tree'),('/root/Buttonsbebe Agent/.env/../other','file')]:
            with self.subTest(path=path):
                try:accepted=policy.allowed(path,kind)
                except ValueError:accepted=False
                self.assertFalse(accepted)
        private=self.root/'plan.json';private.write_text(json.dumps(self.plan));os.chmod(private,0o600)
        self.assertEqual(policy.load_plan(private,self.allow),self.plan)
        os.chmod(private,0o644)
        with self.assertRaises(ValueError):policy.load_plan(private,self.allow)
    def test_explicit_symlink_recipe_requires_captured_target_and_never_restores_link(self):
        link=self.source/'approved-link';link.symlink_to('config')
        plan={**self.plan,'entries':[{'path':str(link),'kind':'symlink','target':str(self.secret)}, {'path':str(self.secret),'kind':'file'}]}
        content=self.directory('content');manifest=pack.capture(plan,content,self.allow)
        target=self.directory('restore');restore.validate_archive(self.archive(manifest,content),target,plan,self.allow)
        self.assertFalse(any(p.is_symlink() for p in target.iterdir()))
        plan['entries']=plan['entries'][:1]
        with self.assertRaises(ValueError):policy.plan_entries(plan,self.allow)

    def test_sqlite_corruption_even_with_updated_hash_is_rejected(self):
        content=self.directory('content');manifest=pack.capture(self.plan,content,self.allow)
        row=next(r for r in manifest['records'] if r['kind']=='sqlite')
        raw=b'Not a SQLite database';(content/row['payload']).write_bytes(raw)
        row['sha256']=hashlib.sha256(raw).hexdigest();row['bytes']=len(raw)
        with self.assertRaises(sqlite3.DatabaseError):
            restore.validate_archive(self.archive(manifest,content),self.directory('bad-db'),self.plan,self.allow)

    def test_private_restore_directory_must_be_empty_and_protected(self):
        output=self.directory('output');(output/'existing').write_text('preserve')
        with self.assertRaises(ValueError):restore.validate_archive(self.root/'absent.tar',output,self.plan,self.allow)
        self.assertEqual((output/'existing').read_text(),'preserve')
        os.chmod(output,0o755)
        with self.assertRaises(ValueError):policy.private_directory(output)

    def test_only_exact_reviewed_user_gateway_unit_is_allowed(self):
        self.assertTrue(policy.allowed('/root/.config/systemd/user/hermes-gateway.service','file'))
        for path,kind in (
            ('/root/.config/systemd/user/other.service','file'),
            ('/root/.config/systemd/user/hermes-gateway.timer','file'),
            ('/root/.config/systemd/user/hermes-gateway.service.d/override.conf','file'),
            ('/root/.config/systemd/user','tree'),
            ('/root/.config/systemd/user/hermes-gateway.service','symlink'),
            ('/root/.hermes/state.db','sqlite'),
            ('/root/.hermes/history','tree')):
            with self.subTest(path=path,kind=kind):self.assertFalse(policy.allowed(path,kind))

    def test_cms_roundtrip_and_wrong_digest_leave_no_plaintext(self):
        key=self.root/'key.pem';cert=self.root/'cert.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','2','-subj','/CN=Synthetic recovery test'],check=True,capture_output=True)
        os.chmod(key,0o600)
        der=pack.command('openssl','x509','-in',str(cert),'-outform','DER');self.plan['recipient_sha256']=hashlib.sha256(der).hexdigest()
        destination=self.directory('encrypted')
        with self.assertRaises(ValueError):pack.pack({**self.plan,'recipient_sha256':'0'*64},destination,cert,self.allow)
        self.assertEqual(list(destination.iterdir()),[])
        receipt=pack.pack(self.plan,destination,cert,self.allow)
        ciphertext=next(destination.glob('*.cms'))
        self.assertNotIn('synthetic-private-value',ciphertext.read_bytes().decode('latin1'))
        self.assertEqual(sorted(p.suffix for p in destination.iterdir()),['.cms','.json'])
        output=self.directory('decrypted');result=restore.restore(ciphertext,key,cert,receipt['ciphertext_sha256'],self.plan,output,self.allow)
        self.assertEqual(result['verification'],'isolated-files-and-sqlite-validated')
        bad=self.directory('bad-digest')
        with self.assertRaises(ValueError):restore.restore(ciphertext,key,cert,'0'*64,self.plan,bad,self.allow)
        self.assertEqual(list(bad.iterdir()),[])
        corrupt=self.root/'corrupt.cms';raw=bytearray(ciphertext.read_bytes());raw[-1]^=1;corrupt.write_bytes(raw)
        gcm=self.directory('bad-gcm')
        with self.assertRaises(RuntimeError):restore.restore(corrupt,key,cert,hashlib.sha256(raw).hexdigest(),self.plan,gcm,self.allow)
        self.assertEqual(list(gcm.iterdir()),[])

if __name__=='__main__':unittest.main()
