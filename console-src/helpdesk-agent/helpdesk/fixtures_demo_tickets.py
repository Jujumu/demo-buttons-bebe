"""Thirty varied demo tickets for AI draft review.

Optional message attachments: [{url, alt, mime}]. Never prize/lottery spam.
joined=True rows carry Cute Things GIDs when an order is cited.
"""

from __future__ import annotations

from .fixtures_live_holes import (
    C_FULFILLED,
    C_MULTI,
    C_UNFULFILLED,
    O_1001,
    O_1002,
    O_1003,
    O_1004,
)

STORE = "Demo Shop"

# Pexels stills (demo only). Alt credits photographer via search-time note.
IMG = {
    "rattle": {
        "url": "https://images.pexels.com/photos/129722/pexels-photo-129722.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        "alt": "Damaged wooden toy — photo on Pexels",
        "mime": "image/jpeg",
    },
    "blanket": {
        "url": "https://images.pexels.com/photos/12654853/pexels-photo-12654853.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        "alt": "Stained baby blanket — photo on Pexels",
        "mime": "image/jpeg",
    },
    "romper": {
        "url": "https://images.pexels.com/photos/16222075/pexels-photo-16222075.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        "alt": "Wrong-color romper — photo on Pexels",
        "mime": "image/jpeg",
    },
    "box": {
        "url": "https://images.pexels.com/photos/33634506/pexels-photo-33634506.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        "alt": "Damaged shipping box — photo on Pexels",
        "mime": "image/jpeg",
    },
    "mug": {
        "url": "https://images.pexels.com/photos/36906438/pexels-photo-36906438.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        "alt": "Broken ceramic item — photo on Pexels",
        "mime": "image/jpeg",
    },
    "plush": {
        "url": "https://images.pexels.com/photos/10703078/pexels-photo-10703078.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        "alt": "Torn soft toy — photo on Pexels",
        "mime": "image/jpeg",
    },
    "shoes": {
        "url": "https://images.pexels.com/photos/6902351/pexels-photo-6902351.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        "alt": "Baby shoes size check — photo on Pexels",
        "mime": "image/jpeg",
    },
    "slip": {
        "url": "https://images.pexels.com/photos/19582307/pexels-photo-19582307.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        "alt": "Packing slip photo — photo on Pexels",
        "mime": "image/jpeg",
    },
    "bottle": {
        "url": "https://images.pexels.com/photos/13779106/pexels-photo-13779106.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        "alt": "Spilled bottle mess — photo on Pexels",
        "mime": "image/jpeg",
    },
    "nipple": {
        "url": "https://images.pexels.com/photos/20387764/pexels-photo-20387764.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        "alt": "Silicone bottle part issue — photo on Pexels",
        "mime": "image/jpeg",
    },
}


def _msg(mid: str, name: str, body: str, at: str, *, agent: bool = False, attachments=None) -> dict:
    row = {
        "id": mid,
        "from": "agent" if agent else "customer",
        "fromAgent": agent,
        "name": STORE if agent else name,
        "body": body,
        "at": at,
    }
    if attachments:
        row["attachments"] = list(attachments)
    return row


def _ticket(
    *,
    tid: str,
    name: str,
    subject: str,
    snippet: str,
    status: str,
    assignee,
    updated: str,
    messages: list,
    events: list | None = None,
    customer_id=None,
    order_id=None,
    channel: str = "email",
) -> dict:
    row = {
        "id": tid,
        "customerName": name,
        "subject": subject,
        "snippet": snippet,
        "status": status,
        "assignee": assignee,
        "updatedAt": updated,
        "channel": channel,
        "messages": messages,
        "statusEvents": events or [],
    }
    if customer_id is not None or order_id is not None:
        row["joined"] = True
        row["customerId"] = customer_id
        row["orderId"] = order_id
    return row


