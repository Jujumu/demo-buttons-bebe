import json
import subprocess
import unittest
from qa_metadata import prove_metadata

class MetadataTests(unittest.TestCase):
    def test_cache_pass_checks_exact_schemas_and_strict_readonly(self):
        schema={'mcp__qa__read':{'type':'object','properties':{'id':{'type':'integer'}},'required':['id']}}
        expected={'schemas':schema,'readonly':{'mcp__qa__read':True}}
        calls=[]
        def run(*args,**kwargs):
            calls.append(args)
            return subprocess.CompletedProcess([],0,'QA_METADATA='+json.dumps(expected),'')
        result=prove_metadata('python','source',{},'home',schema,['qa'],run)
        self.assertEqual(len(calls),2)
        self.assertTrue(result['fresh_process_cache_verified'])
        for defect in ({'schemas':schema,'readonly':{'mcp__qa__read':False}},
                       {'schemas':{'mcp__qa__read':{}},'readonly':expected['readonly']}):
            calls.clear()
            def broken(*args,**kwargs):
                calls.append(args)
                return subprocess.CompletedProcess([],0,'QA_METADATA='+json.dumps(expected if len(calls)==1 else defect),'')
            with self.assertRaisesRegex(ValueError,'fresh-process-cache'):
                prove_metadata('python','source',{},'home',schema,['qa'],broken)
