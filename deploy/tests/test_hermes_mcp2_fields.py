import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec=importlib.util.spec_from_file_location('compat', Path(__file__).parents[1]/'fix_hermes_mcp2_fields.py')
compat=importlib.util.module_from_spec(spec);spec.loader.exec_module(compat)

SOURCE='''
def annotation(annotations):
 hint = getattr(annotations, "readOnlyHint", None)
 return hint is True
def schema(mcp_tool):
 schema_obj = getattr(mcp_tool, "inputSchema", None)
 return schema_obj
'''

class CompatibilityTests(unittest.TestCase):
    def test_both_sdk_field_shapes_preserve_strict_readonly_and_schema(self):
        def mcp_field(obj,snake,camel):
            return getattr(obj,snake,getattr(obj,camel,None))
        namespace={'mcp_field':mcp_field};exec(compat.patched(SOURCE),namespace)
        for field in ('readOnlyHint','read_only_hint'):
            for value in (True,False,1,'true',None):
                self.assertEqual(namespace['annotation'](SimpleNamespace(**{field:value})),value is True)
        schema={'type':'object','properties':{'ticket_id':{'type':'integer'}},'required':['ticket_id']}
        for field in ('inputSchema','input_schema'):
            self.assertEqual(namespace['schema'](SimpleNamespace(**{field:schema})),schema)
        self.assertFalse(namespace['annotation'](SimpleNamespace()))
    def test_repair_is_idempotent_and_unknown_source_fails(self):
        value=compat.patched(SOURCE)
        self.assertEqual(compat.patched(value),value)
        with self.assertRaises(ValueError):compat.patched(SOURCE+SOURCE)
        with self.assertRaises(ValueError):compat.patched('pass')

    def test_installer_requires_reviewed_hash_and_preserves_backup(self):
        import hashlib,subprocess,sys,tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/'mcp_tool.py';target.write_text(SOURCE)
            script=Path(__file__).parents[1]/'fix_hermes_mcp2_fields.py'
            base=[sys.executable,str(script),str(target)]
            self.assertEqual(subprocess.run(base,capture_output=True).returncode,0)
            self.assertEqual(target.read_text(),SOURCE)
            self.assertNotEqual(subprocess.run(base+['--apply','--backup',str(root/'backup')],capture_output=True).returncode,0)
            self.assertFalse((root/'backup').exists())
            result=subprocess.run(base+['--apply','--backup',str(root/'backup'),'--expected-sha256',hashlib.sha256(SOURCE.encode()).hexdigest()],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((root/'backup').read_text(),SOURCE)
            self.assertEqual(target.read_text(),compat.patched(SOURCE))
