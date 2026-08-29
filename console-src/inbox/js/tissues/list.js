import { MAILBOX_TOPICS } from "../contracts.js";
import { esc, formatWhen } from "../util.js";

/**
 * List tissue.
 * In: `{ tickets, selectedTicketId, viewLabel }`
 * Out: `{ ticketId }` on `list/selected`
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
    const snippet = (ticket.messages || []).find((msg) => msg.kind !== "status")?.body || "";
    return `<button type="button" class="ticket-row${on ? " is-selected" : ""}" data-ticket="${esc(ticket.id)}" aria-current="${on ? "true" : "false"}">
      <span class="ticket-bar" aria-hidden="true"></span>
      <span class="ticket-top">
        <span class="ticket-name">${esc(ticket.messages?.[0]?.name || "Customer")}</span>
        <time class="ticket-time">${esc(formatWhen(ticket.updatedAt))}</time>
      </span>
      <span class="ticket-subject">${esc(ticket.subject)}</span>
      <span class="ticket-snippet">${esc(snippet)}</span>
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
