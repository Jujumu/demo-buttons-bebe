import { MAILBOX_TOPICS } from "../contracts.js";
import { listCustomerName } from "../shop/clerk-ticket.js";
import { esc, formatWhen, requestTypeLabel, screenStatus, severityLabel } from "../util.js";

/**
 * List tissue. Client of helpdesk.list_tickets.
 * In: `{ tickets, selectedTicketId, viewLabel }`
 * Out: `{ ticketId }` on `list/selected`
 * Selected row: 4px ink bar. Uses first-party customerName, snippet, and
 * helpdesk status (open / closed / snoozed) — never Return.status.
 */
export function createListTissue({ mailbox }) {
  let model = { tickets: [], selectedTicketId: null, viewLabel: "Inbox" };

  function project(input) {
    return {
      tickets: input.tickets || [],
      selectedTicketId: input.selectedTicketId || null,
      viewLabel: input.viewLabel || "Inbox",
    };
  }

  function renderRow(ticket, selectedId) {
    const on = ticket.id === selectedId;
    const status = ticket.status || "";
    const statusWord = screenStatus(status);
    const typeWord = requestTypeLabel(ticket.requestType);
    const severityWord = severityLabel(ticket.severity);
    const statusHtml = statusWord
      ? `<span class="ticket-status">${esc(statusWord)}</span>`
      : "";
    const typeHtml = typeWord
      ? `<span class="ticket-status ticket-request" data-request-type="${esc(ticket.requestType)}">${esc(typeWord)}</span>`
      : "";
    const severityHtml = severityWord
      ? `<span class="ticket-status ticket-severity" data-severity="${esc(ticket.severity)}">${esc(severityWord)}</span>`
      : "";
    const typeAttr = typeWord ? ` data-request-type="${esc(ticket.requestType)}"` : "";
    const severityAttr = severityWord ? ` data-severity="${esc(ticket.severity)}"` : "";
    const deviceAttr = ticket.device ? ` data-device="${esc(ticket.device)}"` : "";
    return `<button type="button" class="ticket-row${on ? " is-selected" : ""}" data-ticket="${esc(ticket.id)}" data-status="${esc(status)}"${typeAttr}${severityAttr}${deviceAttr} aria-current="${on ? "true" : "false"}">
      <span class="ticket-bar" aria-hidden="true"></span>
      <span class="ticket-top">
        <span class="ticket-name">${esc(listCustomerName(ticket))}</span>
        <span class="ticket-meta">
          ${typeHtml}
          ${severityHtml}
          ${statusHtml}
          <time class="ticket-time" datetime="${esc(ticket.updatedAt || "")}" title="${esc(formatWhen(ticket.updatedAt))}">${esc(formatWhen(ticket.updatedAt, { relative: true }))}</time>
        </span>
      </span>
      <span class="ticket-subject">${esc(ticket.subject)}</span>
      <span class="ticket-snippet">${esc(ticket.snippet || "")}</span>
    </button>`;
  }

  function render(next = model) {
    const rows = next.tickets.length
      ? next.tickets.map((ticket) => renderRow(ticket, next.selectedTicketId)).join("")
      : `<p class="empty-pane">No tickets in this view.</p>`;
    return `<div class="pane-inner">
      <header class="pane-head"><h2>${esc(next.viewLabel)}</h2></header>
      <div class="ticket-list" role="list">${rows}</div>
    </div>`;
  }

  function mount(el) {
    el.innerHTML = render(model);
    el.onclick = (event) => {
      const button = event.target.closest("[data-ticket]");
      if (!button) return;
      mailbox.publish(MAILBOX_TOPICS.LIST_SELECTED, { ticketId: button.dataset.ticket });
    };
  }

  return {
    id: "list",
    project,
    render,
    update(input) {
      model = project(input);
      return model;
    },
    mount,
  };
}
