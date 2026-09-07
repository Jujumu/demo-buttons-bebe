"""Actual Caddy session and strict-origin gate tests using synthetic backends."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from test_inbox_caddy_contract import port

SOURCE = Path(__file__).resolve().parents[1] / 'caddy/sites/receiving.caddy'
ORIGIN = 'https://support.buttonsbebe.com:8443'


@unittest.skipUnless(shutil.which('caddy'), 'Requires Caddy; exercised on Linux staging')
class ReceivingProxyTests(unittest.TestCase):
    def test_session_and_exact_origin_protect_every_write_without_rewriting_paths(self):
        calls = []
        backend_credentials = []
        class Auth(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(('auth',self.path))
                self.send_response(200 if self.headers.get('Cookie') == 'session=synthetic' else 401)
                self.send_header('Content-Type','application/json'); self.end_headers()
                self.wfile.write(b'{"authenticated":false}')
            def log_message(self,*args): pass
        class Backend(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(('backend',self.command,self.path))
                backend_credentials.append((self.headers.get('Cookie'),self.headers.get('Authorization')))
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(json.dumps({'path':self.path,'method':self.command}).encode())
            do_POST=do_GET
            def log_message(self,*args): pass
        auth=ThreadingHTTPServer(('127.0.0.1',0),Auth)
        backend=ThreadingHTTPServer(('127.0.0.1',0),Backend)
        for server in (auth,backend):
            threading.Thread(target=server.serve_forever,daemon=True).start()
            self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        listen=port()
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'Caddyfile'
            source=SOURCE.read_text().replace(ORIGIN+' {',f'http://127.0.0.1:{listen} {{')
            source=source.replace('127.0.0.1:8000',f'127.0.0.1:{auth.server_port}').replace('127.0.0.1:3210',f'127.0.0.1:{backend.server_port}')
            source=source.replace('/var/log/bb-webhook/caddy-receiving.log',str(Path(temp)/'receiving.log'))
            config.write_text('{\n admin off\n auto_https off\n}\n'+source)
            result=subprocess.run(['caddy','adapt','--config',str(config),'--adapter','caddyfile'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            process=subprocess.Popen(['caddy','run','--config',str(config),'--adapter','caddyfile'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            def request(path,method='GET',cookie=False,origin=None):
                headers={}
                if cookie:
                    headers['Cookie']='session=synthetic'
                    headers['Authorization']='Bearer synthetic-not-a-real-token'
                if origin is not None:headers['Origin']=origin
                req=urllib.request.Request(f'http://127.0.0.1:{listen}'+path,method=method,headers=headers,data=b'{}' if method=='POST' else None)
                try:
                    with urllib.request.urlopen(req,timeout=3) as response:return response.status,response.read(),response.headers
                except urllib.error.HTTPError as error:return error.code,error.read(),error.headers
            try:
                for attempt in range(60):
                    try:status,body,headers=request('/');break
                    except urllib.error.URLError:
                        if attempt==59:raise
                        time.sleep(.05)
                self.assertEqual(status,401)
                self.assertEqual(headers['X-Frame-Options'],'DENY')
                self.assertEqual(headers['Content-Security-Policy'],"frame-ancestors 'none'")
                self.assertIn(b'https://support.buttonsbebe.com/console/login',body)
                self.assertIn('text/html',headers.get('Content-Type',''))
                status,body,headers=request('/api/tracking-stats')
                self.assertEqual(status,401);self.assertIn('application/json',headers.get('Content-Type',''))
                for bad in (None,'https://support.buttonsbebe.com',ORIGIN+'.evil.test'):
                    before=len(calls)
                    self.assertEqual(request('/api/synthetic-action','POST',True,bad)[0],403)
                    self.assertEqual(len(calls),before) # Origin gate runs even before auth
                for method in ('PUT','PATCH','DELETE'):
                    self.assertEqual(request('/api/synthetic-action',method,True)[0],403)
                self.assertEqual(request('/api/synthetic-action','POST',False,ORIGIN)[0],401)
                status,body,_=request('/api/synthetic-action','POST',True,ORIGIN)
                self.assertEqual(status,200);self.assertEqual(json.loads(body),{'path':'/api/synthetic-action','method':'POST'})
                for path in ('/api/reconciliation','/api/reconciliation/','/API/RECONCILIATION','/api/reconciliation?filter=synthetic'):
                    self.assertEqual(request(path,'GET',True)[0],403)
                    self.assertEqual(request(path,'HEAD',True)[0],403)
                self.assertEqual(request('/webhooks/redo','POST')[0],403)
                status,body,headers=request('/','GET',True)
                self.assertEqual(status,200)
                self.assertEqual(headers['X-Frame-Options'],'DENY')
                self.assertEqual(headers['Content-Security-Policy'],"frame-ancestors 'none'")
                self.assertEqual(backend_credentials,[(None,None),(None,None)])
                self.assertTrue(all(item[1]=='/auth/session' for item in calls if item[0]=='auth'))
            finally:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


if __name__ == '__main__':unittest.main()
