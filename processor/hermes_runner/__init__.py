"""Compatibility facade for the split, token-authenticated Hermes runner."""

from .constants import (
    _ACTION_SEVERITY,
    _ALLOWED_ACTIONS,
    _FALLBACK_RESULT,
    _MAX_JSON_BLOCK,
    _MAX_NOTE,
    _MAX_REASON,
    _MAX_REASON_WITH_NOTE,
    _MAX_VERDICT_CANDIDATES,
    _MIN_NOTE,
    _NO_DRAFT_RESULT,
    _NONCE_BYTES,
    _NOTE_LABEL,
    _PRIORITY_ORDER,
    _TOKEN_FAILURE_RESULT,
    _UNKNOWN_ACTION_SEVERITY,
    _make_run_token,
    _token_failure_result,
)
from .extract import (
    DraftExtraction,
    _as_bool,
    _draft_tag_re,
    _extract_draft,
    _extract_draft_details,
    _extract_json_block,
    _json_marker_re,
    _merge_verdicts,
    _parse_json_result,
    _valid_verdicts,
)
from .prompt import _MARKER_SUBSTITUTIONS, _build_prompt, _neutralise_markers
from .runner import build_hermes_command, draft_for_console, process_ticket_with_hermes


__all__ = [
    "build_hermes_command",
    "draft_for_console",
    "process_ticket_with_hermes",
]
