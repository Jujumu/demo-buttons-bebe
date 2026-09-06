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


def canonical_nullable_schema(node):
    """Accept only the observed Hermes optional-string normalization.

    Installed Hermes _normalize_mcp_input_schema delegates to
    strip_nullable_unions(..., keep_nullable_hint=True). A two-branch
    string/null union becomes type=string, nullable=true. Preserve every other
    field exactly, including default, enum, required and length constraints.
    Other union shapes are deliberately not treated as equivalent.
    """
    if isinstance(node, list):
        return [canonical_nullable_schema(value) for value in node]
    if not isinstance(node, dict):
        return node
    out = dict(node)
    # Recurse only through schema-valued keywords. Defaults, enum/const values
    # and extension metadata are instance data, even when they resemble schemas.
    for key in ('properties', 'patternProperties', '$defs', 'definitions'):
        if isinstance(out.get(key), dict):
            out[key] = {name: canonical_nullable_schema(value) for name, value in out[key].items()}
    for key in ('items', 'additionalProperties', 'anyOf', 'oneOf', 'allOf', 'not'):
        if key in out:
            out[key] = canonical_nullable_schema(out[key])
    union = out.get('anyOf')
    if (isinstance(union, list) and len(union) == 2
            and {'type': 'string'} in union and {'type': 'null'} in union
            and not {'type', 'nullable', 'oneOf', 'allOf'}.intersection(out)):
        del out['anyOf']
        out['type'] = 'string'
        out['nullable'] = True
    return out


def metadata_equal(actual, expected):
    def canonical_metadata(value):
        if not isinstance(value, dict) or not isinstance(value.get('schemas'), dict):
            return value
        return {**value, 'schemas': {name: canonical_nullable_schema(schema) for name, schema in value['schemas'].items()}}
    # JSON serialization keeps false different from 0 and null from missing.
    return json.dumps(canonical_metadata(actual), sort_keys=True) == json.dumps(canonical_metadata(expected), sort_keys=True)


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
        if result.returncode or len(rows) != 1 or not metadata_equal(json.loads(rows[0]), expected):
            raise ValueError('Hermes readonly metadata/schema mismatch during ' + phase + '; no model calls permitted')
    return {'readonly_verified': True, 'endpoint_schemas_verified': True,
            'fresh_process_cache_verified': True, 'nullable_comparison': 'exact-string-null-union-only', 'tool_count': len(expected_schemas)}
