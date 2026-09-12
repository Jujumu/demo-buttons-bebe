/** First-party bulk assign / snooze / trash. Never a Shopify mutation. */

export const BULK_ACTIONS = Object.freeze(["assign", "snooze", "trash"]);

export function normalizeAssignee(value) {
  if (value == null) return null;
  const raw = String(value).trim().toLowerCase();
  if (!raw || raw === "unassigned" || raw === "none" || raw === "null") return null;
  if (raw === "me") return "me";
  throw new Error("assignee must be me or unassigned");
}

export function applyBulkAction(ticket, action, assignee) {
  if (!ticket) return null;
  const now = new Date().toISOString();
  if (action === "assign") {
    const next = normalizeAssignee(assignee);
    const previous = ticket.assignee ?? null;
    ticket.assignee = next;
    ticket.updatedAt = now;
    if (previous !== next) {
      ticket.statusEvents = [
        ...(ticket.statusEvents || []),
        { at: now, status: ticket.status, note: next === "me" ? "assigned" : "unassigned" },
      ];
    }
    return ticket;
  }
  if (action === "snooze") {
    const previous = ticket.status;
    ticket.status = "snoozed";
    ticket.updatedAt = now;
    if (previous !== "snoozed") {
      ticket.statusEvents = [
        ...(ticket.statusEvents || []),
        { at: now, status: "snoozed", note: "snoozed" },
      ];
    }
    return ticket;
  }
  if (action === "trash") {
    const already = Boolean(ticket.archived);
    ticket.archived = true;
    ticket.updatedAt = now;
    if (!already) {
      ticket.statusEvents = [
        ...(ticket.statusEvents || []),
        { at: now, status: ticket.status, note: "archived" },
      ];
    }
    return ticket;
  }
  throw new Error("action must be assign, snooze, or trash");
}
