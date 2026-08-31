import { MAILBOX_TOPICS } from "../contracts.js";
import { clerkStatusEvents, talkMessages } from "../shop/clerk-ticket.js";
import { esc, formatWeekday, formatWhen, initials, screenStatus } from "../util.js";

/**
 * Thread tissue.
 * In: `{ ticket }` from helpdesk.get_ticket
 * Out: summarize request on `composer/summarize`
 * Status-change events are muted as `Closed · Tuesday`. No Send.
 */
export function createThreadTissue({ mailbox }) {
  let model = { ticket: null };

  function project(input) {
    return { ticket: input.ticket || null };
  }

  function renderAttachments(message) {
    const rows = Array.isArray(message.attachments) ? message.attachments : [];
    if (!rows.length) return "";
    const figures = rows
      .filter((item) => item && item.url)
      .map((item) => {
        const alt = item.alt || "Attachment";
        return `<figure class="bubble-attach">
          <img src="${esc(item.url)}" alt="${esc(alt)}" loading="lazy" />
          <figcaption>${esc(alt)}</figcaption>
        </figure>`;
      })
      .join("");
    return figures ? `<div class="bubble-attachments">${figures}</div>` : "";
  }

  function renderMessage(message) {
    const who = message.fromAgent || message.from === "agent" ? "agent" : "customer";
    return `<article class="bubble ${who}">
      <div class="bubble-meta">
        <span class="avatar">${esc(initials(message.name))}</span>
        <strong>${esc(message.name)}</strong>
        <time>${esc(formatWhen(message.at))}</time>
      </div>
      <p>${esc(message.body)}</p>
      ${renderAttachments(message)}
    </article>`;
  }

  function renderStatus(event) {
    return `<p class="status-line">${esc(screenStatus(event.status))} · ${esc(formatWeekday(event.at))}</p>`;
  }

  function timeline(ticket) {
    const items = [
      ...talkMessages(ticket).map((message) => ({ at: message.at, html: renderMessage(message) })),
      ...clerkStatusEvents(ticket).map((event) => ({ at: event.at, html: renderStatus(event) })),
    ];
    items.sort((a, b) => String(a.at || "").localeCompare(String(b.at || "")));
    return items.map((item) => item.html).join("");
  }

  function render(next = model) {
    const ticket = next.ticket;
    if (!ticket) {
      return `<div class="pane-inner"><p class="empty-pane">Select a ticket.</p></div>`;
    }
    const count = talkMessages(ticket).length;
    const summarizeLabel = count === 1 ? "Summarize 1 message" : `Summarize ${count} messages`;
    return `<div class="pane-inner thread-inner">
      <header class="thread-head">
        <div>
          <h2>${esc(ticket.customerName || "Customer")}</h2>
          <p class="thread-subject">${esc(ticket.subject)}</p>
        </div>
        <span class="status-badge">${esc(screenStatus(ticket.status))}</span>
      </header>
      <div class="thread-scroll">${timeline(ticket)}</div>
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
