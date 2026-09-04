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

PRIYA_UNSUB = {
    "from": "Priya Lane <priya.unsub@example.com>",
    "subject": "Please unsubscribe me from marketing emails",
    "body": "Please take me off the marketing list. I still want order updates.",
    "receivedAt": "2026-08-30T14:18:00Z",
}

LEE_PRIVACY = {
    "from": "Lee Chen <lee.privacy@example.com>",
    "subject": "GDPR request — please delete my data",
    "body": "Please delete my stored personal data. I do not need a Shopify account change from this inbox.",
    "receivedAt": "2026-08-30T14:20:00Z",
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

# Stable AgentMail message ids for the fixture mailbox. Pull-only. Not Shopify.
ADA_MESSAGE_ID = "msg-ada-1001"
SAM_MESSAGE_ID = "msg-sam-rattle"
PRIYA_MESSAGE_ID = "msg-priya-return"
JORDAN_MESSAGE_ID = "msg-jordan-wrong"
PRIZE_MESSAGE_ID = "msg-prize-spam"


def _mailbox_item(message_id: str, fixture: dict) -> dict:
    return {
        "message_id": message_id,
        "from": fixture["from"],
        "subject": fixture["subject"],
        "extracted_text": fixture["body"],
        "text": fixture["body"],
        "extracted_html": None,
        "html": None,
        "received_at": fixture["receivedAt"],
        "labels": ["unread"],
    }


MAILBOX_FIXTURES = (
    _mailbox_item(ADA_MESSAGE_ID, ADA_TRACKING),
    _mailbox_item(SAM_MESSAGE_ID, SAM_RATTLE),
    _mailbox_item(PRIYA_MESSAGE_ID, PRIYA_RETURN),
    _mailbox_item(JORDAN_MESSAGE_ID, JORDAN_WRONG),
    _mailbox_item(PRIZE_MESSAGE_ID, PRIZE_SPAM),
)

FIXTURE_MESSAGE_IDS = frozenset(
    {
        ADA_MESSAGE_ID,
        SAM_MESSAGE_ID,
        PRIYA_MESSAGE_ID,
        JORDAN_MESSAGE_ID,
        PRIZE_MESSAGE_ID,
    }
)
