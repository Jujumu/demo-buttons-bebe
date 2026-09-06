"""One final review policy for model display and persisted processor results."""
from __future__ import annotations
import re
from typing import Any
from draft_cleaner import SENSITIVE_DRAFT_PREFIX
from .priority import Priority, at_least, normalize

_HEADER = re.compile(r'^\s*\[SENSITIVE(?:[^\]\r\n]{0,120})\]\s*',re.IGNORECASE)


def final_review_result(value: dict[str,Any]) -> dict[str,Any]:
    """Return a copy with coherent warning, priority and notification fields.

    Escalation can only increase. No-draft/authentication failures stay empty;
    this function never creates a customer reply or performs an external action.
    """
    result=dict(value)
    priority=normalize(result.get('priority',Priority.HIGH.value),default=Priority.HIGH)
    action=str(result.get('action','')).strip().lower()
    draft=str(result.get('draft_text') or '').strip()
    sensitive=(action in {'sensitive_draft','no_kb_match','escalated'}
               or bool(_HEADER.match(draft)) or at_least(priority,Priority.HIGH))
    if sensitive:
        result['action']='sensitive_draft'
        result['priority']=priority if at_least(priority,Priority.HIGH) else Priority.HIGH.value
        result['notify_owner']=True
        if draft and not result.get('no_draft'):
            if not draft.lower().startswith(SENSITIVE_DRAFT_PREFIX.lower()):
                header=_HEADER.match(draft)
                body=draft[header.end():] if header else draft
                draft=f'{SENSITIVE_DRAFT_PREFIX}\n\n{body}'
    else:
        result['priority']=priority
    result['draft_text']='' if result.get('no_draft') else draft
    result['gorgias_priority_set']=False
    result['note_posted']=False
    return result
