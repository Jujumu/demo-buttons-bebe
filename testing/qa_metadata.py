"""Fail QA before model use when Hermes loses MCP schemas or readonly hints."""
import json

PROBE = '''
import sys,json
sys.path.insert(0,sys.argv[1])
from model_tools import get_tool_definitions
from tools.mcp_tool import discover_mcp_tools,shutdown_mcp_servers,_tool_read_only_hints
try:
 groups=json.loads(sys.argv[2])
 discover_mcp_tools()
 raw=get_tool_definitions(enabled_toolsets=groups,quiet_mode=True,skip_tool_search_assembly=True)
 schemas={item['function']['name']:item['function']['parameters'] for item in raw}
 hints={'mcp__'+group+'__'+name:value is True for group in groups for name,value in _tool_read_only_hints.get(group,{}).items()}
 print('QA_METADATA='+json.dumps({'schemas':schemas,'readonly':hints},sort_keys=True))
finally:
 shutdown_mcp_servers()
'''


def prove_metadata(python, source, env, home, expected_schemas, groups, run):
    if not expected_schemas:
        raise ValueError('QA requires endpoint schema evidence')
    expected = {'schemas': expected_schemas,
                'readonly': {name: True for name in expected_schemas}}
    for phase in ('initial', 'fresh-process-cache'):
        result = run([str(python), '-c', PROBE, str(source), json.dumps(groups)],
                     timeout=90, env=env, cwd=home)
        rows = [line[len('QA_METADATA='):] for line in result.stdout.splitlines()
                if line.startswith('QA_METADATA=')]
        if result.returncode or len(rows) != 1 or json.loads(rows[0]) != expected:
            raise ValueError('Hermes readonly metadata/schema mismatch during ' + phase + '; no model calls permitted')
    return {'readonly_verified': True, 'endpoint_schemas_verified': True,
            'fresh_process_cache_verified': True, 'tool_count': len(expected_schemas)}