DEMO_SEED_TICKETS = (
    _ticket(
        tid="t-demo-01-track",
        name="Maya Chen",
        subject="Tracking stuck on order #1001",
        snippet="Carrier still says label created for #1001. Any update?",
        status="open",
        assignee="me",
        updated="2026-08-31T10:05:00Z",
        customer_id=C_UNFULFILLED,
        order_id=O_1001,
        messages=[
            _msg("d01a", "Maya Chen", "Carrier still says label created for #1001. Any update?", "2026-08-31T10:00:00Z"),
        ],
        events=[{"at": "2026-08-31T10:01:00Z", "status": "open", "note": "created"}],
    ),
    _ticket(
        tid="t-demo-02-wrong-item",
        name="Noah Patel",
        subject="Wrong romper color in #1002",
        snippet="I ordered sage and got pink. Photo attached.",
        status="open",
        assignee="me",
        updated="2026-08-31T11:20:00Z",
        customer_id=C_FULFILLED,
        order_id=O_1002,
        messages=[
            _msg(
                "d02a",
                "Noah Patel",
                "I ordered the sage romper on #1002 and the box had pink. Photo attached — can you help exchange?",
                "2026-08-31T11:15:00Z",
                attachments=[IMG["romper"]],
            ),
        ],
    ),
    _ticket(
        tid="t-demo-03-damaged-rattle",
        name="Sam Rivera",
        subject="Broken rattle arrived",
        snippet="The wooden rattle arrived cracked. Photo attached.",
        status="open",
        assignee="me",
        updated="2026-08-31T12:02:00Z",
        messages=[
            _msg(
                "d03a",
                "Sam Rivera",
                "The wooden rattle arrived cracked through the handle. Photo attached. No order number on the packing slip that I can find.",
                "2026-08-31T12:00:00Z",
                attachments=[IMG["rattle"]],
            ),
        ],
    ),
    _ticket(
        tid="t-demo-04-return",
        name="Priya Nair",
        subject="Start a return for #1003",
        snippet="The merino throw on #1003 is too warm. How do I return it?",
        status="open",
        assignee="me",
        updated="2026-08-31T12:40:00Z",
        customer_id=C_MULTI,
        order_id=O_1003,
        messages=[
            _msg("d04a", "Priya Nair", "The merino throw on #1003 is too warm for our climate. How do I start a return?", "2026-08-31T12:35:00Z"),
            _msg("d04b", "Priya Nair", "Also — is a prepaid label included, or do I buy postage?", "2026-08-31T12:38:00Z"),
        ],
    ),
    _ticket(
        tid="t-demo-05-cancel",
        name="Eli Brooks",
        subject="Cancel #1001 before it ships",
        snippet="Please cancel #1001 if it has not left yet.",
        status="open",
        assignee="me",
        updated="2026-08-31T13:10:00Z",
        customer_id=C_UNFULFILLED,
        order_id=O_1001,
        messages=[
            _msg(
                "d05a",
                "Eli Brooks",
                "Please cancel order #1001 if it has not left the warehouse. We ordered the wrong size.",
                "2026-08-31T13:05:00Z",
            ),
        ],
    ),
    _ticket(
        tid="t-demo-06-angry",
        name="Jordan Lee",
        subject="This is unacceptable — missing item",
        snippet="Box for #1004 was short one bib. I am frustrated.",
        status="open",
        assignee="me",
        updated="2026-08-31T13:55:00Z",
        customer_id=C_MULTI,
        order_id=O_1004,
        messages=[
            _msg(
                "d06a",
                "Jordan Lee",
                "Order #1004 arrived short one snap bib. Packing slip photo attached. This is the second issue and I am frustrated.",
                "2026-08-31T13:50:00Z",
                attachments=[IMG["slip"]],
            ),
        ],
    ),
    _ticket(
        tid="t-demo-07-size",
        name="Ava Nguyen",
        subject="Sizing for Organic Cotton Footed Pajamas",
        snippet="Between 3-6m and 6-12m — which fits a chunky 5 month old?",
        status="open",
        assignee=None,
        updated="2026-08-31T14:20:00Z",
        messages=[
            _msg(
                "d07a",
                "Ava Nguyen",
                "Between 3-6m and 6-12m on the Organic Cotton Footed Pajamas — which fits a chunky 5 month old? Photo of current shoes for scale.",
                "2026-08-31T14:18:00Z",
                attachments=[IMG["shoes"]],
            ),
        ],
    ),
    _ticket(
        tid="t-demo-08-canada",
        name="Luc Martin",
        subject="Do you ship swaddles to Canada?",
        snippet="Can you ship the Muslin Swaddle Trio to Montreal?",
        status="open",
        assignee=None,
        updated="2026-08-31T14:45:00Z",
        messages=[
            _msg("d08a", "Luc Martin", "Can you ship the Muslin Swaddle Trio to Montreal, QC? Duties?", "2026-08-31T14:40:00Z"),
        ],
    ),
    _ticket(
        tid="t-demo-09-address",
        name="Riley Quinn",
        subject="Change ship address on #1001",
        snippet="Please update #1001 to my office address before it ships.",
        status="open",
        assignee="me",
        updated="2026-08-31T15:05:00Z",
        customer_id=C_UNFULFILLED,
        order_id=O_1001,
        messages=[
            _msg(
                "d09a",
                "Riley Quinn",
                "Please change the ship-to on #1001 to 200 Market St, Suite 4, Brooklyn NY 11201 before it leaves.",
                "2026-08-31T15:00:00Z",
            ),
        ],
    ),
    _ticket(
        tid="t-demo-10-stained",
        name="Harper Diaz",
        subject="Blanket arrived stained — #1002",
        snippet="Gauze blanket from #1002 has a stain. Photo attached.",
        status="open",
        assignee="me",
        updated="2026-08-31T15:30:00Z",
        customer_id=C_FULFILLED,
        order_id=O_1002,
        messages=[
            _msg(
                "d10a",
                "Harper Diaz",
                "The Cotton Gauze Dream Blanket on #1002 arrived with a stain near the corner. Photo attached.",
                "2026-08-31T15:25:00Z",
                attachments=[IMG["blanket"]],
            ),
            _msg("d10b", STORE, "Thanks for the photo — reviewing with the warehouse.", "2026-08-31T15:28:00Z", agent=True),
            _msg("d10c", "Harper Diaz", "Any update? We need it for a shower this weekend.", "2026-08-31T15:30:00Z"),
        ],
    ),
    _ticket(
        tid="t-demo-11-chat",
        name="Kit Alvarez",
        subject="Chat: where is #1003?",
        snippet="Any update on #1003 shipping today?",
        status="open",
        assignee="me",
        updated="2026-08-31T16:00:00Z",
        customer_id=C_MULTI,
        order_id=O_1003,
        channel="chat",
        messages=[
            _msg("d11a", "Kit Alvarez", "Hi — any update on #1003 shipping today?", "2026-08-31T15:55:00Z"),
            _msg("d11b", "Kit Alvarez", "Still here if you have an ETA.", "2026-08-31T16:00:00Z"),
        ],
    ),
    _ticket(
        tid="t-demo-12-damaged-box",
        name="Morgan Ellis",
        subject="Package crushed — #1004",
        snippet="Outer box crushed. Items may be fine. Photo attached.",
        status="open",
        assignee=None,
        updated="2026-08-31T16:25:00Z",
        customer_id=C_MULTI,
        order_id=O_1004,
        messages=[
            _msg(
                "d12a",
                "Morgan Ellis",
                "Carrier left #1004 with a crushed outer box. Photo attached. I have not opened the inner wrap yet — what should I do?",
                "2026-08-31T16:20:00Z",
                attachments=[IMG["box"]],
            ),
        ],
    ),
    _ticket(
        tid="t-demo-13-gift",
        name="Casey Sandbox",
        subject="Gift note missing on #1002",
        snippet="Gift note for #1002 was blank. Can you resend a card?",
        status="open",
        assignee=None,
        updated="2026-08-31T16:50:00Z",
        customer_id=C_FULFILLED,
        order_id=O_1002,
        messages=[
            _msg(
                "d13a",
                "Casey Sandbox",
                "I added a gift note on #1002 but the card in the box was blank. Can you mail a replacement card, or is that not possible?",
                "2026-08-31T16:45:00Z",
            ),
        ],
    ),
    _ticket(
        tid="t-demo-14-duplicate",
        name="Drew Kim",
        subject="Charged twice for #1001?",
        snippet="Bank shows two charges that look like #1001.",
        status="open",
        assignee="me",
        updated="2026-08-31T17:10:00Z",
        customer_id=C_UNFULFILLED,
        order_id=O_1001,
        messages=[
            _msg(
                "d14a",
                "Drew Kim",
                "My bank shows two charges that both look like order #1001. Can you confirm whether one is a pending auth?",
                "2026-08-31T17:05:00Z",
            ),
        ],
    ),
    _ticket(
        tid="t-demo-15-stock",
        name="Quinn Foster",
        subject="Restock: Beechwood Push Walker",
        snippet="When is the Beechwood Push Walker back in stock?",
        status="open",
        assignee=None,
        updated="2026-08-31T17:35:00Z",
        messages=[
            _msg(
                "d15a",
                "Quinn Foster",
                "When is the Beechwood Push Walker back in stock? Happy to wait-list if you offer that.",
                "2026-08-31T17:30:00Z",
            ),
        ],
    ),
    _ticket(
        tid="t-demo-16-wholesale",
        name="Boutique North",
        subject="Wholesale pricing for nursery bins",
        snippet="Do you offer wholesale on Linen Nursery Storage Bin?",
        status="open",
        assignee=None,
        updated="2026-08-31T18:00:00Z",
        messages=[
            _msg(
                "d16a",
                "Boutique North",
                "Do you offer wholesale on the Linen Nursery Storage Bin (case packs)? We run a small shop in Portland.",
                "2026-08-31T17:55:00Z",
            ),
        ],
    ),
    _ticket(
        tid="t-demo-17-plush",
        name="Jamie Ortiz",
        subject="Torn plush seam",
        snippet="Soft toy seam tore on day two. Photo attached.",
        status="open",
        assignee="me",
        updated="2026-08-31T18:25:00Z",
        messages=[
            _msg(
                "d17a",
                "Jamie Ortiz",
                "The soft toy seam tore on day two of play. Photo attached. Bought last week — no order number handy but email matches the account.",
                "2026-08-31T18:20:00Z",
                attachments=[IMG["plush"]],
            ),
        ],
    ),
    _ticket(
        tid="t-demo-18-exchange",
        name="Taylor Brooks",
        subject="Exchange hooded towel size — #1003",
        snippet="Need larger hooded towel for #1003.",
        status="open",
        assignee="me",
        updated="2026-08-31T18:50:00Z",
        customer_id=C_MULTI,
        order_id=O_1003,
        messages=[
            _msg(
                "d18a",
                "Taylor Brooks",
                "The Organic Cotton Bath Towel Hood on #1003 is too small. Can we exchange for the next size?",
                "2026-08-31T18:45:00Z",
            ),
        ],
    ),
    _ticket(
        tid="t-demo-19-partial",
        name="Sky Jensen",
        subject="Only one of two swaddles arrived",
        snippet="Muslin Swaddle Trio shipped but only one arrived.",
        status="open",
        assignee="me",
        updated="2026-08-31T19:15:00Z",
        messages=[
            _msg(
                "d19a",
                "Sky Jensen",
                "I ordered the Muslin Swaddle Trio but only one swaddle was in the package. Packing slip attached.",
                "2026-08-31T19:10:00Z",
                attachments=[IMG["slip"]],
            ),
        ],
    ),
    _ticket(
        tid="t-demo-20-delay",
        name="Ada Demo",
        subject="Still waiting on #1001",
        snippet="Following up — #1001 still unfulfilled after a week.",
        status="open",
        assignee="me",
        updated="2026-08-31T19:40:00Z",
        customer_id=C_UNFULFILLED,
        order_id=O_1001,
        messages=[
            _msg("d20a", "Ada Demo", "Following up — order #1001 is still unfulfilled after a week. Can you escalate?", "2026-08-31T19:20:00Z"),
            _msg("d20b", STORE, "Checking fulfillment now.", "2026-08-31T19:30:00Z", agent=True),
            _msg("d20c", "Ada Demo", "Thanks — please write when you have a carrier scan.", "2026-08-31T19:40:00Z"),
        ],
        events=[{"at": "2026-08-31T19:21:00Z", "status": "open", "note": "follow-up"}],
    ),
    _ticket(
        tid="t-demo-21-ceramic",
        name="Blair Soto",
        subject="Night lamp arrived broken",
        snippet="Ceramic Night Light Lamp shattered. Photo attached.",
        status="open",
        assignee=None,
        updated="2026-08-31T20:05:00Z",
        messages=[
            _msg(
                "d21a",
                "Blair Soto",
                "The Ceramic Night Light Lamp arrived shattered in the box. Photo attached. Order was a gift — no number in the note.",
                "2026-08-31T20:00:00Z",
                attachments=[IMG["mug"]],
            ),
        ],
    ),
    _ticket(
        tid="t-demo-22-policy",
        name="Reese Park",
        subject="What is your return window?",
        snippet="How many days to return unused apparel?",
        status="open",
        assignee=None,
        updated="2026-08-31T20:25:00Z",
        messages=[
            _msg(
                "d22a",
                "Reese Park",
                "How many days do I have to return unused baby apparel? Tags still on.",
                "2026-08-31T20:20:00Z",
            ),
        ],
    ),
    _ticket(
        tid="t-demo-23-subscription",
        name="Nina Volkov",
        subject="Pause monthly wipe refill?",
        snippet="Can I pause the wipe refill for one month?",
        status="open",
        assignee=None,
        updated="2026-08-31T20:45:00Z",
        messages=[
            _msg(
                "d23a",
                "Nina Volkov",
                "Can I pause the monthly wipe refill for one month? We still have stock at home.",
                "2026-08-31T20:40:00Z",
            ),
        ],
    ),
    _ticket(
        tid="t-demo-24-bottle",
        name="Omar Haddad",
        subject="Bottle leaked in bag",
        snippet="Formula bottle leaked all over the diaper caddy. Photo.",
        status="open",
        assignee="me",
        updated="2026-08-31T21:05:00Z",
        messages=[
            _msg(
                "d24a",
                "Omar Haddad",
                "The Stainless Straw Cup / bottle setup leaked in the diaper caddy on the first outing. Photo of the mess attached — is the seal defective?",
                "2026-08-31T21:00:00Z",
                attachments=[IMG["bottle"]],
            ),
        ],
    ),
    _ticket(
        tid="t-demo-25-silicone",
        name="Elena Rossi",
        subject="Silicone nipple looks off",
        snippet="New silicone part looks discolored. Photo attached.",
        status="open",
        assignee="me",
        updated="2026-08-31T21:25:00Z",
        messages=[
            _msg(
                "d25a",
                "Elena Rossi",
                "The replacement silicone bottle part looks discolored out of the package. Photo attached — safe to use?",
                "2026-08-31T21:20:00Z",
                attachments=[IMG["nipple"]],
            ),
        ],
    ),
    _ticket(
        tid="t-demo-26-praise",
        name="Chris Young",
        subject="Love the waffle set — sizing tip?",
        snippet="Waffle Knit Lounge Set is great. Sibling size tip?",
        status="open",
        assignee=None,
        updated="2026-08-31T21:45:00Z",
        messages=[
            _msg(
                "d26a",
                "Chris Young",
                "Love the Waffle Knit Lounge Set. Ordering a second for a sibling two months younger — same size or size down?",
                "2026-08-31T21:40:00Z",
            ),
        ],
    ),
    _ticket(
        tid="t-demo-27-snooze",
        name="Pat Okonkwo",
        subject="Waiting on carrier claim for #1002",
        snippet="Snoozed while carrier investigates #1002.",
        status="snoozed",
        assignee="me",
        updated="2026-08-30T09:00:00Z",
        customer_id=C_FULFILLED,
        order_id=O_1002,
        messages=[
            _msg(
                "d27a",
                "Pat Okonkwo",
                "Carrier marked #1002 delivered but we never got it. Opening a claim — please hold.",
                "2026-08-30T08:30:00Z",
            ),
            _msg("d27b", STORE, "Snoozing while the carrier investigates. Write back with their case number.", "2026-08-30T08:50:00Z", agent=True),
        ],
        events=[{"at": "2026-08-30T08:55:00Z", "status": "snoozed", "note": "carrier claim"}],
    ),
    _ticket(
        tid="t-demo-28-closed-thanks",
        name="Ada Demo",
        subject="Replacement received — thank you",
        snippet="Replacement for the stained blanket arrived. Closing.",
        status="closed",
        assignee="me",
        updated="2026-08-29T18:00:00Z",
        customer_id=C_UNFULFILLED,
        order_id=O_1001,
        messages=[
            _msg("d28a", "Ada Demo", "Replacement for the stained blanket arrived. Thank you — you can close this.", "2026-08-29T17:40:00Z"),
            _msg("d28b", STORE, "Glad it reached you, Ada.", "2026-08-29T17:55:00Z", agent=True),
        ],
        events=[{"at": "2026-08-29T18:00:00Z", "status": "closed", "note": "answered"}],
    ),
    _ticket(
        tid="t-demo-29-multi-photo",
        name="Sam Rivera",
        subject="Two issues on one order",
        snippet="Cracked rattle and stained blanket — photos attached.",
        status="open",
        assignee="me",
        updated="2026-08-31T22:10:00Z",
        customer_id=C_FULFILLED,
        order_id=O_1002,
        messages=[
            _msg(
                "d29a",
                "Sam Rivera",
                "On #1002 the rattle arrived cracked and the blanket has a stain. Both photos attached.",
                "2026-08-31T22:05:00Z",
                attachments=[IMG["rattle"], IMG["blanket"]],
            ),
        ],
    ),
    _ticket(
        tid="t-demo-30-preorder",
        name="Jules Abram",
        subject="Preorder ETA for day quilt",
        snippet="When does the Organic Cotton Day Quilt ship if I preorder?",
        status="open",
        assignee=None,
        updated="2026-08-31T22:30:00Z",
        messages=[
            _msg(
                "d30a",
                "Jules Abram",
                "When does the Organic Cotton Day Quilt ship if I preorder today? Need it before Oct 1.",
                "2026-08-31T22:25:00Z",
            ),
        ],
    ),
)

assert len(DEMO_SEED_TICKETS) == 30
