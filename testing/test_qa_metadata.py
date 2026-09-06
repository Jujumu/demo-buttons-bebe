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

    def test_only_observed_optional_string_normalization_is_accepted(self):
        import copy
        from qa_metadata import canonical_nullable_schema, metadata_equal as compare_metadata
        def metadata_equal(a,b):return compare_metadata({'schemas':{'tool':a}}, {'schemas':{'tool':b}})
        endpoint={'type':'object','properties':{'cursor':{'anyOf':[{'type':'string'},{'type':'null'}],'default':None,'title':'Cursor','maxLength':2048}},'required':['id'],'additionalProperties':False}
        normalized=copy.deepcopy(endpoint)
        normalized['properties']['cursor']={'type':'string','nullable':True,'default':None,'title':'Cursor','maxLength':2048}
        self.assertTrue(metadata_equal(endpoint,normalized))
        self.assertEqual(canonical_nullable_schema(endpoint),normalized)
        for change in ('required','bound','enum','default','additional','nullable','bool-vs-int'):
            with self.subTest(change=change):
                altered=copy.deepcopy(normalized)
                cursor=altered['properties']['cursor']
                if change=='required':altered['required']=[]
                elif change=='bound':cursor['maxLength']=4096
                elif change=='enum':cursor['enum']=['one']
                elif change=='default':cursor.pop('default')
                elif change=='additional':altered['additionalProperties']=True
                elif change=='nullable':cursor['nullable']=False
                else:altered['additionalProperties']=0
                self.assertFalse(metadata_equal(endpoint,altered))
        for union in ([{'type':'integer'},{'type':'null'}],
                      [{'type':'string','enum':['a']},{'type':'null'}],
                      [{'type':'string'},{'type':'null'},{'type':'boolean'}]):
            shape={'anyOf':union}
            self.assertEqual(canonical_nullable_schema(shape),shape)
        for extra in ({'oneOf':[{'type':'integer'}]}, {'nullable':False}, {'type':'integer'}):
            shape={'anyOf':[{'type':'string'},{'type':'null'}],**extra}
            self.assertEqual(canonical_nullable_schema(shape),shape)

        literal={'anyOf':[{'type':'string'},{'type':'null'}]}
        for key in ('default','enum','const','x-custom'):
            shape={'type':'object',key:literal}
            self.assertEqual(canonical_nullable_schema(shape),shape)
