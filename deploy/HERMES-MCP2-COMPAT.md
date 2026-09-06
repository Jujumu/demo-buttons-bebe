# Hermes MCP 2 field compatibility repair

The installed MCP 2 SDK exposes `ToolAnnotations.read_only_hint` and
`Tool.input_schema`. Two Hermes cache/trust reads still use the old attribute
spellings. This falsely marks read-only tools as write-capable and serializes
empty schemas. The runtime conversion already uses Hermes' `mcp_field` helper;
this repair uses that same helper in the two remaining locations. It keeps the
strict `hint is True` guard, untrusted-server setting, approval policy, model,
and three-toolset allowlist intact.

`fix_hermes_mcp2_fields.py SOURCE` is a dry run. Apply requires an explicit new
backup filename and the matching reviewed `--expected-sha256`. Unknown source
shapes fail; rerunning a completed repair is harmless. This is a manual repair
of the installed Hermes dependency, not an automatic CD action.

Before applying to production, the operator reviews the two-line diff and
coordinates processor/rewrite downtime so no Hermes process consumes a mixed
version. Preserve a private backup of the source and existing schema cache.
Invalidate only the three Buttons Bebe server entries in the existing Hermes
MCP schema cache, retaining unrelated entries; old cache entries contain false
hints and empty schemas and cannot demonstrate recovery. Do not change server
trust or disable approval. Rebuild and validate read-only metadata before
restarting draft generation. A source rollback also restores its matching cache
backup; customer databases and KB index are never part of this operation.

QA independently compares the MCP endpoint schemas and read-only declarations
with the actual Hermes registry, then repeats the comparison in a fresh process
to exercise its cache. Any difference blocks model calls. Isolated QA can use a
private source overlay before any installed dependency is changed.
