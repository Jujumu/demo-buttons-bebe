"""Demo intake copies. First-party mailbox, not Shopify objects.

Mailbox: helpdesk-support@agentmail.to (display Demo Shop Support).
"""

from __future__ import annotations

MAILBOX_ADDRESS = "helpdesk-support@agentmail.to"
MAILBOX_DISPLAY = "Demo Shop Support"

ADA_TRACKING = {
    "from": "Ada <ada.tracking@example.com>",
    "subject": "Tracking on order #1001 has not moved",
    "body": "Where is my order #1001? The tracking has not updated.",
    "receivedAt": "2026-08-30T14:02:00Z",
}

SAM_RATTLE = {
    "from": "Sam <sam.rattle@example.com>",
    "subject": "Broken rattle",
    "body": "The wooden rattle arrived cracked. Can you help?",
    "receivedAt": "2026-08-30T14:10:00Z",
}

PRIYA_RETURN = {
    "from": "Priya <priya.return@example.com>",
    "subject": "I need to start a return",
    "body": "The romper does not fit. I would like to return it.",
    "receivedAt": "2026-08-30T14:12:00Z",
}

JORDAN_WRONG = {
    "from": "Jordan <jordan.wrong@example.com>",
    "subject": "Wrong item in the box",
    "body": "I ordered the visor and received a blanket instead.",
    "receivedAt": "2026-08-30T14:14:00Z",
}

PRIZE_SPAM = {
    "from": "Prize Desk <winner@prize-farm.example>",
    "subject": "You won a $10,000 prize!",
    "body": "Claim your lottery winnings today. Unsubscribe from this farm of cash prize emails.",
    "receivedAt": "2026-08-30T14:16:00Z",
}

CHAT_WITH_1001 = {
    "fromName": "Ada",
    "body": "Any update on #1001? Tracking looks stuck.",
    "receivedAt": "2026-08-30T15:02:00Z",
}

CHAT_WITHOUT_ORDER = {
    "fromName": "Sam",
    "body": "The rattle is broken. Is anyone there?",
    "receivedAt": "2026-08-30T15:10:00Z",
}
