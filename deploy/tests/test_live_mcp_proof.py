"""Discovery guard and exact metadata comparison; no production access."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('verify_live_mcp',ROOT/'tools/ops/verify_live_mcp.py')
proof=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof)


class DiscoveryProofTests(unittest.TestCase):
    def request(self,method='tools/list',host='127.0.0.1',port=8077):
        return SimpleNamespace(url=SimpleNamespace(host=host,port=port,scheme='http'),
                               method='POST',content=json.dumps({'method':method}).encode())

    def test_sdk1_and_sdk2_alias_shapes_preserve_false_and_none(self):
        for snake in (True, False):
            tool = SimpleNamespace(name='search_kb', annotations=SimpleNamespace(**{
                'read_only_hint' if snake else 'readOnlyHint':True}), **{
                'input_schema' if snake else 'inputSchema':{'type':'object','properties':{'q':{'type':'string'}}}})
            listing = SimpleNamespace(tools=[tool], **{'next_cursor' if snake else 'nextCursor':None})
            result = proof.endpoint_metadata('buttonsbebe_kb',listing)
            self.assertTrue(result['readonly']['mcp__buttonsbebe_kb__search_kb'])
            self.assertTrue(result['schemas']['mcp__buttonsbebe_kb__search_kb']['properties'])
        self.assertIs(proof.mcp_field(SimpleNamespace(read_only_hint=False,readOnlyHint=True),'read_only_hint','readOnlyHint'),False)
        self.assertIsNone(proof.mcp_field({'next_cursor':None,'nextCursor':'bad'},'next_cursor','nextCursor'))

    def test_only_local_discovery_not_tool_or_model_calls(self):
        proof.guard_request(self.request())
        for req in (self.request('tools/call'),self.request('sampling/createMessage'),
                    self.request(host='example.invalid'),self.request(port=8000)):
            with self.assertRaises(PermissionError): proof.guard_request(req)
        proof.audit('socket.connect',(None,('127.0.0.1',8078)))
        with self.assertRaises(PermissionError): proof.audit('socket.connect',(None,('192.0.2.1',8078)))
        with self.assertRaises(PermissionError): proof.audit('subprocess.Popen',())

    def test_exact_ten_readonly_nonempty_schema_required(self):
        names=['mcp__'+g+'__'+n for g,(_,ns) in proof.GROUPS.items() for n in ns]
        metadata={'schemas':{n:{'type':'object','properties':{'id':{'type':'integer'}}} for n in names},
                  'readonly':{n:True for n in names}}
        proof.validate_metadata(metadata)
        for change in ('missing','hint','empty'):
            value=json.loads(json.dumps(metadata))
            if change=='missing':del value['schemas'][names[0]]
            if change=='hint':value['readonly'][names[0]]=1
            if change=='empty':value['schemas'][names[0]]['properties']={}
            with self.assertRaises(ValueError):proof.validate_metadata(value)

    def test_nullable_equivalence_preserves_every_other_constraint_and_instance_value(self):
        original={'schemas':{'x':{'type':'object','properties':{'q':{'anyOf':[{'type':'string'},{'type':'null'}],'default':None}}}},'readonly':{'x':True}}
        normalized=json.loads(json.dumps(original))
        normalized['schemas']['x']['properties']['q']={'type':'string','nullable':True,'default':None}
        self.assertTrue(proof.metadata_equal(original,normalized))
        normalized['schemas']['x']['properties']['q']['maxLength']=1
        self.assertFalse(proof.metadata_equal(original,normalized))
        instance={'default':{'anyOf':[{'type':'string'},{'type':'null'}]}}
        self.assertEqual(proof.canonical_nullable_schema(instance),instance)

    def test_transport_supports_sdk1_triple_and_sdk2_pair_without_unguarded_defaults(self):
        import asyncio
        from contextlib import asynccontextmanager
        from unittest.mock import patch
        for legacy in (True,False):
            events=[]
            class Client:
                def __init__(self,**kwargs):events.append(('client',kwargs))
                async def __aenter__(self):return self
                async def __aexit__(self,*args):events.append(('closed',True))
            @asynccontextmanager
            async def connect(url,**kwargs):
                events.append(('transport',kwargs))
                yield ('read','write','session') if legacy else ('read','write')
            transport=SimpleNamespace(**{'streamablehttp_client' if legacy else 'streamable_http_client':connect})
            http=SimpleNamespace(AsyncClient=Client,Timeout=lambda *a,**k:(a,k))
            async def run():
                async with proof.discovery_transport('http://127.0.0.1:8077/mcp') as streams:
                    self.assertEqual(streams,('read','write'))
            with patch.object(proof.importlib,'import_module',side_effect=lambda name:transport if name=='mcp.client.streamable_http' else http):
                asyncio.run(run())
            if legacy:self.assertEqual(events[0][1],{'timeout':5,'sse_read_timeout':15})
            else:
                self.assertEqual(events[0][1],{'timeout':((5,),{'read':15}),'trust_env':False,'follow_redirects':False})
                self.assertEqual(events[-1],('closed',True))
                self.assertIn('http_client',events[1][1])

    def test_both_http_client_families_block_tool_calls_before_transport(self):
        import asyncio
        for family in ('httpx','httpx2'):
            events=[]
            class Sync:
                def send(self,request,*args,**kwargs):events.append('sync');return 'ok'
            class Async:
                async def send(self,request,*args,**kwargs):events.append('async');return 'ok'
            module=SimpleNamespace(Client=Sync,AsyncClient=Async)
            proof.guard_http_client(module)
            self.assertEqual(Sync().send(self.request()),'ok')
            self.assertEqual(asyncio.run(Async().send(self.request())),'ok')
            for request in (self.request('tools/call'),self.request('sampling/createMessage'),self.request(host='example.invalid')):
                with self.assertRaises(PermissionError):Sync().send(request)
                with self.assertRaises(PermissionError):asyncio.run(Async().send(request))
            self.assertEqual(events,['sync','async'],family)

    def test_head_is_only_allowed_at_reviewed_local_discovery_endpoints(self):
        request=self.request();request.method='HEAD';proof.guard_request(request)
        for host,port in [('example.invalid',8077),('127.0.0.1',8000)]:
            request=self.request(host=host,port=port);request.method='HEAD'
            with self.assertRaises(PermissionError):proof.guard_request(request)

    def test_child_stderr_is_suppressed_through_interpreter_shutdown(self):
        import subprocess,sys
        code="""import sys,atexit,importlib.util
spec=importlib.util.spec_from_file_location('proof',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.silence_stderr()
print('synthetic-diagnostic',file=sys.stderr)
atexit.register(lambda:print('synthetic-late-diagnostic',file=sys.stderr))
print('safe-output')
"""
        result=subprocess.run([sys.executable,'-c',code,str(ROOT/'tools/ops/verify_live_mcp.py')],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stderr,'')
        self.assertEqual(result.stdout.strip(),'safe-output')
