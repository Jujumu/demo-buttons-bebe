import { MAILBOX_TOPICS } from "../contracts.js";
import { esc, formatWhen, initials } from "../util.js";

/**
 * Thread tissue.
 * In: `{ ticket }`
 * Out: summarize request on `composer/summarize`
 * Status-change lines are muted. No Send.
 */
export function createThreadTissue({ mailbox }) {
  let model = { ticket: null };

  function project(input) {
    return { ticket: input.ticket || null };
  }

  function renderMessage(message) {
    if (message.kind === "status") {
      return `<p class="status-line">${esc(message.body)} · ${esc(formatWhen(message.at))}</p>`;
    }
    const who = message.fromAgent ? "agent" : "customer";
    return `<article class="bubble ${who}">
      <div class="bubble-meta">
        <span class="avatar">${esc(initials(message.name))}</span>
        <strong>${esc(message.name)}</strong>
        <time>${esc(formatWhen(message.at))}</time>
      </div>
      <p>${esc(message.body)}</p>
    </article>`;
  }

  function render(next = model) {
    const ticket = next.ticket;
    if (!ticket) {
      return `<div class="pane-inner"><p class="empty-pane">Select a ticket.</p></div>`;
    }
    const count = (ticket.messages || []).filter((msg) => msg.kind !== "status").length;
    const summarizeLabel = count === 1 ? "Summarize 1 message" : `Summarize ${count} messages`;
    const messages = (ticket.messages || []).map(renderMessage).join("");
    return `<div class="pane-inner thread-inner">
      <header class="thread-head">
        <div>
          <h2>${esc(ticket.messages?.[0]?.name || "Customer")}</h2>
          <p class="thread-subject">${esc(ticket.subject)}</p>
        </div>
        <span class="status-badge">${esc(ticket.status)}</span>
      </header>
      <div class="thread-scroll">${messages}</div>
      <div class="summarize-row">
        <button type="button" class="btn-quiet" data-summarize="${esc(ticket.id)}">${esc(summarizeLabel)}</button>
      </div>
    </div>`;
  }

  function mount(el) {
    el.innerHTML = render(model);
    el.onclick = (event) => {
      const button = event.target.closest("[data-summarize]");
      if (!button) return;
      mailbox.publish(MAILBOX_TOPICS.COMPOSER_SUMMARIZE, { ticketId: button.dataset.summarize });
    };
  }

  return {
    id: "thread",
    project,
    render,
    update(input) {
      model = project(input);
      return model;
    },
    mount,
  };
}
