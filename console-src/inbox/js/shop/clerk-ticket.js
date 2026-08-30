/**
 * First-party Clerk ticket projection.
 * customerName is ours — never Customer.displayName.
 * status is open / closed / snoozed — never Return.status OPEN.
 */

export const TICKET_STATUSES = Object.freeze(["open", "closed", "snoozed"]);

export function clerkTicketRow(ticket) {
  if (!ticket) return null;
  return {
    id: ticket.id,
    customerName: ticket.customerName || "",
    subject: ticket.subject || "",
    snippet: ticket.snippet || "",
    status: ticket.status,
    updatedAt: ticket.updatedAt,
    customerId: ticket.customerId || null,
    orderId: ticket.orderId ?? null,
  };
}

export function talkMessages(ticket) {
  return (ticket?.messages || []).filter((message) => message.kind !== "status");
}

export function clerkStatusEvents(ticket) {
  if (Array.isArray(ticket?.statusEvents) && ticket.statusEvents.length) {
    return ticket.statusEvents.map((event) => ({
      at: event.at,
      status: event.status,
      note: event.note || "",
    }));
  }
  return (ticket?.messages || [])
    .filter((message) => message.kind === "status")
    .map((message) => ({
      at: message.at,
      status: ticket.status,
      note: message.body || "",
    }));
}

export function clerkTicket(ticket) {
  if (!ticket) return null;
  return {
    ...clerkTicketRow(ticket),
    messages: talkMessages(ticket).map((message) => ({ ...message })),
    statusEvents: clerkStatusEvents(ticket),
    stubDraft: ticket.stubDraft,
    stubSummary: ticket.stubSummary,
    toEmail: ticket.toEmail,
    assignee: ticket.assignee,
    view: ticket.view,
  };
}
