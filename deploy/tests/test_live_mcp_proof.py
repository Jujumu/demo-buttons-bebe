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
